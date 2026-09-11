#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AI 国漫短片工作室环境自检
================================================================
检查四类东西，任何一项不合格都会导致「脚本不报错但出不了片」：

    1. FFmpeg / ffprobe     合成的地基
    2. 中文字体             缺了字幕会渲染成方框，且 ffmpeg 不报错
    3. Python 依赖          剪辑、音频、TTS、字幕
    4. 目录结构与流水线     分镜生成链路能否跑通（内置冒烟测试）

用法：
    python scripts/test_check.py
    python scripts/test_check.py --json

退出码：
    0  全部就绪
    1  有必装项缺失，环境未就绪
================================================================
"""

from __future__ import annotations

import argparse
import importlib
import json
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

# ============================================================
# Python 依赖：(import 名, 用途, 是否必装, 修复命令)
# ============================================================
DEPENDENCIES: list[dict[str, Any]] = [
    {"import": "imageio_ffmpeg", "purpose": "提供 ffmpeg 二进制", "core": True,
     "fix": "pip install 'imageio-ffmpeg>=0.5.1'"},
    {"import": "moviepy", "purpose": "剪辑拼接", "core": True,
     "fix": "pip install 'moviepy>=1.0.3'"},
    {"import": "PIL", "purpose": "图像处理（水印/拼图/尺寸统一）", "core": True,
     "fix": "pip install 'Pillow>=10.3'"},
    {"import": "numpy", "purpose": "数组运算（moviepy 依赖）", "core": True,
     "fix": "pip install 'numpy>=1.26,<3'"},
    {"import": "pydub", "purpose": "音频拼接与增益", "core": True,
     "fix": "pip install 'pydub>=0.25.1'"},
    {"import": "edge_tts", "purpose": "免费中文配音", "core": True,
     "fix": "pip install 'edge-tts>=6.1.10'"},
    {"import": "yaml", "purpose": "读 YAML 配置", "core": False,
     "fix": "pip install 'pyyaml>=6.0'"},
    {"import": "tqdm", "purpose": "批量进度条", "core": False,
     "fix": "pip install 'tqdm>=4.66'"},
    {"import": "rich", "purpose": "终端输出美化", "core": False,
     "fix": "pip install 'rich>=13.7'"},
    {"import": "faster_whisper", "purpose": "字幕时间轴对齐（可选）", "core": False,
     "fix": "pip install 'faster-whisper>=1.0.3'"},
    {"import": "torch", "purpose": "本地扩散模型（仅本地生成需要）", "core": False,
     "fix": "见 requirements-gpu.txt（按 CUDA 版本从官方源安装）"},
    {"import": "diffusers", "purpose": "本地出图/出视频（仅本地生成需要）", "core": False,
     "fix": "见 requirements-gpu.txt"},
    {"import": "websocket", "purpose": "驱动 ComfyUI（仅本地生图生视频需要）", "core": False,
     "fix": "pip install 'websocket-client>=1.7'"},
    {"import": "requests", "purpose": "调用云端生成 API（可灵/即梦等）", "core": False,
     "fix": "pip install 'requests>=2.32'"},
    {"import": "cv2", "purpose": "人脸关键点/分镜预检（后期增强）", "core": False,
     "fix": "pip install 'opencv-python>=4.9'"},
    {"import": "av", "purpose": "音视频容器读写（BGM/SFX 生成）", "core": False,
     "fix": "pip install 'av>=12.0'"},
]

# ============================================================
# 必需的目录结构
# ============================================================
REQUIRED_DIRS = [
    "01_script", "02_storyboard", "02_storyboard/prompts",
    "03_character", "04_shots", "05_audio", "05_audio/voice",
    "05_audio/bgm", "05_audio/sfx", "06_final", "assets", "assets/fonts",
]

# 中文字体候选（顺序即优先级）
FONT_CANDIDATES = [
    "Noto Sans CJK SC", "Source Han Sans SC", "Microsoft YaHei",
    "SimHei", "PingFang SC", "WenQuanYi Zen Hei", "SimSun",
]


# ============================================================
# 检查项
# ============================================================
def check_python_deps() -> list[dict[str, Any]]:
    results = []
    for spec in DEPENDENCIES:
        try:
            mod = importlib.import_module(spec["import"])
            version = getattr(mod, "__version__", "unknown")
            ok, error = True, None
        except Exception as exc:  # noqa: BLE001
            version, ok, error = None, False, f"{type(exc).__name__}: {exc}"
        results.append({
            "name": spec["import"],
            "purpose": spec["purpose"],
            "core": spec["core"],
            "installed": ok,
            "version": version,
            "error": error,
            "fix": spec["fix"] if not ok else None,
        })
    return results


def check_ffmpeg() -> dict[str, Any]:
    exe = shutil.which("ffmpeg")
    source = "系统 PATH"
    if not exe:
        try:
            import imageio_ffmpeg  # type: ignore

            exe = imageio_ffmpeg.get_ffmpeg_exe()
            source = "imageio-ffmpeg 内置"
        except Exception:  # noqa: BLE001
            pass

    result: dict[str, Any] = {"available": False, "path": None, "version": None,
                              "source": source, "ffprobe": False}
    if not exe:
        return result

    result["path"] = exe
    try:
        out = subprocess.run([exe, "-version"], capture_output=True, text=True, timeout=15)
        if out.stdout:
            result["version"] = out.stdout.splitlines()[0]
            result["available"] = True
    except Exception as exc:  # noqa: BLE001
        result["version"] = f"读取失败: {exc}"

    result["ffprobe"] = shutil.which("ffprobe") is not None
    return result


def check_fonts() -> dict[str, Any]:
    """检测中文字体。这是最容易漏、后果最隐蔽的一项。"""
    fc_list = shutil.which("fc-list")
    if fc_list:
        try:
            out = subprocess.run([fc_list, ":lang=zh", "family"],
                                 capture_output=True, text=True, timeout=15)
            families = sorted({f.strip() for f in out.stdout.splitlines() if f.strip()})
            hits = [c for c in FONT_CANDIDATES if any(c.lower() in f.lower() for f in families)]
            return {"method": "fontconfig", "count": len(families),
                    "available": bool(families), "matched": hits,
                    "families": families[:12], "recommended": hits[0] if hits else None}
        except Exception:  # noqa: BLE001
            pass

    if sys.platform.startswith("win"):
        fonts_dir = Path("C:/Windows/Fonts")
        patterns = {
            "Microsoft YaHei": ["msyh"], "SimHei": ["simhei"], "SimSun": ["simsun"],
            "Noto Sans CJK SC": ["NotoSansCJK", "NotoSansSC"],
            "Source Han Sans SC": ["SourceHanSans"], "PingFang SC": ["PingFang"],
            "WenQuanYi Zen Hei": ["wqy-zenhei"],
        }
        hits = []
        if fonts_dir.exists():
            names = [f.name for f in fonts_dir.iterdir()]
            for family, keys in patterns.items():
                if any(n.startswith(k) for n in names for k in keys):
                    hits.append(family)
        return {"method": "Windows 字体目录", "count": len(hits),
                "available": bool(hits), "matched": hits,
                "families": hits, "recommended": hits[0] if hits else None}

    return {"method": "无法检测", "count": 0, "available": False,
            "matched": [], "families": [], "recommended": None}


def check_dirs() -> dict[str, Any]:
    missing = [d for d in REQUIRED_DIRS if not (ROOT / d).exists()]
    return {"missing": missing, "total": len(REQUIRED_DIRS),
            "ok": len(REQUIRED_DIRS) - len(missing)}


def check_pipeline() -> dict[str, Any]:
    """内置冒烟测试：跑一遍分镜生成链路（零第三方依赖）。"""
    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        import build_shotlist  # type: ignore
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "detail": f"无法导入 build_shotlist: {exc}"}

    cfg = ROOT / "configs" / "demo_short.json"
    if not cfg.exists():
        return {"ok": False, "detail": "configs/demo_short.json 不存在"}

    try:
        config = build_shotlist.load_config(cfg)
        validator = build_shotlist.Validator()
        build_shotlist.validate(config, validator)
        shots = config.get("shots", [])
        # 时间轴与字幕折行也要能跑通
        total = sum(float(s.get("duration_sec", 0)) for s in shots)
        wrapped = build_shotlist.wrap_subtitle("伞断了三根骨，撑不起来了，可我还在等。", 16, 2)
        return {
            "ok": not validator.errors,
            "shots": len(shots),
            "total_duration": round(total, 2),
            "errors": len(validator.errors),
            "warns": len(validator.warns),
            "subtitle_wrap_ok": "\n" in wrapped or len(wrapped) <= 16,
            "detail": "分镜校验、时间轴、字幕折行链路全部跑通"
                      if not validator.errors else f"{len(validator.errors)} 项校验错误",
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "detail": f"执行异常 {type(exc).__name__}: {exc}"}


# ============================================================
# 主流程
# ============================================================
def build_report() -> dict[str, Any]:
    deps = check_python_deps()
    ffmpeg = check_ffmpeg()
    fonts = check_fonts()
    dirs = check_dirs()
    pipeline = check_pipeline()

    core_missing = [d for d in deps if d["core"] and not d["installed"]]
    ok = ffmpeg["available"] and fonts["available"] and not core_missing and pipeline["ok"]

    return {
        "python": sys.version.split()[0],
        "platform": platform.system().lower(),
        "ffmpeg": ffmpeg,
        "fonts": fonts,
        "dependencies": deps,
        "directories": dirs,
        "pipeline": pipeline,
        "summary": {
            "core_missing": [d["name"] for d in core_missing],
            "optional_installed": sum(1 for d in deps if not d["core"] and d["installed"]),
            "optional_total": sum(1 for d in deps if not d["core"]),
            "ready": ok,
        },
    }


def render(report: dict[str, Any]) -> None:
    line = "=" * 72
    print(line)
    print(" AI 国漫短片工作室 · 环境自检  (ai-guoman-studio)")
    print(f" Python {report['python']}  |  平台 {report['platform']}")
    print(line)

    # ---- FFmpeg ----
    ff = report["ffmpeg"]
    if ff["available"]:
        print(f" [ OK  ] FFmpeg   {ff['version']}")
        print(f"          来源：{ff['source']}")
        print(f"          ffprobe：{'可用' if ff['ffprobe'] else '不可用（部分平台导出功能受限）'}")
    else:
        print(" [缺失] FFmpeg   未找到 —— 没有它无法合成视频")
        print("          修复：pip install imageio-ffmpeg")
        print("                或系统安装 https://ffmpeg.org/download.html")

    # ---- 中文字体 ----
    fonts = report["fonts"]
    print("-" * 72)
    if fonts["available"]:
        print(f" [ OK  ] 中文字体  检测到 {fonts['count']} 个（{fonts['method']}）")
        print(f"          可用族：{'、'.join(fonts['matched'][:6])}")
        print(f"          建议用：{fonts['recommended']}")
    else:
        print(" [缺失] 中文字体  未检测到任何中文字体包")
        print("          ⚠️ 后果：字幕与片名会渲染成方框，且 ffmpeg 不会报错")
        print("          修复：Linux: apt install fonts-noto-cjk fonts-wqy-zenhei")
        print("                Windows: 系统自带微软雅黑，请检查字体目录权限")

    # ---- Python 依赖 ----
    print("-" * 72)
    width = max(len(d["name"]) for d in report["dependencies"])
    for dep in report["dependencies"]:
        if dep["installed"]:
            tag = "[ OK  ]"
        else:
            tag = "[缺失]" if dep["core"] else "[可选]"
        ver = dep["version"] if dep["installed"] else "-"
        print(f" {tag} {dep['name']:<{width}}  {ver:<24} {dep['purpose']}")

    missing = [d for d in report["dependencies"] if d["core"] and not d["installed"]]
    if missing:
        print("-" * 72)
        print(" 必装依赖缺失 —— 复制以下命令修复：")
        for dep in missing:
            print(f"   {dep['name']:<{width}} ->  {dep['fix']}")

    # ---- 目录结构 ----
    print("-" * 72)
    d = report["directories"]
    if d["missing"]:
        print(f" [警告] 目录结构  缺失 {len(d['missing'])}/{d['total']} 个目录：")
        for m in d["missing"]:
            print(f"          {m}/")
        print("          修复：python scripts/init_dirs.py  （或用 mkdir -p 手工创建）")
    else:
        print(f" [ OK  ] 目录结构  {d['ok']}/{d['total']} 个目录齐备")

    # ---- 流水线冒烟 ----
    p = report["pipeline"]
    flag = "[ OK  ]" if p["ok"] else "[失败]"
    print(f" {flag} 流水线    {p.get('detail', '')}")
    if p.get("shots"):
        print(f"          演示项目：{p['shots']} 镜 / {p['total_duration']}s"
              f" / 校验错误 {p['errors']} 项 / 警告 {p['warns']} 项")

    # ---- 结论 ----
    s = report["summary"]
    print(line)
    verdict = "环境就绪，可以开始制作" if s["ready"] else "环境未就绪，先修复上面标记为 [缺失] 的项"
    print(f" 结论：{verdict}"
          f"  |  可选依赖 {s['optional_installed']}/{s['optional_total']} 已装")
    print(line)
    print(" 提醒：本脚本只保证「工具链跑得通」，不保证「作品好」与「素材合规」。")
    print("       角色一致性、字幕准确性、版权与内容合规均须人工核验。")
    print(line)


def main() -> int:
    parser = argparse.ArgumentParser(description="AI 国漫短片工作室环境自检")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args()

    report = build_report()
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        render(report)
    return 0 if report["summary"]["ready"] else 1


if __name__ == "__main__":
    sys.exit(main())
