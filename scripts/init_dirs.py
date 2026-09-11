#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
初始化短片工作室目录结构
================================================================
创建标准制作目录，并放入 .gitkeep 占位与各目录的用途说明。
可重复执行（幂等）。

用法：
    python scripts/init_dirs.py
    python scripts/init_dirs.py --dry-run
================================================================
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# 目录 -> 用途说明
DIRS: dict[str, str] = {
    "01_script": "剧本、大纲、人物小传、台词终稿。台词改动必须同步到 02_storyboard。",
    "02_storyboard": "分镜表与提示词（由 scripts/build_shotlist.py 生成，不要手改生成物）。",
    "02_storyboard/prompts": "每镜的文生图 / 图生视频提示词，可直接粘贴到任意生成平台。",
    "03_character": "角色设定表、一致性参考图、LoRA 文件（LoRA 体积大，已在 .gitignore 排除）。",
    "03_character/loras": "角色 LoRA 权重文件。不入库，用网盘或对象存储交换。",
    "04_shots": "镜头素材。命名严格遵循 S001.mp4 / S001.png（镜号与分镜表一致）。",
    "05_audio": "配音、背景音乐、音效、字幕。",
    "05_audio/voice": "配音文件，命名 S001_C01.mp3（镜号_角色ID.mp3），脚本按此名自动对齐时间轴。",
    "05_audio/bgm": "背景音乐。必须为已授权曲库或自有版权音乐。",
    "05_audio/sfx": "音效素材。同样需注意授权。",
    "06_final": "成片输出目录，含 concat 清单与中间产物。",
    "assets": "字体、LUT 调色文件、水印、片头片尾模板。",
    "assets/fonts": "字体文件。片名卡与字幕依赖它；缺中文字体会渲染成方框。",
}

GITIGNORE_EXTRA = """# 素材与成片（体积大，不入库）
04_shots/*
!04_shots/.gitkeep
06_final/*
!06_final/.gitkeep
05_audio/voice/*
!05_audio/voice/.gitkeep
05_audio/bgm/*
!05_audio/bgm/.gitkeep
03_character/loras/*
!03_character/loras/.gitkeep
assets/fonts/*
!assets/fonts/.gitkeep
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="初始化短片工作室目录结构")
    parser.add_argument("--dry-run", action="store_true", help="只显示将创建的内容")
    args = parser.parse_args()

    created_dirs, created_files, existed = 0, 0, 0

    for rel, purpose in DIRS.items():
        path = ROOT / rel
        if path.exists():
            existed += 1
            continue
        if args.dry_run:
            print(f" [将创建] {rel}/")
            created_dirs += 1
            continue
        path.mkdir(parents=True, exist_ok=True)
        readme = path / "_README.txt"
        readme.write_text(
            f"目录：{rel}\n用途：{purpose}\n\n由 scripts/init_dirs.py 生成。\n",
            encoding="utf-8",
        )
        (path / ".gitkeep").touch()
        created_dirs += 1
        created_files += 2
        print(f" [已创建] {rel}/")

    if not args.dry_run and not (ROOT / ".gitignore").exists():
        (ROOT / ".gitignore").write_text(GITIGNORE_EXTRA, encoding="utf-8")
        created_files += 1
        print(" [已创建] .gitignore")

    line = "=" * 60
    print(line)
    if args.dry_run:
        print(f" 预演完成：将创建 {created_dirs} 个目录，已存在 {existed} 个")
    else:
        print(f" 完成：新建 {created_dirs} 个目录（含 {created_files} 个占位文件），"
              f"已存在 {existed} 个")
    print(line)
    print(" 下一步：python scripts/test_check.py   检查环境是否就绪")
    print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
