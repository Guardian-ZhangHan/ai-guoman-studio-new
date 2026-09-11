---
name: gen-engine-comfyui
description: 生成引擎编排技能 —— 用 ComfyUI 作为本地生图/生视频中枢，或用云端 API（可灵/即梦/HunyuanVideo）。把 build_shotlist 产出的分镜 prompt 映射成可复现的生成任务，并落盘完整参数。当用户要"真的出素材"而不是只写提示词时使用。
---

# 生成引擎编排（ComfyUI 中枢 / 云端 API 回退）

## 一、为什么用 ComfyUI 当中枢
分镜脚本只产出**提示词文本**，要变成像素必须接一个生成后端。ComfyUI 是 2026 年开源短片流水线的事实标准：
- 统一调度 Wan2.2 / HunyuanVideo / LTX / FLUX / SDXL 等模型
- 节点图可版本化、可批量、可复用
- 支持 LoRA / IP-Adapter / PuLID 接入（见 `character-lora-train`）

## 二、本地路线（有 GPU，≥16GB 显存推荐）
```bash
# 引擎已克隆到 engines/ComfyUI（见 copilot-setup-steps.yml）
cd engines/ComfyUI && python main.py --listen 127.0.0.1 --port 8188
```
用 `websocket-client` 把镜头推成任务：
```python
import websocket, json, uuid
ws = websocket.WebSocket(); ws.connect("ws://127.0.0.1:8188/ws")
prompt = build_workflow(shot)          # 见下方映射
ws.send(json.dumps({"prompt": prompt, "client_id": str(uuid.uuid4())}))
# 轮询 /history 取输出视频，存 04_shots/S0xx.mp4
```

### 分镜 → ComfyUI 节点映射
| 分镜字段 | ComfyUI 节点 |
|---|---|
| `image_prompt` | CLIP Text Encode（正向） |
| `negative_prompt` | CLIP Text Encode（负向） |
| `style_bible.seed` | KSampler seed / 模型固定种子 |
| `ref_image`（角色） | IP-Adapter / Load Image |
| `loras` | Load LoRA（叠加权重） |
| 图生视频 | Wan2.2-I2V / HunyuanVideo-I2V 节点 |

**关键原则**：把 model / seed / steps / cfg / lora 权重 **随镜头落盘**（`04_shots/S0xx.meta.json`），
这样"这个镜头效果好"可以复现，否则参数就丢了。

## 三、云端路线（无显卡推荐）
`requests` 调平台 API，提示词同样落盘：
- 可灵 / Kling、即梦 / Jimeng、海螺 / Hailuo、通义万相、Vidu、Runway
- 返回视频存 `04_shots/S0xx.mp4`，meta 记录平台+任务ID+参数

## 四、验收
- [ ] 每个镜头都记录了模型与完整参数（可复现）
- [ ] 角色镜头走了 IP-Adapter/LoRA 锚点，不是纯文字
- [ ] 单镜 ≤ 10s（长镜拆镜或分段拼接）
- [ ] 生成素材命名遵循 `S0xx` 规范，可对应分镜表
