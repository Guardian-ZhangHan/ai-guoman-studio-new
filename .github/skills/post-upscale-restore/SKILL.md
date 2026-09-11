---
name: post-upscale-restore
description: 后期增强技能 —— 超分辨率（Real-ESRGAN）、人脸修复（GFPGAN / CodeFormer）、帧率补间（RIFE 24→60fps）。把 AI 生成的低质/低帧素材提升到成片可用的清晰度与流畅度。在生成素材进 compose_video 之前使用。
---

# 后期增强：超分 / 人脸修复 / 补帧

## 一、超分辨率（Real-ESRGAN）
```bash
python engines/Real-ESRGAN/inference_realesrgan.py \
  -n RealESRGAN_x4plus -i 04_shots/S0xx.png -o 04_shots/S0xx_4x.png
```
- 视频：逐帧或专用视频版（`realesrgan-ncnn-vulkan` 更快）
- 注意：**不要过度超分**，动画线条超分易出"塑料描边"

## 二、人脸修复（GFPGAN / CodeFormer）
```bash
python engines/CodeFormer/inference_codeformer.py -i 04_shots/ -o 04_shots/restored/ -w 0.7
```
- 人脸特写必做，否则放大后五官糊
- `w` 为人脸保真度权重，0.5–0.8 较稳

## 三、帧率补间（RIFE）
AI 视频常见 16–24fps，成片需 25/30/60fps：
```bash
python engines/ECCV2022-RIFE/inference_video.py \
  --video 04_shots/S0xx.mp4 --output 04_shots/S0xx_60fps.mp4 -f 60
```
- 动作镜头补帧更顺；但**慢镜头/静态别硬补**，会显假

## 四、接入合成
- 增强后素材放回 `04_shots/`（建议 `_enh` 后缀区分原片）
- `compose_video.py` 读增强版；BGM 闪避仍用 `demucs` 分离（见 `bgm-sfx-gen`）

## 验收
- [ ] 超分未引入明显伪影（线条/文字清晰不塑料）
- [ ] 人脸特写已修复
- [ ] 成片帧率统一（避免镜间 24/60 跳变）
- [ ] 保留原片，增强版单独命名
