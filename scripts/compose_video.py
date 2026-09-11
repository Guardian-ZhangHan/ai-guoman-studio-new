#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
成片合成器：FFmpeg 编排
================================================================
把 04_shots/ 下的镜头素材、05_audio/ 下的配音与 BGM、字幕，
按分镜顺序合成为成片。

支持：
    - 镜头拼接与统一分辨率/帧率（不同平台生成的素材尺寸常不一致）
    - 配音按时间轴对齐（adelay 定位到全局时间轴）
    - BGM 自动闪避（sidechaincompress 侧链压缩：说话时音乐自动降低）
    - 字幕烧录（中文字体 + 描边，防糊在浅色画面上）
    - 片名卡 drawtext 叠加
    - 母版响度归一（loudnorm，按平台要求设 LUFS）
    - --dry-run 只打印命令不执行（没装 ffmpeg 也能检查命令是否正确）

用法：
    python scripts/compose_video.py --project configs/demo_short.json --dry-run
    python scripts/compose_video.py --project configs/demo_short.json
    python scripts/compose_video.py --project configs/demo_short.json --no-subtitle
    python scripts/compose_video.py --project configs/demo_short.json --preview-only  # 只合成前 3 镜

退出码：
    0  成功（或 dry-run 正常）
    1  素材缺失 / ffmpeg 不可用 / 执行失败
================================================================
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


# ============================================================
# 工具
# ============================================================
def load_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"配置不存在: {path}")
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in (".yaml", ".yml"):
        try:
            import yaml  # type: ignore
        except ImportError as exc:
            raise RuntimeError("读取 YAML 需 pyyaml：pip install 'pyyaml>=6.0'") from exc
        return yaml.safe_load(text)
    return json.loads(text)


def find_ffmpeg() -> tuple[str | None, str]:
    """定位 ffmpeg：优先系统 PATH，其次 imageio-ffmpeg 自带的二进制。"""
    exe = shutil.which("ffmpeg")
    if exe:
        return exe, "系统 PATH"
    try:
        import imageio_ffmpeg  # type: ignore

        return imageio_ffmpeg.get_ffmpeg_exe(), "imageio-ffmpeg 内置"
    except Exception:  # noqa: BLE001
        return None, "未找到"


def ffmpeg_version(ffmpeg: str) -> str:
    try:
        out = subprocess.run(
            [ffmpeg, "-version"], capture_output=True, text=True, timeout=15,
        )
        return out.stdout.splitlines()[0] if out.stdout else "未知版本"
    except Exception as exc:  # noqa: BLE001
        return f"版本读取失败: {exc}"


def escape_ffmpeg_path(path: Path) -> str:
    """ffmpeg 滤镜里的路径需要转义盘符冒号与反斜杠（Windows 尤其关键）。"""
    s = str(path).replace("\\", "/")
    s = s.replace(":", r"\:")
    return s


def wrap_drawtext_text(text: str) -> str:
    """drawtext 里的中文文本需要转义特殊字符。"""
    return text.replace("\\", r"\\").replace(":", r"\:").replace("'", r"\'")


# 中文字体候选：按平台常见度排序
DEFAULT_FONT_CANDIDATES = [
    "Noto Sans CJK SC",        # Linux / CI（fonts-noto-cjk）
    "Source Han Sans SC",      # Adobe 思源黑体
    "Microsoft YaHei",         # Windows
    "SimHei",                  # Windows 备选
    "PingFang SC",             # macOS
    "WenQuanYi Zen Hei",       # Linux 备选
]


