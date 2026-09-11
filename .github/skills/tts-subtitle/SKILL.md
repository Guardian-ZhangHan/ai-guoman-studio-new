---
name: tts-subtitle
description: 中文配音与字幕制作规范。当任务涉及用 edge-tts 生成配音、选择中文音色、调整语速音调、字幕时间轴对齐、SRT 生成与折行、字幕样式设置与烧录时使用。
---

# 中文配音与字幕（TTS & Subtitle）

## 何时使用

- 生成角色配音
- 为台词选择合适的中文音色
- 生成/校对字幕时间轴
- 设置字幕样式并烧录

## 一、配音（TTS）

### 免费方案：edge-tts（推荐起步）

微软 Edge 神经语音，**免费、无需 API Key、中文音色质量高**。

```python
import asyncio
from pathlib import Path
import edge_tts

async def synth(text: str, voice: str, out: Path,
                rate: str = "+0%", pitch: str = "+0Hz", volume: str = "+0%") -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    await edge_tts.Communicate(
        text=text, voice=voice, rate=rate, pitch=pitch, volume=volume,
    ).save(str(out))

# 用法
asyncio.run(synth(
    text="伞撑不起来，可以不走。",
    voice="zh-CN-YunxiNeural",
    out=Path("05_audio/voice/S005_C01.mp3"),
    rate="-5%", pitch="-2Hz",
))
```

### 中文音色选择表

| 音色 | 性别 | 气质 | 适合角色 |
|---|---|---|---|
| `zh-CN-YunxiNeural` | 男 | 清朗少年感 | 青年男主、清冷角色 |
| `zh-CN-YunyangNeural` | 男 | 沉稳播音 | 旁白、长者、正式叙述 |
| `zh-CN-YunjianNeural` | 男 | 浑厚有力 | 硬汉、武将 |
| `zh-CN-XiaoxiaoNeural` | 女 | 标准温柔 | 女主、现代女性 |
| `zh-CN-XiaoyiNeural` | 女 | 轻软少女 | 少女、灵动角色 |
| `zh-CN-XiaomoNeural` | 女 | 温柔知性 | 姐姐、母亲 |
| `zh-CN-XiaoshuangNeural` | 女 | 童声 | 儿童角色 |
| `zh-CN-liaoning-XiaobeiNeural` | 女 | 东北口音 | 方言角色 |
| `zh-CN-shaanxi-XiaoniNeural` | 女 | 陕西口音 | 方言角色 |

**音色必须与角色设定一致，且全片不换。** 换了音色等于换了演员。

### 语速与音调调参

| 参数 | 语法 | 效果 |
|---|---|---|
| `rate` | `+10%` / `-5%` | 语速。**放慢比加快更显情绪** |
| `pitch` | `+4Hz` / `-2Hz` | 音调。降低显沉稳，升高显年轻 |
| `volume` | `+0%` | 音量，一般不动，留给后期 |

**经验值**：
- 清冷少年：`rate=-5%, pitch=-2Hz`
- 轻软少女：`rate=+2%, pitch=+4Hz`
- 旁白：`rate=-8%, pitch=-4Hz`
- 情绪激动：`rate=+8%, pitch=+2Hz`

### 配音必做的三件事

**1. 逐句试听**（不可跳过）
TTS 的中文多音字与断句经常出错：
- 「还」huán / hái
- 「行」xíng / háng
- 「重」zhòng / chóng
- 「了」le / liǎo

修正手段：改写成不易读错的同义词，或用标点强制断句。
```
❌ 我还了钱（可能读成 hái）
✅ 我已经把钱还了（语义明确，读音不易错）
```

**2. 按镜号命名**：`05_audio/voice/S001_C01.mp3`
`compose_video.py` 依赖这个命名自动做时间轴对齐。名字错了就对不上。

**3. 响度统一**：不同句子音量可能不一致，统一到 **-16 LUFS**（配音轨）
```bash
ffmpeg -i in.mp3 -af loudnorm=I=-16:TP=-1.5:LRA=11 out.mp3
```

## 二、字幕（Subtitle）

### 时间轴生成：两种方式

**方式 A：按字数估算（快速，够用）**
中文 TTS 约 4.8 字/秒，标点 0.3 秒。
本仓库 `build_shotlist.py` 已内置，输出到 `05_audio/subtitles.srt`。

**方式 B：语音识别对齐（精确，推荐成片前做）**
用 `faster-whisper` 识别实际配音音频，得到真实时间轴：
```python
from faster_whisper import WhisperModel

model = WhisperModel("small", device="cpu", compute_type="int8")
segments, info = model.transcribe("05_audio/voice/S005_C01.mp3", language="zh")
for seg in segments:
    print(f"{seg.start:.2f} - {seg.end:.2f}  {seg.text}")
```
**方式 A 用于预览，方式 B 用于成片。** 估算的偏差在 0.3–1 秒，
短句里会明显不同步。

