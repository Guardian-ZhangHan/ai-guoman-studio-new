---
name: bgm-sfx-gen
description: 配乐与音效技能 —— 本地用 audiocraft（MusicGen）生成 BGM、用 demucs 分离人声/伴奏做垫乐闪避；或用 Suno/Udio 等云端 API。把音频落到 05_audio/bgm、05_audio/sfx，并接入 compose_video 的 --bgm 与闪避逻辑。当短片需要自带版权音乐、不能用水货商业歌时使用。
---

# 配乐与音效（BGM / SFX）

## 一、为什么不能随便用商业歌
版权红线（见 `historical-compliance`）：BGM 必须用**已授权曲库 / 自有版权 / AI 生成可商用**的。
商业歌曲直接套 = 侵权下架。

## 二、本地生成（audiocraft / MusicGen）
```bash
python -m audiocraft.models.musicgen \
  --prompt "紧张的军事行进弦乐，低鼓，压抑" \
  --out 05_audio/bgm/S0xx_bgm.wav
```
- 按分幕情绪给 prompt（紧张/悲壮/希望）
- 时长对齐镜头或分幕

## 三、人声/伴奏分离（demucs，做闪避）
垫乐闪避（ducking）需要干净伴奏轨：
```bash
python -m demucs -n htdemucs 05_audio/bgm/S0xx_bgm.wav \
  -o 05_audio/bgm/stems/        # 分出 vocals / drums / bass / other
```
- `compose_video.py` 用 `sidechaincompress` 让人声起时垫乐自动压低

## 四、云端（无显卡）
- Suno / Udio API 生成 BGM；音效用自有库或 CC0 音效包
- 同样落盘并标注来源与许可

## 五、SFX 清单（国漫常用）
脚步、兵器碰撞、风声、爆炸、心跳、环境底噪 —— 按镜头 `sfx` 字段落 `05_audio/sfx/`

## 验收
- [ ] BGM 来源可商用（AI生成/授权/自有），非商业歌
- [ ] 垫乐已做闪避（人声起处不抢戏）
- [ ] SFX 与画面动作同步
- [ ] 全部音频命名对齐分镜/分幕
