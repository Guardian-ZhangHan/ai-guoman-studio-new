---
name: lip-sync-talkinghead
description: 对口型 / 数字人技能 —— 把 TTS 音频驱动到角色肖像上，生成会说话的镜头。覆盖 MuseTalk（腾讯近实时）、EchoMimic（蚂蚁 landmark 可控）、LivePortrait（快手表情/姿态）、LatentSync（字节）、Wav2Lip（重同步）、Hallo（复旦）。当短片有台词、需要角色"开口说话"时使用。
---

# 对口型 / 肖像驱动（Lip-Sync & Talking Head）

## 一、适用场景
只要有**台词镜头**，就不能只放一张静态图 + 画外音，必须让角色开口。否则观众立刻出戏。

## 二、引擎选型矩阵（2026）
| 需求 | 首选 | 说明 |
|---|---|---|
| 同步精度优先（配音译制） | **Wav2Lip** / Sync 1.9 | 帧对齐最强，但需已有正脸视频 |
| 情感表达 | **Sonic** / EchoMimic | 携带表演情绪 |
| 长镜头 / 数字人 | **Hallo / Hallo2** | 身份保持最干净（>30s） |
| 近实时 / 直播感 | **MuseTalk**（腾讯）/ LivePortrait | 推理快 |
| 表情 + 头姿精细控制 | **LivePortrait**（快手） | MIT，需另接口型 |
| 开源音画同生成 | **LTX-2**（见 gen-engine-comfyui） | 一步出带口型视频 |

## 三、流程
1. 准备：角色参考图 `03_character/C0x_ref.png` + TTS 音频 `05_audio/voice/S0xx_C0x.wav`
2. 驱动：
   ```bash
   # MuseTalk 示例
   python engines/MuseTalk/inference.py \
     --avatar 03_character/C0x_ref.png \
     --audio 05_audio/voice/S0xx_C0x.wav \
     --out 04_shots/S0xx_talk.mp4
   ```
3. 合成：把 `S0xx_talk.mp4` 替换/叠加进该镜成片（`compose_video.py` 支持外部片段）

## 四、与角色一致性衔接
- 先过 `character-lora-train` 出稳定角色脸，再对口型，避免"脸对上了嘴不对"
- 口型镜头仍要走 `build_shotlist` 的角色锚点校验

## 五、合规
- 用真人形象驱动需**肖像权授权**
- 平台对口型/深伪有标注要求，上线前核对

## 验收
- [ ] 口型与音频帧对齐（无明显漂移）
- [ ] 角色脸与全程一致
- [ ] 时长匹配镜头
- [ ] 肖像授权已确认
