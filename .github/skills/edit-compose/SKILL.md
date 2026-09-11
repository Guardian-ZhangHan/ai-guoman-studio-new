---
name: edit-compose
description: 剪辑与成片合成规范。当任务涉及用 FFmpeg 拼接镜头、统一分辨率与帧率、混合配音与背景音乐、烧录字幕、调色、叠加片名、响度归一与导出平台成片时使用。
---

# 剪辑与成片合成（Edit & Compose）

## 何时使用

- 把分镜素材拼接成成片
- 处理不同平台导出素材的分辨率/帧率不一致
- 混合配音、BGM、音效
- 烧录字幕、叠加片名
- 导出符合平台要求的成片

## 一、素材预处理（先统一，再拼接）

**不同 AI 平台导出的素材几乎不可能尺寸一致。** 直接拼接会得到花屏或变形。

```bash
# 统一方案：等比缩放 + 黑边填充（不裁切，不丢画面）
ffmpeg -i raw/S001.mp4 \
  -vf "scale=1920:1080:force_original_aspect_ratio=decrease,\
pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=black,fps=24,format=yuv420p" \
  -c:v libx264 -crf 18 -preset slow -an 04_shots/S001.mp4
```

**为什么用 pad 而不是 crop**：
crop 会切掉画面边缘（可能切掉角色头部或关键构图），
pad 只加黑边，信息不丢失。若黑边难看，后续统一裁切或调色掩盖。

**帧率必须统一。** 混用 24/25/30fps 会造成音画不同步与卡顿。
本项目统一 **24 fps**（电影感）或 **30 fps**（网络平台更顺滑）。

## 二、拼接（concat）

```bash
# 1. 生成清单文件（路径必须正确，Windows 下注意斜杠）
cat > 06_final/concat_list.txt <<'EOF'
file 'C:/project/04_shots/S001.mp4'
file 'C:/project/04_shots/S002.mp4'
EOF

# 2. 拼接（-safe 0 允许绝对路径）
ffmpeg -y -f concat -safe 0 -i 06_final/concat_list.txt -c copy 06_final/merged.mp4
```

**注意**：`-c copy` 只在所有素材编码参数完全一致时可用。
素材来自多个平台时，**必须重新编码**（去掉 `-c copy`），否则会出现：
- 时间戳错乱，音画不同步
- 部分片段时间轴异常
- 某些播放器无法解码

本仓库 `compose_video.py` 默认走**重编码**路径，牺牲速度换稳定性。

## 三、音频混合

### 三层结构

```
配音轨  ← 主体，-16 LUFS
BGM 轨  ← 衬托，侧链闪避（说话时自动降 8dB）
音效轨  ← 点缀（脚步、雨声、竹篙入水）
```

### 时间轴对齐（adelay）

```bash
# 把配音延迟到全局时间轴的 9500ms 处（S002 起点 7.0s + 镜内偏移 2.5s）
ffmpeg -i voice/S002_C02.mp3 \
  -af "aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,\
adelay=9500|9500,volume=1.0" out.wav
```
`adelay=A|B` 的 A、B 分别对应左右声道，**两个值都要写**。

### BGM 自动闪避（sidechaincompress）

```bash
[bgmraw][voicemix]sidechaincompress=threshold=0.05:ratio=6:attack=20:release=350:makeup=1[bgmduck]
```

| 参数 | 值 | 作用 |
|---|---|---|
| `threshold` | 0.05 | 触发闪避的人声阈值，越低越敏感 |
| `ratio` | 6 | 压缩比，越大压得越狠 |
| `attack` | 20 ms | 响应速度，太快会有「抽气感」 |
| `release` | 350 ms | 恢复速度，太慢音乐会「回不来」 |

**顺序很重要**：`[主输入][侧链输入]sidechaincompress`
主输入是 BGM，侧链输入是配音。反过来会把音乐压到人声上。

### 响度归一（母版必做）

```bash
ffmpeg -i mixed.wav -af "loudnorm=I=-14:TP=-1.0:LRA=11" -ar 48000 master.wav
```

| 平台 | 目标响度 |
|---|---|
| 抖音 / 快手 / 视频号 | -14 LUFS |
| B站 / YouTube | -14 LUFS |
| 影院 / 展映 | -20 ~ -24 LUFS |
| 播客 / 音频平台 | -16 LUFS |

`TP=-1.0` 是真实峰值上限，防止转码后削波。

