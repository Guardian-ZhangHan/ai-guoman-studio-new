---
name: character-consistency
description: AI 短片角色一致性控制规范。当任务涉及建立角色设定表、锁定角色外观（种子/参考图/LoRA/IP-Adapter）、跨镜头检查角色是否漂移、修复换脸与服装变化问题时使用。
---

# 角色一致性控制（Character Consistency）

## 何时使用

- 新建角色，需要跨镜头保持同一张脸、同一套服装
- 出现「第 3 镜换脸」「第 5 镜衣服变了」「发色不一致」
- 需要为角色写可复用的外观锚点（appearance anchors）
- 需要跨镜头做一致性巡检

## 为什么这是 AI 短片最大的坑

文本生成图像是**无状态**的：每次生成都是从随机噪声开始，
「同一个角色」在模型眼里没有任何内在绑定关系。
指望靠文字描述保持一致性，结果一定是每镜一张新脸。

**必须靠工程手段锁死**，靠四个锚点叠加。

## 四层锚点（按可靠性排序）

| 层级 | 手段 | 可靠性 | 成本 |
|---|---|---|---|
| 1 | **LoRA 微调** | ★★★★★ | 高（需 20–50 张素材训练） |
| 2 | **参考图 + IP-Adapter / 角色参考** | ★★★★ | 中（1 张清晰参考图） |
| 3 | **固定种子 + 完整外观锚点** | ★★★ | 低 |
| 4 | 纯文字描述 | ★ | 极低（不可靠） |

**生产级配置 = 1 + 2 + 3 三层叠加。** 只靠文字描述的项目，一致性问题必然爆发。

## 角色设定表模板

```json
{
  "id": "C01",
  "name": "沈砚",
  "role": "主角·摆渡人",
  "age_look": "二十许",
  "appearance_anchors": {
    "hair": "墨色长发，半束，一支素竹簪",
    "face": "清瘦，眼尾微垂，左眉有一道浅疤",
    "clothing": "靛青粗布短褐，外罩灰白蓑衣，腰间挂旧竹牌",
    "signature_prop": "一柄磨得发亮的竹篙",
    "forbidden": "不得出现金饰、华丽纹样、铠甲"
  },
  "consistency": {
    "seed": 480731,
    "reference_image": "03_character/C01_ref.png",
    "lora_path": "03_character/loras/shenyan_v1.safetensors",
    "lora_weight": 0.75,
    "ip_adapter_weight": 0.6,
    "lock_appearance": true
  },
  "voice": {
    "tts_voice": "zh-CN-YunxiNeural",
    "rate": "-5%",
    "pitch": "-2Hz",
    "persona": "清冷、话少、尾音下沉"
  }
}
```

### 写锚点的三条硬规则

**1. 必须有「不可变特征」（2–3 个）**
例：左眉一道浅疤、眼下小痣、断了三根伞骨的伞。
**这些是跨镜识别的锚**，比「清瘦的少年」这种模糊词有用一百倍。

AI 对「特征点」的保持能力远高于对「整体气质」的保持能力。

**2. 必须有 `forbidden`（禁止元素）**
负向约束比正向描述更能防止漂移。
不写 forbidden 的角色，第 5 镜大概率戴上了金冠或换了华服。

**3. 服装要「封闭描述」**
```
❌ 古装，素雅（模型自由发挥，每镜都不同）
✅ 靛青粗布短褐，外罩灰白蓑衣，腰间挂旧竹牌（封闭且具体）
```
封闭描述 = 颜色 + 材质 + 款式 + 配饰，四项齐全。

## 一致性锚点配置规范

```python
# 每镜生成时的参数组装逻辑（伪代码）
def build_generation_params(shot, character):
    return {
        "prompt": style_prefix + shot.image_prompt,
        "negative_prompt": style.negative_prompt + character.forbidden,
        "seed": character.consistency.seed,         # 角色级固定种子
        "reference_image": character.consistency.reference_image,
        "ip_adapter_weight": 0.6,                   # 0.5-0.7 之间，过高会僵化
        "lora": character.consistency.lora_path,
        "lora_weight": 0.75,                        # 0.6-0.85，过高会过拟合
    }
```

### 权重调参指南

| 参数 | 范围 | 过低后果 | 过高后果 |
|---|---|---|---|
| IP-Adapter weight | 0.5–0.7 | 脸部漂移 | 表情僵化，姿势被参考图锁死 |
| LoRA weight | 0.6–0.85 | 特征不明显 | 过拟合，只会画参考图里的角度 |

**多角色同框时**：IP-Adapter 权重各降到 0.45–0.55，
否则两个角色的特征会互相污染（出现「中间脸」）。

## 一致性巡检流程（必做）

每批素材生成后，**必须**做一次巡检：

```
1. 把同一角色的所有镜头截图拼成一张对比图
   → 工具：Pillow 拼图，或直接看文件夹缩略图
2. 逐项核对（按顺序看，这是人的视觉搜索顺序）：
   ① 脸型与五官比例
   ② 发型与发色
   ③ 服装主色与款式
   ④ 标志性特征（疤/痣/配饰）是否存在且位置正确
   ⑤ 是否出现 forbidden 元素
3. 记录不合格镜头，重出时优先调 IP-Adapter 权重，而非改文字描述
```

**巡检发现的漂移，第一反应是调锚点参数，而不是改提示词文字。**
文字描述对一致性的贡献远小于锚点参数。

```python
# 拼图巡检脚本（Pillow）
from PIL import Image
from pathlib import Path

def contact_sheet(char_id: str, paths: list[Path], out: Path, cols: int = 4) -> None:
    thumbs = [Image.open(p).convert("RGB").resize((320, 180)) for p in paths]
    rows = (len(thumbs) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * 320, rows * 180), "black")
    for i, t in enumerate(thumbs):
        sheet.paste(t, ((i % cols) * 320, (i // cols) * 180))
    sheet.save(out)
```

## 微电影（长片）的额外要求

微电影镜头多、时间跨度长，一致性要求更严：

1. **分段锁定**：每 20 镜做一次巡检，不要攒到全片结束才发现崩了
2. **角色状态表**：如果角色有换装/受伤/年老等变化，必须**显式定义状态节点**
   ```
   C01 状态节点：
     第 1–12 镜：默认造型（靛青短褐 + 蓑衣）
     第 13–18 镜：湿身状态（衣料贴身、发丝滴水）
     第 19 镜后  ：无蓑衣（遗落在渡口）
   ```
   **不做状态表，AI 会在第 13 镜随机换装。**
3. **同框镜头单列清单**：多角色同框镜需单独调低 IP-Adapter 权重并优先重出

## 常见错误清单

- ❌ 只靠文字描述控制一致性
- ❌ 没有 `forbidden`，角色饰品随机漂移
- ❌ 服装描述不封闭（「古装」→ 每镜不同）
- ❌ 每个镜头换一个种子
- ❌ IP-Adapter 权重设到 0.9，人物表情僵死
- ❌ 多角色同框不降权重，出现「中间脸」
- ❌ 全片结束才做一致性检查，返工成本爆炸
- ❌ 角色有换装/状态变化却不定义状态节点

## 验收标准

- [ ] 每个角色有设定表，含 2–3 个不可变特征
- [ ] 每个角色有 forbidden 列表
- [ ] 服装描述封闭（颜色+材质+款式+配饰）
- [ ] 一致性锚点至少配置到第 3 层（种子+参考图），推荐叠加 LoRA
- [ ] 生成后做了巡检拼图，不合格镜头已记录
- [ ] 微电影定义了角色状态节点
- [ ] 多角色同框镜单独记录并降权重
