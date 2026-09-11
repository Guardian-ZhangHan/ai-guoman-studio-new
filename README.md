# AI 国漫短片 / 微电影制作环境（Guoman AI Studio）

> 一个面向 **GitHub Copilot Coding Agent** 的 AI 国漫短片与微电影流水线仓库。
> 目标：把「剧本 → 分镜 → 角色一致性 → 文生图/图生视频 → 配音字幕 → 剪辑合成」
> 这条链上的**参数、提示词模板、命名规范与校验脚本**全部固化成可执行的工程，
> 让 AI 生成的不是一堆散装素材，而是一条**可复现、可换模型、可接续生产**的流水线。

配套方法论对照（对应参考图五个阶段）：

| 阶段 | 参考图内容 | 本仓库落地位置 |
|---|---|---|
| 阶段 1 | 开通订阅、开启 Coding Agent、配置仓库权限 | GitHub 网页设置，见下方「阶段 1 清单」 |
| 阶段 2 | `.github/copilot-setup-steps.yml` 环境配置 | [`.github/copilot-setup-steps.yml`](.github/copilot-setup-steps.yml) + `requirements.txt` |
| 阶段 3 | `.github/skills/` 技能包 + 自定义 Agent | [`.github/skills/`](.github/skills) + [`.github/agents/`](.github/agents) |
| 阶段 4 | 三种入口（网页面板 / Issue 驱动 / VS Code） | 见下方「阶段 4 三种入口」 |
| 阶段 5 | 权限与安全 | 见下方「阶段 5」 |

---

## 一、为什么短片制作也需要工程化

AI 短片最容易死在三个地方，而且都不是「模型不行」：

| 痛点 | 表现 | 本仓库的对策 |
|---|---|---|
| **角色不一致** | 同一个角色第 3 镜换脸、换服装、换发色 | 角色设定表 + 一致性锚点（seed / 参考图 / LoRA）+ 逐镜检查脚本 |
| **素材失控** | 生成 80 个文件，最后剪辑时不知道哪个是哪一镜 | 强制命名规范 + 分镜表驱动生成 + 提示词落盘 |
| **参数丢失** | 某个镜头效果很好，但忘了用什么参数生成的，无法复现 | 每个镜头的完整 prompt + 参数随镜头存档，可随时重出 |

**本仓库的核心主张：提示词和参数是资产，必须像代码一样版本管理。**

## 二、目录结构

```
ai-guoman-studio/
├── .github/
│   ├── copilot-setup-steps.yml      # 阶段 2：Agent 沙箱环境配方
│   ├── agents/                      # 阶段 3：导演 / 美术 / 剪辑 Agent
│   │   ├── guoman-director.agent.md
│   │   ├── storyboard-artist.agent.md
│   │   └── edit-director.agent.md
│   └── skills/                      # 阶段 3：技能包（基础 5 + 生成增强 9）
│       ├── guoman-visual-prompt/SKILL.md   # 国漫视觉提示词规范（水墨/赛璐璐/厚涂）
│       ├── character-consistency/SKILL.md   # 角色一致性（seed/参考图/LoRA 锚点）
│       ├── storyboard-shotlist/SKILL.md     # 分镜→镜头清单 schema
│       ├── tts-subtitle/SKILL.md            # 配音与字幕（edge-tts 兜底）
│       ├── edit-compose/SKILL.md            # FFmpeg 合成
│       ├── gen-engine-comfyui/SKILL.md      # 生成引擎编排（ComfyUI + 云端 API 兜底）
│       ├── voice-clone-tts/SKILL.md         # 声音克隆 TTS（CosyVoice/GPT-SoVITS/Fish/IndexTTS-2）
│       ├── lip-sync-talkinghead/SKILL.md    # 对口型/说话头（MuseTalk/EchoMimic/LivePortrait/Wav2Lip）
│       ├── character-lora-train/SKILL.md    # 角色 LoRA / IP-Adapter / PuLID 训练梯度
│       ├── post-upscale-restore/SKILL.md    # 超分修复（Real-ESRGAN/GFPGAN/RIFE）
│       ├── bgm-sfx-gen/SKILL.md             # BGM / 音效生成（audiocraft/demucs/Suno）
│       ├── ww2-style-bible/SKILL.md         # 二战题材美术圣经（1940s 胶片感 + 合规红线）
│       ├── apocalypse-style-bible/SKILL.md  # 末日生存题材美术圣经（锈蚀/衰败/分级）
│       └── historical-compliance/SKILL.md   # 历史/版权/地图合规闸门
├── configs/
│   ├── pipeline.example.yaml        # 完整项目配置模板（人读，含注释）
│   ├── demo_short.json              # 可执行演示项目（青竹渡·水墨仙侠，零依赖）
│   ├── ww2_example.json              # 二战题材 demo（无名高地，6 镜 / 40s）
│   └── apocalypse_example.json      # 末日生存题材 demo（锈色黎明，6 镜 / 40s）
├── scripts/
│   ├── test_check.py                # 环境自检（ffmpeg / 依赖 / 字体 / 目录）
│   ├── build_shotlist.py            # 分镜→镜头清单 + 提示词 +配音稿 + SRT
│   └── compose_video.py             # FFmpeg 合成成片（支持 --dry-run）
├── 01_script/                       # 剧本、大纲、台词
├── 02_storyboard/                   # 分镜表、提示词（build_shotlist 产出）
│   └── prompts/                     # 每镜一个提示词文件，可复制到任何生成平台
├── 03_character/                    # 角色设定表 + 一致性参考图 + LoRA
├── 04_shots/                        # 镜头素材（S001.mp4 / S001.png ...）
├── 05_audio/                        # 配音、BGM、音效、字幕
├── 06_final/                        # 成片输出
└── assets/                          # 字体、LUT、水印、片头片尾
```

