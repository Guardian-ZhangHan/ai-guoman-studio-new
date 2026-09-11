---
name: voice-clone-tts
description: 角色声纹配音技能 —— 为每个角色建声纹档案，用 CosyVoice2 / GPT-SoVITS / Fish Speech / IndexTTS-2 生成一致的中文配音。把 voiceover.csv 的台词逐句转成 wav。当用户要做"听得是同一个人"的国漫配音时使用（替代 edge-tts 通用音）。
---

# 角色声纹配音（Voice Cloning TTS）

## 一、为什么不用 edge-tts 了
`edge-tts` 免费但**每个角色声音一样**，短片一听就"AI 味"。要做角色辨识度，必须声纹克隆。

## 二、引擎选型（2026）
| 引擎 | 克隆样本 | 亮点 | 许可 |
|---|---|---|---|
| **CosyVoice 2/3**（阿里通义） | 3s 零样本 / 30s+ 更佳 | 流式150ms、18方言、情感 | 免费（商用查条款） |
| **GPT-SoVITS v2** | 30s–3min | 中文社区最活跃、生态全 | MIT |
| **Fish Speech 1.5** | 10–30s | 多语种 ELO 最高(1339) | 自定义（免费） |
| **IndexTTS-2** | 5–15s | 时长精确可控 + 音色/情感解耦 | 自定义（免费） |

> 配音首选 **IndexTTS-2**（时长可控，避免台词超镜）；方言/实时选 CosyVoice。

## 三、角色声纹档案（放 03_character/）
```
03_character/
├── C01_沈砚/
│   ├── ref_voice.wav        # 参考音频（清晰、无背景乐，30s+ 更稳）
│   └── voice_profile.yaml   # 引擎 / 样本路径 / 默认情感 / 语言
└── C02_阿箬/ ...
```

## 四、流程
1. 读 `05_audio/voiceover.csv`（角色 / 台词 / 时间轴 / 情感）
2. 按角色加载声纹档案
3. 逐句生成：`python -m <engine> --ref ref_voice.wav --text "台词" --out 05_audio/voice/S0xx_C0x.wav`
4. 命名对齐分镜：`S0xx` = 镜号，`C0x` = 角色
5. 时长校验：生成音频时长 ≤ 镜头 `duration_sec`，否则重生成或拆镜

## 五、合规红线
- **声音克隆须获授权**（含用他人声音做 AI 配音）
- 商用前核对各引擎许可条款（部分自定义许可限制商业使用）

## 验收
- [ ] 每个角色有独立声纹档案，且样本清晰
- [ ] 同角色多镜声音一致（可盲听区分角色）
- [ ] 音频时长不超镜头
- [ ] 授权已确认（如用他人声音）