### SRT 格式规范

```
1
00:00:28,000 --> 00:00:30,892
伞撑不起来，可以不走。

2
00:00:14,500 --> 00:00:15,500
为何？
```

硬性要求：
- 时间戳格式 `HH:MM:SS,mmm`（逗号，不是点）
- 序号连续，从 1 开始
- 每条之间空一行
- 单条最短显示 **1.0 秒**（更短观众看不清）
- 单条最长不超过 **7 秒**（超过就读不完了）

### 字幕折行规则

| 约束 | 值 | 理由 |
|---|---|---|
| 单行最大字数 | 16 字（中文） | 超过会压到画面主体 |
| 最多行数 | 2 行 | 3 行遮挡严重 |
| 断行位置 | **优先在标点处** | 语义完整才读得顺 |
| 人工调整 | 断行不理想时手工调 | 脚本只能按标点，语义要人来判 |

```
✅ 伞断了三根骨，
   撑不起来了。
❌ 伞断了三根骨，撑
   不起来了。
```

### 字幕样式

```json
{
  "font_name": "Noto Sans CJK SC",
  "font_candidates": ["Noto Sans CJK SC", "Source Han Sans SC",
                      "Microsoft YaHei", "SimHei", "PingFang SC"],
  "font_size": 26,
  "primary_color": "FFFFFF",
  "outline_color": "1B2A33",
  "outline_width": 2,
  "shadow": 1,
  "margin_v": 48,
  "alignment": 2
}
```

**关键设计**：
- **必须有描边或阴影**。白色字幕压在浅色画面上（水墨白、雪、雾）会完全看不见。
  描边色建议用画面主色（如墨青 `1B2A33`）。
- **margin_v ≥ 40**，避免贴边；短视频平台底部还有 UI 遮挡，建议留 60 以上。
- `alignment=2` 是底部居中（ASS 规范）。

### 字体缺失是隐形炸弹

libass 按字体名查找，**找不到就静默回退到默认字体**，
而默认字体常无中文字形 → 字幕全变成方框（豆腐块），**ffmpeg 不会报错**。

本仓库的 `compose_video.py` 内置字体探测，会按 `font_candidates` 自动回退并打印结果：
```
中文字体：Microsoft YaHei
         已解析到『Microsoft YaHei』（Windows 字体目录命中）；
         配置的『Noto Sans CJK SC』在本机不存在，已自动替换
```

**如果这行输出显示「未找到任何中文字体」，必须先装字体再合成。**

## 三、BGM 与人声的关系

配音与 BGM 的响度关系决定「能不能听清台词」：

| 轨道 | 响度 | 说明 |
|---|---|---|
| 配音 | -16 LUFS | 主体 |
| BGM（无人声时） | -22 dB 相对 | 衬托 |
| BGM（有人声时） | **自动 -8 dB** | 侧链闪避 |
| 成片母版 | -14 LUFS | 平台标准 |

`compose_video.py` 用 `sidechaincompress` 实现自动闪避：
说话时音乐自动降低，说完自动恢复，无需手工调音量曲线。

## 常见错误清单

- ❌ 不试听配音，多音字读错直接进成片
- ❌ 全片角色音色换来换去
- ❌ 配音文件名不符合 `S001_C01.mp3` 规范，时间轴对不上
- ❌ 各句响度不统一，忽大忽小
- ❌ 用估算时间轴直接出成片（应与实际波形对齐）
- ❌ SRT 时间戳用点号而非逗号，部分播放器不识别
- ❌ 字幕单行超过 16 字，遮挡画面
- ❌ 字幕无描边，压在浅色画面上看不见
- ❌ 字幕贴底边，被短视频平台 UI 遮挡
- ❌ 字体缺失不检查，字幕渲染成方框

## 验收标准

- [ ] 音色与角色设定一致且全片不换
- [ ] 逐句试听过，多音字与断句已修正
- [ ] 配音按 `镜号_角色ID.mp3` 命名
- [ ] 配音响度统一（-16 LUFS）
- [ ] 字幕时间轴与实际配音波形对齐（成片前用识别校验）
- [ ] 单行 ≤ 16 字，最多 2 行，断行在标点处
- [ ] 字幕有描边/阴影，margin_v ≥ 40
- [ ] 字体探测结果显示已解析到中文字体
- [ ] BGM 有人声时自动闪避
- [ ] 台词语义与画面动作时间上对得上（说话时人物有相应动作或表情）