def resolve_font_name(candidates: list[str], configured: str | None) -> tuple[str, str]:
    """解析实际可用的中文字体名。

    为什么必须做这一步：libass 按字体名查找，找不到就静默回退到默认字体，
    而默认字体常常没有中文字形 —— 结果就是字幕全是方框（豆腐块），
    但 ffmpeg 不会报任何错。这是 AI 短片流水线里最难排查的坑之一。

    返回 (字体名, 判定依据)。
    """
    # 1. 若配置的字体确实存在，直接用
    if configured:
        found, how = _font_exists(configured)
        if found:
            return configured, how

    # 2. 依次尝试候选字体
    for name in candidates:
        found, how = _font_exists(name)
        if found:
            note = f"已解析到『{name}』（{how}）"
            if configured and configured != name:
                note += f"；配置的『{configured}』在本机不存在，已自动替换"
            return name, note

    # 3. 都找不到：仍返回配置值，但调用方会打印警告
    fallback = configured or candidates[0]
    return fallback, f"警告：未在系统字体中找到任何中文字体，字幕可能渲染为方框。请安装 fonts-noto-cjk / 思源黑体 / 微软雅黑"


def _font_exists(family: str) -> tuple[bool, str]:
    """检查字体族是否可用：优先用 fc-list（Linux），Windows 查字体目录。"""
    fc_list = shutil.which("fc-list")
    if fc_list:
        try:
            out = subprocess.run(
                [fc_list, ":lang=zh", "family"], capture_output=True, text=True, timeout=10,
            )
            families = out.stdout.lower()
            if family.lower() in families:
                return True, "fontconfig fc-list 命中"
            return False, "fontconfig 未命中"
        except Exception:  # noqa: BLE001
            pass

    # Windows：查字体目录里的常见文件名特征
    if sys.platform.startswith("win"):
        patterns = {
            "microsoft yahei": ["msyh.ttc", "msyh.ttf"],
            "simhei": ["simhei.ttf"],
            "simsun": ["simsun.ttc"],
            "noto sans cjk sc": ["NotoSansCJK", "NotoSansSC"],
            "source han sans sc": ["SourceHanSans"],
            "pingfang sc": ["PingFang"],
            "wenquanyi zen hei": ["wqy-zenhei"],
        }
        win_fonts = Path("C:/Windows/Fonts")
        if win_fonts.exists():
            key = family.lower()
            targets = patterns.get(key)
            if targets:
                for f in win_fonts.iterdir():
                    if any(f.name.startswith(t) for t in targets):
                        return True, "Windows 字体目录命中"
            return False, "Windows 字体目录未命中"
    return False, "无法检测"


# ============================================================
# 素材盘点
# ============================================================
def collect_assets(config: dict[str, Any], root: Path, preview_only: int | None) -> dict[str, Any]:
    shots = config.get("shots", [])
    if preview_only:
        shots = shots[:preview_only]

    video_ok: list[dict[str, Any]] = []
    video_missing: list[str] = []
    for shot in shots:
        p = root / "04_shots" / f"{shot['id']}.mp4"
        if p.exists() and p.stat().st_size > 0:
            video_ok.append({**shot, "path": p})
        else:
            video_missing.append(shot["id"])

    voice_tracks: list[dict[str, Any]] = []
    voice_missing: list[str] = []
    cursor = 0.0
    for shot in shots:
        for line in shot.get("dialogue", []):
            start = cursor + float(line.get("start_sec", 0))
            p = root / "05_audio" / "voice" / f"{shot['id']}_{line['character']}.mp3"
            if p.exists() and p.stat().st_size > 0:
                voice_tracks.append({"path": p, "start": start, "shot": shot["id"],
                                     "char": line["character"], "text": line.get("text", "")})
            else:
                voice_missing.append(f"{shot['id']}_{line['character']}.mp3")
        cursor += float(shot.get("duration_sec", 0))

    bgm_cfg = config.get("audio", {}).get("bgm", {})
    bgm_path = root / bgm_cfg.get("file", "") if bgm_cfg.get("file") else None
    bgm = bgm_path if (bgm_path and bgm_path.exists()) else None

    srt = root / "05_audio" / "subtitles.srt"

    return {
        "video_ok": video_ok,
        "video_missing": video_missing,
        "voice_tracks": voice_tracks,
        "voice_missing": voice_missing,
        "bgm": bgm,
        "srt": srt if srt.exists() else None,
        "shot_count": len(shots),
    }