## 四、字幕烧录

```bash
ffmpeg -i merged.mp4 \
  -vf "subtitles='05_audio/subtitles.srt':force_style='FontName=Microsoft YaHei,FontSize=26,PrimaryColour=&HFFFFFF,OutlineColour=&H1B2A33,Outline=2,Shadow=1,MarginV=48,Alignment=2,BorderStyle=1'" \
  -c:v libx264 -crf 18 -c:a copy out.mp4
```

**Windows 路径转义**：`subtitles` 滤镜里的盘符冒号必须转义为 `C\:`，
否则 ffmpeg 会把冒号当参数分隔符。本仓库脚本已自动处理。

**字体名必须存在**，否则字幕渲染成方框且不报错（见 tts-subtitle 技能）。

## 五、片名与文字叠加（drawtext）

```bash
ffmpeg -i merged.mp4 \
  -vf "drawtext=fontfile='assets/fonts/title.otf':text='青竹渡':\
fontsize=97:fontcolor=white@0.95:borderw=3:bordercolor=black@0.55:\
x=(w-text_w)/2:y=(h-text_h)/2:enable='between(t,7,9)'" out.mp4
```

- 中文文本中的 `:` `/` `'` 需转义
- 字体文件缺失时退回 `font='字体族名'`（需 ffmpeg 启用 fontconfig）
- `enable='between(t,start,end)'` 控制显示时间窗口
- 加 `borderw` 描边，避免文字糊在浅色背景上

## 六、导出参数

```bash
ffmpeg -i master.wav -i merged.mp4 \
  -map "[vout]" -map "[audioout]" \
  -c:v libx264 -crf 18 -preset slow -pix_fmt yuv420p \
  -c:a aac -b:a 192k -ar 48000 \
  -movflags +faststart \
  06_final/final.mp4
```

| 参数 | 值 | 说明 |
|---|---|---|
| `-crf` | 18 | 视觉无损，太大文件大，超过 23 画质明显下降 |
| `-preset` | slow | 压缩效率高，耗时换体积 |
| `-pix_fmt` | yuv420p | **必须**，否则部分播放器黑屏 |
| `-movflags +faststart` | — | 网络播放秒开（moov 前移） |

**平台二次压制提示**：上传到短视频平台会被重新压制，
源文件建议用较高码率（CRF 18）留出余量。

## 七、合成后的必做检查

```
□ 全片看一遍（不要只看第一分钟）
□ 音画同步：说话时嘴部/表演动作是否对得上
□ 字幕：有无错别字、多音字、超出画面
□ 配音：语气是否贴合、有无读错
□ 角色一致性：逐镜核对（见 character-consistency 技能）
□ 转场：有无突兀硬切或残留黑帧
□ 首尾：开头是否抓人，结尾是否收得住
□ 黑帧/卡帧：逐帧抽查拼接点
□ 平台要求：时长、比例、响度、文件大小
```

**最常见的事故：拼接点出现黑帧。** 原因是素材首尾有编码残留帧，
预处理时统一加 `-vsync cfr` 或裁剪首尾 1–2 帧。

## 常见错误清单

- ❌ 不同尺寸素材直接拼接，导致花屏/变形
- ❌ 混用帧率，音画不同步
- ❌ 用 `-c copy` 拼接跨平台素材，时间戳错乱
- ❌ `adelay` 只写一个值，只有单声道生效
- ❌ sidechain 主输入与侧链输入写反
- ❌ 不做响度归一，不同设备上音量差异巨大
- ❌ 忘了 `-pix_fmt yuv420p`，部分播放器黑屏
- ❌ 字幕无描边，压在浅色画面看不见
- ❌ Windows 路径冒号未转义，滤镜报错
- ❌ 字体缺失导致字幕成方框
- ❌ 不检查拼接点，成片里出现黑帧
- ❌ 只看前 1 分钟就交付

## 验收标准

- [ ] 所有素材已统一分辨率、帧率、像素格式
- [ ] 拼接后逐帧抽查了拼接点，无黑帧
- [ ] 配音时间轴与实际画面对齐
- [ ] BGM 有人声时自动闪避
- [ ] 母版响度符合目标平台要求
- [ ] 字幕字体已探测存在，有描边，位置不被遮挡
- [ ] 导出使用 yuv420p + faststart
- [ ] 全片完整看过一遍，逐项勾完检查清单