## 三、快速开始

```bash
# 1. 环境自检（先确认 ffmpeg、字体、依赖）
python scripts/test_check.py

# 2. 打开演示项目（青竹渡·水墨仙侠短片）
python scripts/build_shotlist.py --config configs/demo_short.json

# 2b. 二战题材 demo（无名高地，6 镜 / 40s，含 style_bible + 合规闸门）
python scripts/build_shotlist.py --config configs/ww2_example.json

# 2c. 末日生存题材 demo（锈色黎明，6 镜 / 40s，含 style_bible + 分级）
python scripts/build_shotlist.py --config configs/apocalypse_example.json

# 产出：
#   02_storyboard/shotlist.md        人读分镜表
#   02_storyboard/shots.csv          机读镜头清单（供批量生成平台导入）
#   02_storyboard/prompts/S001_image.txt   文生图提示词（可直接粘贴到平台）
#   02_storyboard/prompts/S001_video.txt   图生视频提示词
#   05_audio/voiceover.csv           配音清单（角色/台词/时间轴/情感）
#   05_audio/subtitles.srt           字幕（可直接烧录）

# 3. 把 04_shots/ 补上真实素材后合成
python scripts/compose_video.py --project configs/demo_short.json --dry-run   # 先看命令
python scripts/compose_video.py --project configs/demo_short.json             # 真合成
```

## 四、核心依赖说明

### 核心依赖（`requirements.txt`，轻量，必装）

| 包 | 用途 |
|---|---|
| `imageio-ffmpeg` | 提供 ffmpeg 二进制，免手动装 |
| `moviepy` / `ffmpeg-python` | 剪辑封装 |
| `Pillow` | 图片处理、加水印、拼图预演 |
| `pydub` | 音频拼接、音轨淡入淡出、响度归一 |
| `edge-tts` | **免费中文配音**（微软 Edge TTS，神经语音，无需 API Key） |
| `faster-whisper` | 台词时间轴自动对齐（可选，也可用脚本估算） |
| `pyyaml` | 读 YAML 配置 |
| `tqdm` | 批量处理进度条 |
| `websocket-client` / `requests` | 对接 ComfyUI 本地服务 / 云端生成 API |
| `opencv-python` / `av` | 帧序列读写、抽帧、视频容器处理（对口型/超分前置） |
| `realesrgan` / `basicsr` / `gfpgan` / `facexlib` | 超分修复、人脸复原（后期增强） |
| `audiocraft` / `demucs` | BGM / 音效生成、人声伴奏分离（后期音轨） |

### 可选 GPU 依赖（`requirements-gpu.txt`，本地跑扩散模型才需要）

`torch` / `diffusers` / `transformers` / `accelerate` / `xformers` / `safetensors` —— **注意**：本地跑视频生成
对显存要求极高（通常 ≥ 12GB，图生视频建议 ≥ 24GB）。
**没有本地显卡时的推荐路径：用云端平台生成（即梦 / 可灵 / 通义万相 / Runway / Vidu 等），
本仓库负责产出「可直接粘贴的提示词 + 参数 + 命名规范 + 合成链路」。**

> **生成引擎与模型权重**：ComfyUI、CosyVoice、GPT-SoVITS、MuseTalk、LivePortrait、EchoMimic、
> CodeFormer、RIFE 等通过 `copilot-setup-steps.yml` 的「步骤 8」（默认 `if: false`，需手动开启）以 `git clone` +
> `huggingface-cli` 拉取。脚本本身零依赖、不绑定任何引擎，提示词落盘为纯文本可自由切换平台。

## 四-甲、生成增强流水线（14 个技能包如何串起来）

基础 5 包管「剧本→分镜→一致性→配音→合成」；增强 9 包覆盖本地/云端高阶生成链路：

```
build_shotlist → gen-engine-comfyui(文生图/图生视频) → voice-clone-tts(角色声线)
   → lip-sync-talkinghead(对口型说话头) → character-lora-train(角色固化)
   → post-upscale-restore(超分/人脸修复/补帧) → bgm-sfx-gen(配乐音效)
   → edit-compose(合成)   // 全程受 historical-compliance 闸门约束
```