# ============================================================
# 命令构建
# ============================================================
def build_commands(
    config: dict[str, Any],
    root: Path,
    assets: dict[str, Any],
    ffmpeg: str | None,
    burn_subtitle: bool,
    use_bgm: bool,
    loudnorm: bool,
) -> tuple[list[str], Path, Path]:
    """返回 (ffmpeg 命令列表, concat 清单路径, 输出路径)。"""
    project = config.get("project", {})
    out_cfg = config.get("output", {})
    sub_cfg = config.get("subtitle", {})
    audio_cfg = config.get("audio", {})

    final_dir = root / "06_final"
    final_dir.mkdir(parents=True, exist_ok=True)
    output = final_dir / out_cfg.get("filename", "final.mp4")
    concat_file = final_dir / "concat_list.txt"

    # ---- concat 清单 ----
    lines = []
    for shot in assets["video_ok"]:
        rel = shot["path"].as_posix()
        lines.append(f"file '{rel}'")
    concat_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # ---- 分辨率与帧率 ----
    resolution = str(project.get("resolution", "1920x1080"))
    width, height = resolution.lower().split("x")
    fps = str(project.get("fps", 24))

    inputs: list[str] = ["-f", "concat", "-safe", "0", "-i", str(concat_file)]

    # ---- 配音输入 ----
    for track in assets["voice_tracks"]:
        inputs += ["-i", str(track["path"])]

    # ---- BGM 输入 ----
    bgm_index = None
    if use_bgm and assets["bgm"]:
        bgm_index = 1 + len(assets["voice_tracks"])
        inputs += ["-stream_loop", "-1", "-i", str(assets["bgm"])]

    # ---- 视频滤镜链 ----
    vf = [
        f"scale={width}:{height}:force_original_aspect_ratio=decrease",
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black",
        f"fps={fps}",
        "format=yuv420p",
    ]

    # 解析实际可用的中文字体（避免字幕渲染成方框）
    font_candidates = sub_cfg.get("font_candidates") or DEFAULT_FONT_CANDIDATES
    font_name, font_note = resolve_font_name(
        list(font_candidates), sub_cfg.get("style", {}).get("font_name")
    )
    assets["font_name"] = font_name
    assets["font_note"] = font_note
    assets["title_font_missing"] = None

    # 片名卡（drawtext）
    overlay = next(
        (s.get("post_overlay") for s in config.get("shots", [])
         if s.get("post_overlay") and s.get("post_overlay", {}).get("type") == "title_card"),
        None,
    )
    if overlay and overlay.get("text"):
        font_file = root / overlay["font"] if overlay.get("font") else None
        start = float(overlay.get("start_sec", 0))
        end = start + float(overlay.get("duration_sec", 2))
        if font_file and font_file.exists():
            font_clause = f":fontfile='{escape_ffmpeg_path(font_file)}'"
        else:
            # 字体文件缺失时退回按字体族名查找（需 ffmpeg 编译了 fontconfig）
            font_clause = f":font='{font_name}'"
            assets["title_font_missing"] = str(overlay.get("font"))
        vf.append(
            "drawtext"
            + font_clause
            + f":text='{wrap_drawtext_text(overlay['text'])}'"
            + f":fontsize={int(int(height) * 0.09)}"
            + ":fontcolor=white@0.95"
            + ":borderw=3:bordercolor=black@0.55"
            + ":x=(w-text_w)/2:y=(h-text_h)/2"
            + f":enable='between(t,{start:.3f},{end:.3f})'"
        )
        if overlay.get("subtext"):
            vf.append(
                "drawtext"
                + font_clause
                + f":text='{wrap_drawtext_text(overlay['subtext'])}'"
                + f":fontsize={int(int(height) * 0.032)}"
                + ":fontcolor=white@0.8"
                + f":x=(w-text_w)/2:y=(h-text_h)/2+{int(int(height) * 0.075)}"
                + f":enable='between(t,{start + 0.6:.3f},{end:.3f})'"
            )

    # 字幕烧录
    if burn_subtitle and assets["srt"]:
        style_cfg = sub_cfg.get("style", {})
        force_style = ",".join([
            f"FontName={font_name}",
            f"FontSize={style_cfg.get('font_size', 26)}",
            f"PrimaryColour=&H{style_cfg.get('primary_color', 'FFFFFF')}",
            f"OutlineColour=&H{style_cfg.get('outline_color', '1B2A33')}",
            f"Outline={style_cfg.get('outline_width', 2)}",
            f"Shadow={style_cfg.get('shadow', 1)}",
            f"MarginV={style_cfg.get('margin_v', 48)}",
            f"Alignment={style_cfg.get('alignment', 2)}",
            "BorderStyle=1",
        ])
        vf.append(
            f"subtitles='{escape_ffmpeg_path(assets['srt'])}'"
            f":force_style='{force_style}'"
        )

    filter_parts: list[str] = [f"[0:v]{','.join(vf)}[vout]"]

    # ---- 音频滤镜链 ----
    n_voice = len(assets["voice_tracks"])
    voice_labels: list[str] = []
    for idx, track in enumerate(assets["voice_tracks"], start=1):
        delay_ms = int(round(track["start"] * 1000))
        # adelay 需为每个声道给值，这里统一按立体声处理
        label = f"v{idx}"
        filter_parts.append(
            f"[{idx}:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,"
            f"adelay={delay_ms}|{delay_ms},volume=1.0[{label}]"
        )
        voice_labels.append(f"[{label}]")

    voice_mix_label = None
    if voice_labels:
        if len(voice_labels) == 1:
            filter_parts.append(f"{voice_labels[0]}anull[voicemix]")
        else:
            filter_parts.append(
                f"{''.join(voice_labels)}amix=inputs={len(voice_labels)}"
                f":duration=longest:normalize=0[voicemix]"
            )
        voice_mix_label = "[voicemix]"

    bgm_cfg = audio_cfg.get("bgm", {})
    base_vol_db = float(bgm_cfg.get("base_volume_db", -22))
    duck_db = float(bgm_cfg.get("ducking_db", -8))
    ducking = bool(bgm_cfg.get("ducking_on_dialogue", True)) and voice_mix_label is not None
    fade_in = float(bgm_cfg.get("fade_in_sec", 2.0))
    fade_out = float(bgm_cfg.get("fade_out_sec", 3.0))

    audio_map_label = None
    if bgm_index is not None:
        filter_parts.append(
            f"[{bgm_index}:a]aresample=48000,"
            f"aformat=sample_fmts=fltp:channel_layouts=stereo,"
            f"volume={base_vol_db}dB[bgmraw]"
        )
        if ducking:
            # 侧链压缩实现「说话时音乐自动降低」
            filter_parts.append(
                f"[bgmraw][voicemix]sidechaincompress="
                f"threshold=0.05:ratio=6:attack=20:release=350:makeup=1[bgmduck]"
            )
            bgm_label = "[bgmduck]"
            # 侧链已降低，再补偿 duck_db
            filter_parts.append(f"{bgm_label}volume={duck_db}dB[bgm]")
            bgm_label = "[bgm]"
        else:
            filter_parts.append("[bgmraw]anull[bgm]")
            bgm_label = "[bgm]"

        if voice_mix_label:
            filter_parts.append(
                f"{voice_mix_label}{bgm_label}amix=inputs=2:duration=longest:normalize=0[mixed]"
            )
            audio_map_label = "[mixed]"
        else:
            audio_map_label = bgm_label
    elif voice_mix_label:
        audio_map_label = voice_mix_label

    if audio_map_label and loudnorm:
        target = float(audio_cfg.get("master", {}).get("loudness_target_lufs", -14))
        tp = float(audio_cfg.get("master", {}).get("true_peak_db", -1.0))
        filter_parts.append(
            f"{audio_map_label}loudnorm=I={target}:TP={tp}:LRA=11[audioout]"
        )
        audio_map_label = "[audioout]"

    # ---- 组装命令 ----
    cmd: list[str] = []
    if ffmpeg:
        cmd.append(ffmpeg)
    else:
        cmd.append("ffmpeg")     # dry-run 时给出可读命令
    cmd += ["-y"]
    cmd += inputs
    cmd += ["-filter_complex", ";".join(filter_parts)]
    cmd += ["-map", "[vout]"]
    if audio_map_label:
        cmd += ["-map", audio_map_label]
    cmd += [
        "-c:v", out_cfg.get("codec", "libx264"),
        "-crf", str(out_cfg.get("crf", 18)),
        "-preset", out_cfg.get("preset", "slow"),
        "-pix_fmt", out_cfg.get("pix_fmt", "yuv420p"),
    ]
    if audio_map_label:
        cmd += [
            "-c:a", out_cfg.get("audio_codec", "aac"),
            "-b:a", out_cfg.get("audio_bitrate", "192k"),
            "-ar", "48000",
        ]
    cmd += ["-movflags", out_cfg.get("movflags", "+faststart")]
    cmd.append(str(output))

    return cmd, concat_file, output


