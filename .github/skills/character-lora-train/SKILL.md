---
name: character-lora-train
description: 角色一致性终极方案技能 —— 把"seed + 参考图"锚点升级为可复用的 LoRA / IP-Adapter / PuLID / InstantID，让同一角色跨镜、跨场景、跨镜头保持同一张脸。当 build_shotlist 的 seed 锚点仍出现换脸漂移时使用。
---

# 角色一致性：LoRA / IP-Adapter / PuLID

## 一、一致性梯度（从弱到强）
1. **seed 锚点**（已有）：同模型同种子，弱一致，换姿态易漂
2. **IP-Adapter**：把参考图注入，不动训练，即插即用，强度可调
3. **PuLID / InstantID**：人脸 ID 强锁定，适合特写
4. **LoRA 训练**：用角色多视图数据集训 SDXL / FLUX LoRA，最强且最稳

> 准则（来自 guoman-director）：一致性漂移先调**锚点参数**，不要靠改文字描述。

## 二、LoRA 训练流程
```bash
# 1. 准备数据集 03_character/C0x/lora_train/（20–40 张多角度、统一画风）
# 2. 打标（角色名触发词，如 "shenyan character"）
# 3. 训练（SDXL 示例，具体见各项目 README）
python engines/ComfyUI/.../sd_xl_train.py \
  --data 03_character/C0x/lora_train --output 03_character/loras/C0x.safetensors
```
- 产出 `.safetensors` 放 `03_character/loras/`（已被 .gitignore 排除，体积大）
- `build_shotlist` 的 `characters[].loras` 字段引用权重

## 三、IP-Adapter / PuLID（免训练）
- ComfyUI 加载 `IPAdapter` / `PuLID` 节点，输入 `ref_image`
- 强度建议 0.6–0.9，过高会损失画面多样性

## 四、验收
- [ ] 同一角色在 ≥5 个镜头里脸一致（盲测可分）
- [ ] LoRA 文件已存档且记录触发词/权重
- [ ] 参考图与成片画风统一（不被参考图写实细节带偏）
- [ ] 特写镜头用 PuLID/InstantID 锁定 ID