题材专属：`ww2-style-bible`（二战）与 `apocalypse-style-bible`（末日生存）提供调色板、
负向提示词与合规红线，直接挂到分镜配置 `style_bible` 字段即可。

## 五、支持的两类作品

| 类型 | 时长 | 镜头数（参考） | 特点 |
|---|---|---|---|
| **短片** `short_film` | 1–5 分钟 | 15–60 镜 | 完整起承转合，需要 BGM 与配音 |
| **微电影** `micro_film` | 5–20 分钟 | 60–200 镜 | 多场景多角色，需要角色一致性强约束与分幕管理 |

`configs/pipeline.example.yaml` 中通过 `project.type` 切换，脚本会据此调整校验严格度
（微电影对角色一致性、场景连续性的检查更严）。

### 当前重点题材方向：二战系列 + 末日生存

本仓库按使用者的创作方向，预置了 2 套「美术圣经 + 合规闸门」，可直接挂到分镜配置：

| 题材 | 美术圣经技能包 | 视觉基调 | 合规红线（highlights） |
|---|---|---|---|
| **二战系列** | `ww2-style-bible` | 1940s 胶片颗粒、褪色档案感、战地泥泞与硝烟、不同战区（华北/太平洋/欧洲）差异 | **不美化侵略与极端主义**；卐字符仅限史料/批判性语境；不煽动民族仇恨；平台分级注意血腥 |
| **末日生存** | `apocalypse-style-bible` | 锈蚀灰调 + 辐射绿、衰败城市、末日天光、废土质感 | 暴力度与分级合规；不渲染真实自残/自杀方法；不影射现实灾难事件 |

两个 demo（`ww2_example.json` / `apocalypse_example.json`）均已写满 `style_bible`、`palette`、
`negative_prompt`、角色一致性锚点（`seed`/`lora`/`ip_adapter`）与 `compliance` 清单，
可被 `build_shotlist.py` 直接校验通过。

## 六、阶段 1 操作清单（GitHub 网页端）

1. 登录 GitHub → 头像下拉 → **Settings**
2. 左侧进入 **Copilot**
3. 找到 **Coding agent** 板块，打开 **Enable coding agent**
4. **Repository access**：选择本仓库（`Only selected repositories` 更安全）
5. **Model**：按需开启模型开关
6. 保存后 Agent 即可读仓库、建 `copilot/*` 分支、提交、创建 Draft PR

## 七、阶段 4 三种入口

**入口 A：网页 Agent 面板**
> 按 `.github/skills/guoman-visual-prompt` 的规范，为 `configs/demo_short.json` 里的
> 第 4–8 镜补写 image_prompt 与 video_prompt，并跑 `scripts/build_shotlist.py` 验证通过

**入口 B：Issue 驱动**
新建 Issue 写清需求 → Assignee 设为 `@copilot` → 自动生成 Draft PR → PR 评论里继续迭代

**入口 C：VS Code Copilot Chat**
```
@github 让 build_shotlist.py 支持按幕分组输出，并补测试
```

## 八、阶段 5 权限与安全

1. 原生 GitHub 内置 App，**无需手动配 Token**
2. 沙箱临时隔离，任务结束销毁；**只能推 `copilot/*` 分支**，无法直接改 `main`
3. 消耗 GitHub Actions minutes + Copilot AI Credits

## 九、⚠️ 版权与合规提醒（影视创作尤其重要）

1. **AI 生成素材的版权归属**因平台而异，商用前必须逐一核对各生成平台的服务条款
2. **不得**用真人明星肖像、未授权 IP 角色形象作为参考图输入
3. **不得**生成侵犯他人著作权、商标权的形象；国漫风格可以借鉴**风格流派**，
   不能复制具体作品的**受保护角色形象**
4. **影视备案**：国内上线发行的微电影可能涉及备案与内容审核要求，请按现行规定办理
5. 背景音乐必须使用**已授权**曲库或自有版权音乐，不得直接使用商业歌曲
6. 配音使用他人声音（含 AI 声音克隆）需获得**明确授权**
7. 本仓库脚本只做工程组织，**不提供任何版权判断**，合规责任由创作者承担

## 十、AI 生成内容的科学/事实性提醒

1. 若短片涉及历史、地理、民族、宗教内容，**史实与表述必须人工核查**
2. 涉及中国地图画面的，必须使用合规地图数据，中国香港/中国台湾/中国澳门的标注须符合国家标准
3. AI 生成的字幕/台词可能含错别字与事实错误，**成片前必须逐句校对**

## 十一、与 CodeWhale 的差异

| | Copilot Coding Agent | CodeWhale |
|---|---|---|
| Token | 原生 GitHub，**免配置** | 需手动配 MCP + token |
| Issue/PR | 原生支持 | 需手动配置 |
| 底层模型 | 受限（平台提供的模型） | **自由** |

本仓库的脚本与技能包**不绑定任何平台**，提示词落盘为纯文本，
因此可以自由切换生成平台（这也是把提示词当资产管理的好处）。