# ============================================================
# 主流程
# ============================================================
def main() -> int:
    parser = argparse.ArgumentParser(description="成片合成器（FFmpeg 编排）")
    parser.add_argument("--project", required=True, help="项目配置文件")
    parser.add_argument("--outdir", default=str(ROOT), help="项目根目录")
    parser.add_argument("--dry-run", action="store_true", help="只打印命令，不执行")
    parser.add_argument("--no-subtitle", action="store_true", help="不烧录字幕")
    parser.add_argument("--no-bgm", action="store_true", help="不加背景音乐")
    parser.add_argument("--no-loudnorm", action="store_true", help="不做响度归一")
    parser.add_argument("--preview-only", type=int, default=None, help="只合成前 N 镜做预览")
    args = parser.parse_args()

    root = Path(args.outdir).resolve()
    cfg_path = Path(args.project)
    if not cfg_path.is_absolute():
        cfg_path = (root / cfg_path).resolve()

    try:
        config = load_config(cfg_path)
    except Exception as exc:  # noqa: BLE001
        print(f"[错误] 读取配置失败: {exc}", file=sys.stderr)
        return 1

    project = config.get("project", {})
    line = "=" * 72
    print(line)
    print(f" 成片合成 · {project.get('title', '未命名')}"
          + ("  [预览模式：只合成前 %d 镜]" % args.preview_only if args.preview_only else ""))
    print(line)

    # ---- ffmpeg 检查 ----
    ffmpeg, source = find_ffmpeg()
    if ffmpeg:
        print(f" FFmpeg：{ffmpeg_version(ffmpeg)}")
        print(f" 来源  ：{source}")
    else:
        print(" FFmpeg：未找到")
        print(" 修复  ：pip install imageio-ffmpeg  （会自动带上 ffmpeg 二进制）")
        print("         或系统安装：https://ffmpeg.org/download.html")
    print("-" * 72)

    # ---- 素材盘点 ----
    assets = collect_assets(config, root, args.preview_only)
    print(f" 镜头素材：就绪 {len(assets['video_ok'])} / 共 {assets['shot_count']} 镜")
    for sid in assets["video_missing"]:
        print(f"   [缺失] 04_shots/{sid}.mp4")
    print(f" 配音文件：就绪 {len(assets['voice_tracks'])} 条"
          + (f"，缺失 {len(assets['voice_missing'])} 条" if assets["voice_missing"] else ""))
    for name in assets["voice_missing"]:
        print(f"   [缺失] 05_audio/voice/{name}")
    print(f" BGM     ：{'已就位 ' + assets['bgm'].name if assets['bgm'] else '未找到（将合成无 BGM 版本）'}")
    print(f" 字幕    ：{'已就位' if assets['srt'] else '未找到（将不烧录字幕）'}")
    print("-" * 72)

    if not assets["video_ok"]:
        if not args.dry_run:
            print(" [失败] 没有任何可用的镜头素材，无法合成。")
            print("        请先把生成的视频放到 04_shots/，命名格式 S001.mp4 / S002.mp4 ...")
            print("        分镜清单见 02_storyboard/shots.csv（含每镜的目标文件名）")
            print(line)
            return 1
        # dry-run 场景：用占位路径演示完整命令，便于在没素材时核对滤镜图与参数
        print(" [提示] 暂无真实素材。--dry-run 模式将用占位路径演示完整命令结构，")
        print("        便于在生成素材前先核对滤镜链、时间轴与编码参数是否正确。")
        print("-" * 72)
        shots = config.get("shots", [])[: (args.preview_only or None)]
        placeholder: list[dict[str, Any]] = []
        cursor = 0.0
        for shot in shots:
            placeholder.append({**shot, "path": root / "04_shots" / f"{shot['id']}.mp4"})
            for line_cfg in shot.get("dialogue", []):
                assets["voice_tracks"].append({
                    "path": root / "05_audio" / "voice" / f"{shot['id']}_{line_cfg['character']}.mp3",
                    "start": cursor + float(line_cfg.get("start_sec", 0)),
                    "shot": shot["id"],
                    "char": line_cfg["character"],
                    "text": line_cfg.get("text", ""),
                })
            cursor += float(shot.get("duration_sec", 0))
        assets["video_ok"] = placeholder
        if assets["bgm"] is None:
            bgm_rel = config.get("audio", {}).get("bgm", {}).get("file")
            if bgm_rel:
                assets["bgm"] = root / bgm_rel
                print(f" [提示] BGM 亦为占位路径: {bgm_rel}")

    burn_sub = not args.no_subtitle and assets["srt"] is not None
    cmd, concat_file, output = build_commands(
        config, root, assets, ffmpeg,
        burn_subtitle=burn_sub,
        use_bgm=not args.no_bgm,
        loudnorm=not args.no_loudnorm,
    )

    print(f" 合成清单：{concat_file.relative_to(root)}（{len(assets['video_ok'])} 个镜头）")
    print(f" 输出    ：{output.relative_to(root)}")
    print(f" 字幕    ：{'烧录' if burn_sub else '不烧录'}")
    if burn_sub:
        print(f" 中文字体：{assets.get('font_name')}")
        print(f"           {assets.get('font_note')}")
    if assets.get("title_font_missing"):
        print(f" [警告] 片名字体文件不存在: {assets['title_font_missing']}")
        print("        已退回按字体族名查找；若 ffmpeg 未启用 fontconfig，片名可能不显示。")
        print("        建议把字体放到 assets/fonts/ 并在配置里指向它。")
    print("-" * 72)
    print(" FFmpeg 命令：")
    shown = " ".join(f'"{c}"' if " " in c and not c.startswith("[") else c for c in cmd)
    print(f" {shown}")
    print(line)

    if args.dry_run:
        print(" 模式：--dry-run，未执行。去掉该参数即真正合成。")
        print(line)
        return 0

    if not ffmpeg:
        print(" [失败] 未找到 ffmpeg，无法执行。先按上面的修复命令安装，")
        print("        或用 --dry-run 检查命令是否正确。")
        print(line)
        return 1

    print(" 正在合成……（耗时取决于素材总时长与预设）")
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True)
    except Exception as exc:  # noqa: BLE001
        print(f" [失败] 执行异常: {exc}")
        return 1

    if proc.returncode != 0:
        print(" [失败] FFmpeg 返回非零退出码，末尾日志：")
        for l in (proc.stderr or "").strip().splitlines()[-15:]:
            print(f"   {l}")
        print(line)
        return 1

    size_mb = output.stat().st_size / 1024 / 1024 if output.exists() else 0
    print(f" [成功] 成片已生成：{output}")
    print(f"        文件大小：{size_mb:.1f} MB")
    print(line)
    print(" 成片后仍需人工完成的检查：")
    print("   1. 逐镜检查角色一致性（有无换脸/服装漂移）")
    print("   2. 逐句校对字幕（错别字、多音字、事实性错误）")
    print("   3. 试听配音（语气、断句、响度）")
    print("   4. 版权与合规自查（见 config 的 compliance.checklist）")
    print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
