#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
分镜生成器：把项目配置变成可执行的生产资料
================================================================
输入：configs/*.json（或 .yaml）
输出：
    02_storyboard/shotlist.md              人读分镜表
    02_storyboard/shots.csv                机读镜头清单（可导入批量生成平台）
    02_storyboard/prompts/S001_image.txt   文生图提示词（可直接粘贴）
    02_storyboard/prompts/S001_video.txt   图生视频提示词
    05_audio/voiceover.csv                 配音清单（角色/台词/时间轴/情感）
    05_audio/subtitles.srt                 字幕文件

同时执行 7 项一致性校验，把「AI 短片最容易崩的地方」在生成之前就拦住：
    1. 镜头 ID 唯一性
    2. 引用角色是否在角色表里存在
    3. 多镜头出现的角色是否配置了一致性锚点（seed/参考图/LoRA）
    4. 风格前缀是否齐全（style_prefix_required）
    5. 台词时间轴是否超出镜头时长
    6. 分幕结构与实际镜头是否对得上
    7. 总时长是否偏离目标时长

用法：
    python scripts/build_shotlist.py --config configs/demo_short.json
    python scripts/build_shotlist.py --config configs/demo_short.json --strict
    python scripts/build_shotlist.py --config configs/demo_short.yaml  # 需 pyyaml

退出码：
    0  校验通过（或仅有警告）
    1  存在错误，或 --strict 下有警告
================================================================
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

# 中文 TTS 语速估算：约 4.8 字/秒（edge-tts 正常语速经验值）
CHARS_PER_SECOND = 4.8

ROOT = Path(__file__).resolve().parents[1]


# ============================================================
# 配置读取
# ============================================================
def load_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"配置文件不存在: {path}")

    text = path.read_text(encoding="utf-8")

    if path.suffix.lower() in (".yaml", ".yml"):
        try:
            import yaml  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "读取 YAML 需要 pyyaml：pip install 'pyyaml>=6.0'\n"
                "或者改用 JSON 配置（configs/demo_short.json）"
            ) from exc
        return yaml.safe_load(text)

    return json.loads(text)


# ============================================================
# 校验
# ============================================================
@dataclass
class Issue:
    level: str        # error | warn | info
    scope: str        # 校验项名称
    message: str


@dataclass
class Validator:
    issues: list[Issue] = field(default_factory=list)

    def error(self, scope: str, msg: str) -> None:
        self.issues.append(Issue("error", scope, msg))

    def warn(self, scope: str, msg: str) -> None:
        self.issues.append(Issue("warn", scope, msg))

    def info(self, scope: str, msg: str) -> None:
        self.issues.append(Issue("info", scope, msg))

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.level == "error"]

    @property
    def warns(self) -> list[Issue]:
        return [i for i in self.issues if i.level == "warn"]


def estimate_speech_duration(text: str) -> float:
    """按中文字数估算配音时长（秒）。标点按停顿计 0.3 秒。"""
    punctuation = len(re.findall(r"[，。！？、；：…—]", text))
    chars = len(re.sub(r"\s", "", text))
    return chars / CHARS_PER_SECOND + punctuation * 0.3


def validate(config: dict[str, Any], v: Validator) -> None:
    project = config.get("project", {})
    style = config.get("style_bible", {})
    characters = {c["id"]: c for c in config.get("characters", [])}
    shots = config.get("shots", [])

    # ---- 校验 1：镜头 ID 唯一性 ----
    seen: set[str] = set()
    for shot in shots:
        sid = shot.get("id", "")
        if not sid:
            v.error("镜头ID", "存在没有 id 的镜头")
            continue
        if sid in seen:
            v.error("镜头ID", f"镜头 ID 重复: {sid}")
        seen.add(sid)

    # ---- 校验 2：引用角色必须存在 ----
    for shot in shots:
        for cid in shot.get("characters", []):
            if cid not in characters:
                v.error("角色引用", f"镜头 {shot.get('id')} 引用了未定义的角色 {cid}")

    # ---- 校验 3：多镜头角色必须具备一致性锚点 ----
    appearance_count: dict[str, int] = {}
    for shot in shots:
        for cid in shot.get("characters", []):
            appearance_count[cid] = appearance_count.get(cid, 0) + 1

    lock_required = style.get("consistency_requirements", {}).get("character_anchor_required", True)
    for cid, count in appearance_count.items():
        if count <= 1:
            continue
        ch = characters.get(cid)
        if not ch:
            continue
        anchor = ch.get("consistency", {})
        if lock_required:
            missing = [k for k in ("seed", "reference_image") if not anchor.get(k)]
            if missing:
                v.error(
                    "角色一致性",
                    f"角色 {cid}({ch.get('name')}) 出现在 {count} 个镜头，但缺少一致性锚点: {', '.join(missing)}",
                )
            else:
                v.info(
                    "角色一致性",
                    f"角色 {cid}({ch.get('name')}) 出现 {count} 镜，锚点齐备 "
                    f"(seed={anchor.get('seed')}, ref={anchor.get('reference_image')})",
                )
        if not ch.get("appearance_anchors", {}).get("forbidden"):
            v.warn("角色一致性", f"角色 {cid}({ch.get('name')}) 未设 forbidden（禁止元素），易出现服装/饰品漂移")

    # ---- 校验 4：风格前缀与负向提示词 ----
    if style.get("consistency_requirements", {}).get("style_prefix_required", True):
        if not style.get("art_style"):
            v.error("风格圣经", "style_bible.art_style 缺失，无法生成统一风格前缀")
        if not style.get("palette"):
            v.warn("风格圣经", "style_bible.palette 未定义，色彩一致性无约束")
    if not style.get("negative_prompt"):
        v.warn("风格圣经", "未定义 negative_prompt，AI 易出现写实化、多手指、画面抖动等问题")

    # ---- 校验 5：台词时间轴与镜头时长 ----
    for shot in shots:
        sid = shot.get("id")
        duration = float(shot.get("duration_sec", 0))
        if duration <= 0:
            v.error("镜头时长", f"镜头 {sid} 时长无效: {duration}")
        for line in shot.get("dialogue", []):
            est = estimate_speech_duration(line.get("text", ""))
            start = float(line.get("start_sec", 0))
            end = start + est
            if end > duration + 0.05:
                v.error(
                    "台词时间轴",
                    f"镜头 {sid} 角色 {line.get('character')} 台词超出镜头时长："
                    f"起 {start:.2f}s + 估算 {est:.2f}s = {end:.2f}s > 镜头 {duration:.2f}s",
                )
            if est > 0 and duration > 0 and est > duration * 0.9:
                v.warn("台词时间轴", f"镜头 {sid} 台词几乎占满整镜，建议拆镜或缩短台词")
        # 无台词的镜头给出提示（可能是有意为之）
        if not shot.get("dialogue") and shot.get("shot_size") in ("近景", "特写", "大特写"):
            v.info("台词时间轴", f"镜头 {sid} 为{shot.get('shot_size')}但无台词，确认是有意留白")

    # ---- 校验 6：分幕结构与镜头对齐 ----
    act_structure = project.get("act_structure", [])
    if act_structure:
        declared = [sid for act in act_structure for sid in act.get("shots", [])]
        actual = [s.get("id") for s in shots]
        if declared != actual:
            missing = [s for s in actual if s not in declared]
            extra = [s for s in declared if s not in actual]
            detail = []
            if missing:
                detail.append(f"未归入任何幕: {missing}")
            if extra:
                detail.append(f"幕中声明但不存在: {extra}")
            if not missing and not extra:
                detail.append("顺序不一致（分幕顺序与实际镜头顺序不同）")
            v.error("分幕结构", "分幕结构与实际镜头不匹配 -> " + "; ".join(detail))

    # ---- 校验 7：总时长 ----
    total = sum(float(s.get("duration_sec", 0)) for s in shots)
    target = float(project.get("duration_target_sec", 0))
    if target > 0:
        deviation = abs(total - target) / target
        msg = f"总时长 {total:.1f}s / 目标 {target:.1f}s（偏差 {deviation * 100:.1f}%，共 {len(shots)} 镜）"
        if deviation > 0.25:
            v.warn("总时长", msg + " -> 偏差超过 25%，确认是否符合预期")
        else:
            v.info("总时长", msg)

    # ---- 附加：合规清单提醒 ----
    if not config.get("compliance", {}).get("checklist"):
        v.warn("合规", "未配置 compliance.checklist，版权与内容合规缺少显式检查项")


# ============================================================
# 提示词组装
# ============================================================
def build_style_prefix(style: dict[str, Any]) -> str:
    """把风格圣经压成一段可复用的前缀，保证跨镜头风格一致。"""
    parts = [style.get("art_style", "")]
    palette = style.get("palette", [])
    if palette:
        names = "、".join(p.get("name", "") for p in palette if p.get("name"))
        if names:
            parts.append(f"主色调{names}")
    if style.get("texture"):
        parts.append(style["texture"])
    return "，".join(p for p in parts if p)


def compose_prompt(shot: dict[str, Any], config: dict[str, Any], with_prefix: bool) -> str:
    """把风格前缀与镜头描述拼接，并对重复片段去重。

    为什么要去重：生成模型对提示词是按 token 计权的，同一描述出现两次
    等于暗中加了权重，会让画面被某个元素主导（比如「宣纸纹理」重复
    导致纹理压过主体）。这里按逗号切分做片段级去重。
    """
    base = shot.get("image_prompt") or shot.get("description", "")
    if not with_prefix:
        return base

    prefix = build_style_prefix(config.get("style_bible", {}))
    if not prefix:
        return base

    def segments(text: str) -> list[str]:
        return [s.strip() for s in re.split(r"[，,]", text) if s.strip()]

    prefix_segs = segments(prefix)
    seen = {s.lower() for s in prefix_segs}

    kept: list[str] = []
    for seg in segments(base):
        key = seg.lower()
        if key in seen:
            continue
        # 处理「A + B」这类包含关系：片段被前缀完整包含时也跳过
        if any(key in s.lower() for s in prefix_segs):
            continue
        seen.add(key)
        kept.append(seg)

    return "，".join(prefix_segs + kept)


def write_prompt_files(shot: dict[str, Any], config: dict[str, Any], out_dir: Path,
                       with_prefix: bool, total_offset: float) -> None:
    project = config.get("project", {})
    style = config.get("style_bible", {})
    chars = {c["id"]: c for c in config.get("characters", [])}
    sid = shot["id"]

    char_names = [f"{cid}({chars[cid]['name']})" for cid in shot.get("characters", []) if cid in chars]
    char_line = "、".join(char_names) if char_names else "无"

    header = (
        f"# {sid} 提示词\n"
        f"# 幕次：{shot.get('act', '-')}  |  场景：{shot.get('scene', '-')}\n"
        f"# 景别：{shot.get('shot_size', '-')}  |  运镜：{shot.get('camera_move', '-')}  |  时长：{shot.get('duration_sec')}s\n"
        f"# 画面比例：{project.get('aspect_ratio', '-')}  分辨率：{project.get('resolution', '-')}  帧率：{project.get('fps', '-')}\n"
        f"# 时间轴起点：{format_timestamp(total_offset)}（全片累计）\n"
        f"# 出现角色：{char_line}\n"
        f"# 转场出：{shot.get('transition_out', 'cut')}\n"
    )

    seed_hint = "无角色，可用全局种子"
    if char_names:
        seeds = [str(chars[cid].get("consistency", {}).get("seed")) for cid in shot.get("characters", [])
                 if cid in chars and chars[cid].get("consistency", {}).get("seed")]
        refs = [chars[cid].get("consistency", {}).get("reference_image") for cid in shot.get("characters", [])
                if cid in chars and chars[cid].get("consistency", {}).get("reference_image")]
        seed_hint = f"种子 {'/'.join(seeds)}（角色锁定），参考图 {'、'.join(str(r) for r in refs)}"

    image_txt = (
        f"{header}\n"
        f"[正向提示词]\n{compose_prompt(shot, config, with_prefix)}\n\n"
        f"[负向提示词]\n{style.get('negative_prompt', '')}\n\n"
        f"[生成参数建议]\n"
        f"  目标比例 : {project.get('aspect_ratio', '')}\n"
        f"  分辨率   : {project.get('resolution', '')}\n"
        f"  角色锁定 : {seed_hint}\n"
        f"  风格前缀 : {'已拼接到正向提示词' if with_prefix else '未拼接（--no-style-prefix）'}\n"
        f"  一致性   : {style.get('art_style', '')}\n\n"
        f"[复现记录]（生成后手工填写，这是参数资产的核心）\n"
        f"  生成时间 : \n"
        f"  使用平台 : \n"
        f"  实际种子 : \n"
        f"  采样步数 : \n"
        f"  CFG/权重 : \n"
        f"  备注     : \n"
    )

    video_txt = (
        f"{header}\n"
        f"[首帧图]\n04_shots/{sid}.png\n\n"
        f"[运动提示词]\n{shot.get('video_prompt', '')}\n\n"
        f"[负向提示词]\n{style.get('negative_prompt', '')}\n\n"
        f"[运动约束]\n"
        f"  运动强度 : {style.get('motion_intensity', '低')}\n"
        f"  时长     : {shot.get('duration_sec')}s\n"
        f"  帧率     : {project.get('fps', '')}\n"
        f"  首尾帧   : 建议首尾帧同构图，避免 AI 视频常见的形变漂移\n\n"
        f"[音频设计]\n"
        f"  BGM  : {shot.get('bgm', '-')}\n"
        f"  音效 : {'、'.join(shot.get('sfx', [])) or '无'}\n\n"
        f"[复现记录]\n"
        f"  生成时间 : \n"
        f"  使用平台 : \n"
        f"  实际参数 : \n"
        f"  备注     : \n"
    )

    (out_dir / f"{sid}_image.txt").write_text(image_txt, encoding="utf-8")
    (out_dir / f"{sid}_video.txt").write_text(video_txt, encoding="utf-8")


# ============================================================
# 时间轴工具
# ============================================================
def format_timestamp(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def format_srt_time(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def wrap_subtitle(text: str, max_chars: int, max_lines: int) -> str:
    """按标点与字数折行，避免长句撑出画面。"""
    if len(text) <= max_chars:
        return text
    # 优先在标点处断句
    parts = re.split(r"([，。！？、；：])", text)
    lines: list[str] = []
    current = ""
    for chunk in parts:
        if not chunk:
            continue
        if len(current) + len(chunk) <= max_chars:
            current += chunk
        else:
            if current:
                lines.append(current)
            current = chunk
        if len(lines) == max_lines:
            break
    if current and len(lines) < max_lines:
        lines.append(current)
    return "\n".join(lines[:max_lines])


# ============================================================
# 主流程
# ============================================================
def write_shotlist_md(config: dict[str, Any], out_path: Path) -> None:
    project = config.get("project", {})
    chars = {c["id"]: c for c in config.get("characters", [])}
    shots = config.get("shots", [])
    total = sum(float(s.get("duration_sec", 0)) for s in shots)

    lines = [
        f"# 分镜表 · {project.get('title', '未命名')}",
        "",
        f"- 类型：{project.get('type', '-')}",
        f"- 一句话故事：{project.get('logline', '-')}",
        f"- 目标时长：{project.get('duration_target_sec', '-')}s ｜ 实际合计：{total:.1f}s ｜ 镜头数：{len(shots)}",
        f"- 画面：{project.get('resolution', '-')} @ {project.get('fps', '-')}fps ｜ 比例 {project.get('aspect_ratio', '-')}",
        "",
        "## 角色表",
        "",
        "| ID | 姓名 | 定位 | 一致性锚点 | 配音音色 |",
        "|---|---|---|---|---|",
    ]
    for c in config.get("characters", []):
        cons = c.get("consistency", {})
        anchor = f"seed={cons.get('seed', '-')} / ref={cons.get('reference_image', '-')}"
        voice = c.get("voice", {}).get("tts_voice", "-")
        lines.append(f"| {c['id']} | {c['name']} | {c.get('role', '-')} | {anchor} | {voice} |")

    lines += ["", "## 镜头清单", ""]
    for act in project.get("act_structure", []):
        lines.append(f"### {act.get('act', '')}（情绪曲线：{act.get('emotion_curve', '-')}）")
        lines.append("")
        lines.append("| 镜号 | 场景 | 景别 | 运镜 | 时长 | 角色 | 台词 | 转场 |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for sid in act.get("shots", []):
            shot = next((s for s in shots if s.get("id") == sid), None)
            if not shot:
                lines.append(f"| {sid} | ⚠️ 配置中不存在此镜头 | | | | | | |")
                continue
            names = "、".join(chars[cid]["name"] for cid in shot.get("characters", []) if cid in chars) or "—"
            dlg = " / ".join(f"{d['character']}：「{d['text']}」" for d in shot.get("dialogue", [])) or "—"
            lines.append(
                f"| {sid} | {shot.get('scene', '-')} | {shot.get('shot_size', '-')} | "
                f"{shot.get('camera_move', '-')} | {shot.get('duration_sec')}s | {names} | {dlg} | "
                f"{shot.get('transition_out', 'cut')} |"
            )
        lines.append("")

    lines += ["## 镜头描述", ""]
    for shot in shots:
        lines.append(f"**{shot['id']}**（{shot.get('scene', '-')}，{shot.get('shot_size', '-')}，{shot.get('duration_sec')}s）")
        lines.append("")
        lines.append(f"- 画面：{shot.get('description', '-')}")
        lines.append(f"- 首帧提示词：`02_storyboard/prompts/{shot['id']}_image.txt`")
        lines.append(f"- 运动提示词：`02_storyboard/prompts/{shot['id']}_video.txt`")
        if shot.get("sfx"):
            lines.append(f"- 音效：{'、'.join(shot['sfx'])}")
        if shot.get("bgm"):
            lines.append(f"- BGM：{shot['bgm']}")
        if shot.get("post_overlay"):
            ov = shot["post_overlay"]
            lines.append(f"- 后期叠加：{ov.get('type')}「{ov.get('text', '')}」于 {ov.get('start_sec')}s 起，持续 {ov.get('duration_sec')}s")
        lines.append("")

    out_path.write_text("\n".join(lines), encoding="utf-8")


def write_shots_csv(config: dict[str, Any], out_path: Path) -> None:
    shots = config.get("shots", [])
    with out_path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow([
            "镜号", "幕次", "场景", "景别", "运镜", "时长秒",
            "角色", "首帧图", "生成视频", "台词", "音效", "BGM", "转场",
            "素材状态",
        ])
        for shot in shots:
            sid = shot["id"]
            dlg = " | ".join(f"{d['character']}:{d['text']}" for d in shot.get("dialogue", []))
            writer.writerow([
                sid,
                shot.get("act", ""),
                shot.get("scene", ""),
                shot.get("shot_size", ""),
                shot.get("camera_move", ""),
                shot.get("duration_sec", ""),
                "/".join(shot.get("characters", [])),
                f"04_shots/{sid}.png",
                f"04_shots/{sid}.mp4",
                dlg,
                "/".join(shot.get("sfx", [])),
                shot.get("bgm", ""),
                shot.get("transition_out", "cut"),
                "待生成",
            ])


def write_voiceover_csv(config: dict[str, Any], out_path: Path, offsets: dict[str, float]) -> None:
    chars = {c["id"]: c for c in config.get("characters", [])}
    rows = []
    for shot in config.get("shots", []):
        base = offsets.get(shot["id"], 0.0)
        for line in shot.get("dialogue", []):
            cid = line.get("character", "")
            ch = chars.get(cid, {})
            voice = ch.get("voice", {})
            start = base + float(line.get("start_sec", 0))
            est = estimate_speech_duration(line.get("text", ""))
            rows.append([
                shot["id"], cid, ch.get("name", ""),
                line.get("text", ""), line.get("emotion", ""),
                f"{start:.2f}", f"{start + est:.2f}", f"{est:.2f}",
                voice.get("tts_voice", ""), voice.get("rate", ""), voice.get("pitch", ""),
                f"05_audio/voice/{shot['id']}_{cid}.mp3",
            ])
    with out_path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow([
            "镜号", "角色ID", "角色名", "台词", "情感", "全局起始秒", "全局结束秒",
            "估算时长秒", "TTS音色", "语速", "音调", "输出文件",
        ])
        writer.writerows(rows)
    return rows  # type: ignore[return-value]


def write_srt(config: dict[str, Any], out_path: Path, offsets: dict[str, float]) -> int:
    sub = config.get("subtitle", {})
    max_chars = int(sub.get("max_chars_per_line", 18))
    max_lines = int(sub.get("max_lines", 2))
    min_dur = float(sub.get("min_duration_sec", 1.0))

    entries: list[tuple[float, float, str]] = []
    for shot in config.get("shots", []):
        base = offsets.get(shot["id"], 0.0)
        shot_end = base + float(shot.get("duration_sec", 0))
        for line in shot.get("dialogue", []):
            start = base + float(line.get("start_sec", 0))
            est = estimate_speech_duration(line.get("text", ""))
            end = start + max(est, min_dur)
            # 字幕不得溢出本镜时长
            end = min(end, shot_end)
            if end <= start:
                end = start + min_dur
            entries.append((start, end, line.get("text", "")))

    entries.sort(key=lambda e: e[0])

    blocks = []
    for idx, (start, end, text) in enumerate(entries, start=1):
        blocks.append(
            f"{idx}\n"
            f"{format_srt_time(start)} --> {format_srt_time(end)}\n"
            f"{wrap_subtitle(text, max_chars, max_lines)}\n"
        )
    out_path.write_text("\n".join(blocks), encoding="utf-8")
    return len(entries)


def main() -> int:
    parser = argparse.ArgumentParser(description="分镜生成器：配置 -> 分镜表 / 提示词 / 配音稿 / 字幕")
    parser.add_argument("--config", required=True, help="项目配置文件（.json / .yaml）")
    parser.add_argument("--outdir", default=str(ROOT), help="项目根目录，默认仓库根")
    parser.add_argument("--strict", action="store_true", help="有警告也视为失败")
    parser.add_argument("--no-style-prefix", action="store_true", help="不自动拼接风格前缀")
    parser.add_argument("--json-summary", action="store_true", help="额外输出 JSON 摘要")
    args = parser.parse_args()

    root = Path(args.outdir).resolve()
    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = (root / config_path).resolve()

    try:
        config = load_config(config_path)
    except Exception as exc:  # noqa: BLE001
        print(f"[错误] 读取配置失败: {exc}", file=sys.stderr)
        return 1

    with_prefix = not args.no_style_prefix

    # ---- 校验 ----
    v = Validator()
    validate(config, v)

    # ---- 时间轴 ----
    offsets: dict[str, float] = {}
    cursor = 0.0
    for shot in config.get("shots", []):
        offsets[shot["id"]] = cursor
        cursor += float(shot.get("duration_sec", 0))
    total_duration = cursor

    # ---- 输出目录 ----
    storyboard_dir = root / "02_storyboard"
    prompts_dir = storyboard_dir / "prompts"
    audio_dir = root / "05_audio"
    for d in (storyboard_dir, prompts_dir, audio_dir, root / "04_shots", root / "06_final"):
        d.mkdir(parents=True, exist_ok=True)

    # ---- 生成产物 ----
    write_shotlist_md(config, storyboard_dir / "shotlist.md")
    write_shots_csv(config, storyboard_dir / "shots.csv")
    for shot in config.get("shots", []):
        write_prompt_files(shot, config, prompts_dir, with_prefix, offsets[shot["id"]])
    vo_rows = write_voiceover_csv(config, audio_dir / "voiceover.csv", offsets)
    srt_count = write_srt(config, audio_dir / "subtitles.srt", offsets)

    # ---- 报告 ----
    project = config.get("project", {})
    line = "=" * 72
    print(line)
    print(f" 分镜生成完成 · {project.get('title', '未命名')}")
    print(line)
    print(f" 镜头数    : {len(config.get('shots', []))}")
    print(f" 总时长    : {total_duration:.1f}s / 目标 {project.get('duration_target_sec', '-')}s")
    print(f" 角色数    : {len(config.get('characters', []))}")
    print(f" 台词条数  : {len(vo_rows)}")
    print(f" 字幕条数  : {srt_count}")
    print(f" 风格前缀  : {'已拼接' if with_prefix else '未拼接'}")
    print("-" * 72)
    print(" 产出文件：")
    for rel in [
        "02_storyboard/shotlist.md",
        "02_storyboard/shots.csv",
        f"02_storyboard/prompts/（{len(config.get('shots', []))} 镜 × 2 个提示词文件）",
        "05_audio/voiceover.csv",
        "05_audio/subtitles.srt",
    ]:
        print(f"   {rel}")
    print("-" * 72)

    if v.issues:
        print(" 校验结果：")
        icon = {"error": "[错误]", "warn": "[警告]", "info": "[信息]"}
        for issue in v.issues:
            print(f"   {icon[issue.level]} [{issue.scope}] {issue.message}")
    else:
        print(" 校验结果：全部通过，无任何问题")
    print(line)

    failed = bool(v.errors) or (args.strict and bool(v.warns))
    print(f" 结论：{'校验未通过 -> 先修复问题再开始生成素材' if failed else '校验通过 -> 可以开始生成素材'}")
    print(line)

    if args.json_summary:
        summary = {
            "title": project.get("title"),
            "shots": len(config.get("shots", [])),
            "total_duration_sec": round(total_duration, 2),
            "dialogue_lines": len(vo_rows),
            "subtitle_entries": srt_count,
            "issues": [{"level": i.level, "scope": i.scope, "message": i.message} for i in v.issues],
            "passed": not failed,
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2))

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
