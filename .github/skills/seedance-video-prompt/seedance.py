#!/usr/bin/env python3
"""
Seedance 2.0 电影级AI视频提示词生成器 · 专业版 V2.1.7
========================================================
真实可运行的 Seedance 2.0 提示词工程工具

功能：
- 参数化提示词生成（四层建筑法 L1→L4）
- 八大行业模板一键调用
- 反模式过滤器（抽象词/冲突指令/多动叠加检测）
- 问题诊断引擎（症状→修复方案）
- 多模态绑定语法组装
- 黄金公式校验
- 能力边界检查

依赖：仅需 Python 3.8+（无第三方依赖）

用法：
  python3 seedance.py --template T1 --subject "运动鞋"
  python3 seedance.py --custom --subject "..." --scene "..." --style "..."
  python3 seedance.py --diagnose "人物变脸"
  python3 seedance.py --check "很科幻的画面，静止且冲刺"
  python3 seedance.py --list-templates
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass, asdict, field
from typing import Optional, Dict, List, Tuple

# ==================== 配置常量 ====================

VERSION = "2.1.7"

# 支持的画幅比例
ASPECT_RATIOS = {
    "9:16": "9:16竖屏",
    "16:9": "16:9横屏",
    "2.35:1": "2.35:1宽银幕",
    "1:1": "1:1方形",
    "4:3": "4:3标准",
}

# Seedance 2.0 能力边界
MODEL_LIMITS = {
    "max_duration": 60,
    "max_resolution": "2K",
    "lip_sync_accuracy": 0.924,
    "stable_success_rate": 0.90,
    "recommended_short": (4, 15),
    "recommended_long": (15, 60),
}

# 抽象形容词黑名单（反模式）
ABSTRACT_WORDS = [
    "高级", "氛围感", "科幻感", "很酷", "很棒", "很美",
    "很治愈", "很文艺", "很有感觉", "特别", "非常好看",
    "很唯美", "很梦幻", "有种感觉", "说不出的",
]

# 逻辑冲突指令对
CONFLICT_PAIRS = [
    ("静止", "冲刺"), ("静止", "奔跑"), ("静止", "高速"),
    ("昏暗", "高亮"), ("暗调", "明亮"), ("阴暗", "耀眼"),
    ("特写", "远景"), ("俯拍", "仰拍"),
    ("慢动作", "急速"), ("缓慢", "高速"),
]

# 多动作叠加检测词
MOTION_WORDS = [
    "奔跑", "冲刺", "跳跃", "翻转", "旋转", "冲击",
    "推进", "拉远", "摇移", "环绕", "跟拍",
]

# 违背物理关键词（需明确声明）
ANTI_PHYSICS = [
    "漂浮空中", "无重力", "反向流动", "穿墙",
    "凭空出现", "瞬移", "变形融合",
]

# 慎用高危项
HIGH_RISK = {
    "复杂文字": "复杂文字必乱码，后期字幕合成",
    "高精度口型": "中文识别 92.4%，复杂对话后期配音",
    "复杂流体": "熔岩/血液/复杂烟雾易穿模，后期特效合成",
    "高速运动": "快速=糊帧抖动，改为缓慢/匀速",
    "多风格混合": "多风格混叠成功率极低，锁定单一风格",
}

# ==================== 八大行业模板库 ====================

TEMPLATES = {
    "T1": {
        "name": "电商产品展示",
        "aspect": "16:9",
        "fps": 24,
        "duration": 5,
        "L1": "16:9横屏、24fps、电影质感、无颗粒",
        "L2": "产品居中特写、白色纯净背景、占画面2/3",
        "L3": "顶部45°聚光柔光、无阴影、暖白色调",
        "L4": "产品匀速旋转360°",
        "style": "高级极简风、商业质感",
        "emotion": "精致质感",
    },
    "T2": {
        "name": "社交媒体治愈生活",
        "aspect": "9:16",
        "fps": 24,
        "duration": 5,
        "L1": "9:16竖屏、24fps、柔光颗粒",
        "L2": "浅景深、主体居中、前景虚化",
        "L3": "自然日光从右上入射、逆光轮廓、暖色调",
        "L4": "主体呼吸感、静止微动",
        "style": "文艺片质感",
        "emotion": "治愈氛围",
    },
    "T3": {
        "name": "科幻史诗场景",
        "aspect": "2.35:1",
        "fps": 24,
        "duration": 10,
        "L1": "2.35:1宽银幕、24fps、暗调电影色、胶片颗粒",
        "L2": "远景山脉、中景飞船、前景人物剪影",
        "L3": "双光源（落日主光+冷蓝补光）、强对比",
        "L4": "缓慢向前推进长镜头",
        "style": "科幻大片质感",
        "emotion": "史诗感、震撼",
    },
    "T4": {
        "name": "美食特写",
        "aspect": "16:9",
        "fps": 24,
        "duration": 5,
        "L1": "16:9、4K、浅景深、纪录片质感",
        "L2": "食物占据画面2/3、盘边虚化、蒸汽升腾",
        "L3": "45°侧光、质感提亮、暖橙色调",
        "L4": "镜头缓慢环绕、蒸汽动态",
        "style": "纪录片风",
        "emotion": "诱人食欲",
    },
    "T5": {
        "name": "运动潮流",
        "aspect": "9:16",
        "fps": 60,
        "duration": 5,
        "L1": "9:16竖屏、60fps高帧率、动态模糊",
        "L2": "主体运动员居中、街头背景",
        "L3": "高对比广告色调、逆光轮廓",
        "L4": "单镜头跟拍",
        "style": "运动潮流广告风",
        "emotion": "荷尔蒙感",
    },
    "T6": {
        "name": "音乐舞蹈MV",
        "aspect": "16:9",
        "fps": 24,
        "duration": 8,
        "L1": "16:9、24fps、舞台质感",
        "L2": "主角居中、霓虹背景",
        "L3": "舞台追光、霓虹光效渲染",
        "L4": "配合音频鼓点、节奏切镜",
        "style": "舞台MV质感",
        "emotion": "律动感",
    },
    "T7": {
        "name": "情感叙事微电影",
        "aspect": "2.35:1",
        "fps": 24,
        "duration": 10,
        "L1": "2.35:1宽银幕、24fps、文艺片颗粒",
        "L2": "留白构图、主体偏右下1/3",
        "L3": "逆光轮廓、情绪光影、冷暖对比",
        "L4": "呼吸感慢镜头",
        "style": "文艺片质感",
        "emotion": "克制情绪、留白",
    },
    "T8": {
        "name": "国风古风",
        "aspect": "16:9",
        "fps": 24,
        "duration": 5,
        "L1": "16:9、24fps、水墨质感",
        "L2": "国画留白、主体居中偏下",
        "L3": "自然光柔光、无强阴影",
        "L4": "主体缓慢转身、衣袂飘动",
        "style": "东方古典韵律、水墨风",
        "emotion": "古典意境",
    },
}

# ==================== 场景问题诊断表 ====================

DIAGNOSTICS = {
    "人物变脸": {
        "symptom": "人物不一致、变脸、面部漂移",
        "cause": "未绑定参考图",
        "fix": "使用 @图片作为主角 绑定参考图",
        "fallback": "连续失效则换首尾帧模式",
    },
    "运镜混乱": {
        "symptom": "运镜混乱抖动、镜头飘忽",
        "cause": "运动指令模糊冲突",
        "fix": "改为单一匀速运动指令",
        "fallback": "或绑定视频运镜参考",
    },
    "无电影感": {
        "symptom": "画面像手机拍摄，缺电影质感",
        "cause": "缺失 L1 技术地基参数",
        "fix": "补 24fps + 宽银幕 + 胶片颗粒 + 暗角",
        "fallback": "参考 T3/T7 模板",
    },
    "音画脱节": {
        "symptom": "音乐与动作不同步",
        "cause": "未绑定音频",
        "fix": "@音频 精准绑定鼓点时间戳",
        "fallback": "改为氛围适配（非精准同步）",
    },
    "画面糊": {
        "symptom": "画面糊、背景乱",
        "cause": "空间分层缺失",
        "fix": "明确前中后景占比 + 虚化背景",
        "fallback": "补浅景深、背景虚化关键词",
    },
    "光影闪烁": {
        "symptom": "光影闪烁、亮度不一致",
        "cause": "多光源冲突",
        "fix": "精简为单一主光源",
        "fallback": "指定光源方向+色温",
    },
    "杂物多": {
        "symptom": "多余人物、杂物入镜",
        "cause": "空间过开放",
        "fix": "收紧构图 + 负向提示无路人无杂物",
        "fallback": "改为特写镜头",
    },
    "穿模": {
        "symptom": "穿模、流体假、物理错乱",
        "cause": "物理交互复杂",
        "fix": "简化动作",
        "fallback": "复杂特效后期合成",
    },
    "动作僵硬": {
        "symptom": "动作僵硬、生硬",
        "cause": "未指定动作速度",
        "fix": "补'缓慢'、'匀速'关键词",
        "fallback": "动作过复杂时删减",
    },
    "画质模糊": {
        "symptom": "画质模糊、颗粒感重",
        "cause": "L1 未写清",
        "fix": "补 4K/2K + 帧率 + 颗粒等级",
        "fallback": "用高帧率模板",
    },
    "文字乱码": {
        "symptom": "画面文字乱码、错字",
        "cause": "触及模型能力边界",
        "fix": "画面不生成文字",
        "fallback": "后期字幕合成",
    },
    "口型对不上": {
        "symptom": "口型与配音不符",
        "cause": "触及模型能力边界",
        "fix": "改为背景旁白，不出现说话画面",
        "fallback": "复杂对话后期配音",
    },
}

# ==================== 数据结构 ====================

@dataclass
class PromptLayers:
    """四层建筑法结构"""
    L1_technical: str = ""    # 技术地基
    L2_spatial: str = ""      # 空间搭建
    L3_lighting: str = ""     # 光影设计
    L4_motion: str = ""       # 运动编排
    subject: str = ""         # 主体
    style: str = ""           # 风格
    emotion: str = ""         # 情绪


@dataclass
class Bindings:
    """@多模态绑定"""
    character_ref: str = ""   # @图片 作为主角
    style_ref: str = ""       # @图片 作为风格参考
    motion_ref: str = ""      # @视频 作为运镜参考
    audio_ref: str = ""       # @音频 X秒鼓点


@dataclass
class RiskCheck:
    """风险检测结果"""
    abstract_words: List[str] = field(default_factory=list)
    conflicts: List[str] = field(default_factory=list)
    motion_overload: List[str] = field(default_factory=list)
    physics_violations: List[str] = field(default_factory=list)
    high_risk_warnings: List[str] = field(default_factory=list)
    is_safe: bool = True


@dataclass
class PromptOutput:
    """完整输出结构"""
    prompt: str = ""
    layers: PromptLayers = field(default_factory=PromptLayers)
    bindings: Bindings = field(default_factory=Bindings)
    risk: RiskCheck = field(default_factory=RiskCheck)
    creation_logic: str = ""
    risk_warnings: List[str] = field(default_factory=list)
    optimization_tips: List[str] = field(default_factory=list)
    fallback_plan: str = ""


# ==================== 反模式过滤器 ====================

def check_abstract_words(text: str) -> List[str]:
    """检测抽象形容词（跳过复合词，如'高级极简风'中的'高级'）"""
    # 白名单：作为复合词组一部分的组合，不算抽象滥用
    safe_compounds = [
        "高级极简", "高级质感", "高级灰", "高级感（", "高级冷色", "高级暖色",
        "氛围光", "氛围灯",
    ]
    hits = []
    for w in ABSTRACT_WORDS:
        if w not in text:
            continue
        # 检查是否只出现在安全复合词中
        temp = text
        for sc in safe_compounds:
            if w in sc:
                temp = temp.replace(sc, "")
        if w in temp:
            hits.append(w)
    return hits


def check_conflicts(text: str) -> List[str]:
    """检测逻辑冲突指令"""
    conflicts = []
    for a, b in CONFLICT_PAIRS:
        if a in text and b in text:
            conflicts.append(f"{a} + {b}")
    return conflicts


def check_motion_overload(text: str) -> List[str]:
    """检测多动作叠加"""
    hits = [w for w in MOTION_WORDS if w in text]
    if len(hits) >= 3:
        return hits
    return []


def check_physics_violation(text: str) -> List[str]:
    """检测违背物理"""
    violations = [w for w in ANTI_PHYSICS if w in text]
    if violations and "参考" not in text and "@" not in text:
        return violations
    return []


def check_high_risk(text: str) -> List[str]:
    """检测慎用高危项"""
    warnings = []
    if re.search(r'文字|字幕|标语', text) and '@' not in text:
        warnings.append(HIGH_RISK["复杂文字"])
    if re.search(r'说话|对话|口型|台词', text):
        warnings.append(HIGH_RISK["高精度口型"])
    if re.search(r'熔岩|血液|烟雾|流体|水花', text):
        warnings.append(HIGH_RISK["复杂流体"])
    if re.search(r'冲刺|高速|急速|飞奔', text):
        warnings.append(HIGH_RISK["高速运动"])
    return warnings


def run_risk_check(text: str) -> RiskCheck:
    """完整风险检查"""
    risk = RiskCheck()
    risk.abstract_words = check_abstract_words(text)
    risk.conflicts = check_conflicts(text)
    risk.motion_overload = check_motion_overload(text)
    risk.physics_violations = check_physics_violation(text)
    risk.high_risk_warnings = check_high_risk(text)
    risk.is_safe = not any([
        risk.abstract_words,
        risk.conflicts,
        risk.motion_overload,
        risk.physics_violations,
    ])
    return risk


# ==================== 提示词生成引擎 ====================

def build_prompt(layers: PromptLayers, bindings: Optional[Bindings] = None) -> str:
    """按四层结构组装提示词"""
    parts = []

    # L1 技术地基（必写）
    if layers.L1_technical:
        parts.append(layers.L1_technical)

    # L2 空间搭建
    if layers.L2_spatial:
        parts.append(layers.L2_spatial)

    # L3 光影设计
    if layers.L3_lighting:
        parts.append(layers.L3_lighting)

    # 主体细节
    if layers.subject:
        parts.append(layers.subject)

    # L4 运动编排
    if layers.L4_motion:
        parts.append(layers.L4_motion)

    # 风格
    if layers.style:
        parts.append(layers.style)

    # 情绪
    if layers.emotion:
        parts.append(layers.emotion)

    prompt = " | ".join(parts)

    # 追加多模态绑定
    if bindings:
        binds = []
        if bindings.character_ref:
            binds.append(f"@{bindings.character_ref} 作为主角")
        if bindings.style_ref:
            binds.append(f"@{bindings.style_ref} 作为风格参考")
        if bindings.motion_ref:
            binds.append(f"@{bindings.motion_ref} 作为运镜参考")
        if bindings.audio_ref:
            binds.append(f"@{bindings.audio_ref}")
        if binds:
            prompt += "\n\n【素材绑定】\n" + "\n".join(binds)

    return prompt


def generate_from_template(
    template_id: str,
    subject: str = "",
    duration: Optional[int] = None,
    bindings: Optional[Bindings] = None,
) -> PromptOutput:
    """从模板生成提示词"""
    if template_id not in TEMPLATES:
        raise ValueError(f"未知模板：{template_id}，可选：{list(TEMPLATES.keys())}")

    t = TEMPLATES[template_id]
    dur = duration or t["duration"]

    layers = PromptLayers(
        L1_technical=t["L1"],
        L2_spatial=t["L2"],
        L3_lighting=t["L3"],
        L4_motion=f"{t['L4']}、时长{dur}秒",
        subject=subject or "（请指定主体）",
        style=t["style"],
        emotion=t["emotion"],
    )

    output = PromptOutput()
    output.layers = layers
    output.bindings = bindings or Bindings()
    output.prompt = build_prompt(layers, output.bindings)

    # 生成创作逻辑说明
    output.creation_logic = (
        f"【调用模板】{template_id} · {t['name']}\n"
        f"【画幅】{t['aspect']}（{ASPECT_RATIOS.get(t['aspect'], t['aspect'])})\n"
        f"【时长】{dur} 秒\n"
        f"【四层结构】L1→L2→L3→L4 分层撰写，未堆砌抽象词\n"
        f"【运动策略】{t['L4']}（{'高成功率' if '缓慢' in t['L4'] or '匀速' in t['L4'] or '静止' in t['L4'] else '中成功率'}）"
    )

    # 风险检查
    output.risk = run_risk_check(output.prompt)
    _fill_warnings_and_tips(output, dur, template_id)

    return output


def generate_custom(
    subject: str,
    scene: str,
    style: str,
    emotion: str = "",
    aspect: str = "16:9",
    fps: int = 24,
    duration: int = 5,
    lighting: str = "",
    motion: str = "缓慢推进",
    bindings: Optional[Bindings] = None,
) -> PromptOutput:
    """自定义参数生成提示词"""
    # 边界校验
    if duration > MODEL_LIMITS["max_duration"]:
        duration = MODEL_LIMITS["max_duration"]

    aspect_desc = ASPECT_RATIOS.get(aspect, aspect)

    layers = PromptLayers(
        L1_technical=f"{aspect_desc}、{fps}fps、电影质感、胶片颗粒",
        L2_spatial=scene,
        L3_lighting=lighting or "45°主光、暖色调、软光",
        L4_motion=f"镜头{motion}、时长{duration}秒",
        subject=subject,
        style=style,
        emotion=emotion or "自然氛围",
    )

    output = PromptOutput()
    output.layers = layers
    output.bindings = bindings or Bindings()
    output.prompt = build_prompt(layers, output.bindings)

    # 生成创作逻辑
    output.creation_logic = (
        f"【自定义生成】\n"
        f"【画幅】{aspect}（{aspect_desc}）\n"
        f"【帧率】{fps}fps\n"
        f"【时长】{duration} 秒\n"
        f"【运动策略】{motion}\n"
        f"【四层结构】L1→L2→L3→L4 完整覆盖"
    )

    output.risk = run_risk_check(output.prompt)
    _fill_warnings_and_tips(output, duration, "custom")

    return output


def _fill_warnings_and_tips(output: PromptOutput, duration: int, template_id: str):
    """填充警告和优化建议"""
    tips = []
    warnings = []

    # 时长建议
    if duration <= 15:
        tips.append("✅ 短视频（≤15秒）：优先稳定极简运动，成功率最高")
    else:
        tips.append("⚠️ 长视频（>15秒）：建议改用多镜头分段叙事，避免单镜头复杂多动")

    # 素材绑定建议
    if not output.bindings.character_ref and "人物" in output.prompt:
        tips.append("💡 涉及人物：强烈建议绑定 @图片作为主角 保障一致性")

    # 风险合并
    risk = output.risk
    if risk.abstract_words:
        warnings.append(f"❌ 抽象词：{', '.join(risk.abstract_words)} → 替换为具体摄影参数")
    if risk.conflicts:
        warnings.append(f"❌ 冲突指令：{', '.join(risk.conflicts)} → 保留其一")
    if risk.motion_overload:
        warnings.append(f"⚠️ 多动作叠加：{', '.join(risk.motion_overload)} → 简化为单一运动")
    if risk.physics_violations:
        warnings.append(f"⚠️ 违背物理：{', '.join(risk.physics_violations)} → 需绑定参考素材")
    for hw in risk.high_risk_warnings:
        warnings.append(f"🟡 {hw}")

    output.optimization_tips = tips
    output.risk_warnings = warnings

    # 兜底方案
    if not risk.is_safe:
        output.fallback_plan = "反模式命中 → 切换极简稳定模板（T1/T2）+ 参考素材绑定"
    elif duration > 30:
        output.fallback_plan = "长视频容错 → 若成片糊帧，切分为 2-3 个短镜头分段生成"
    else:
        output.fallback_plan = f"稳定率约 {int(MODEL_LIMITS['stable_success_rate']*100)}%，如失败保留 10% 重试预算"


# ==================== 问题诊断引擎 ====================

def diagnose(symptom_keyword: str) -> Dict:
    """症状 → 修复方案"""
    # 关键词模糊匹配
    for key, data in DIAGNOSTICS.items():
        if key in symptom_keyword or symptom_keyword in data["symptom"]:
            return {
                "matched": key,
                "symptom": data["symptom"],
                "cause": data["cause"],
                "fix": data["fix"],
                "fallback": data["fallback"],
            }

    # 未匹配返回全表参考
    return {
        "matched": None,
        "message": f"未匹配到「{symptom_keyword}」，请从下表选择：",
        "available_symptoms": [
            {"key": k, "symptom": v["symptom"]}
            for k, v in DIAGNOSTICS.items()
        ]
    }


# ==================== 输出格式化 ====================

def format_output(output: PromptOutput) -> str:
    """Markdown 格式输出"""
    lines = []
    lines.append("═" * 50)
    lines.append("🎬 Seedance 2.0 电影级提示词")
    lines.append("═" * 50)

    lines.append("\n【提示词】\n")
    lines.append(output.prompt)

    lines.append("\n【核心创作逻辑】\n")
    lines.append(output.creation_logic)

    if output.risk_warnings:
        lines.append("\n【失效风险提示】\n")
        for w in output.risk_warnings:
            lines.append(f"  {w}")

    if output.optimization_tips:
        lines.append("\n【优化取舍建议】\n")
        for t in output.optimization_tips:
            lines.append(f"  {t}")

    lines.append("\n【边界止损方案】\n")
    lines.append(f"  {output.fallback_plan}")

    lines.append("\n" + "═" * 50)
    return "\n".join(lines)


def format_diagnosis(result: Dict) -> str:
    """诊断结果格式化"""
    lines = ["🩺 Seedance 问题诊断报告", "═" * 40]

    if result.get("matched"):
        lines.append(f"\n【症状】{result['symptom']}")
        lines.append(f"【根本原因】{result['cause']}")
        lines.append(f"【修复方案】{result['fix']}")
        lines.append(f"【止损兜底】{result['fallback']}")
    else:
        lines.append(f"\n{result.get('message', '')}")
        for item in result.get("available_symptoms", []):
            lines.append(f"  • {item['key']}：{item['symptom']}")

    lines.append("\n" + "═" * 40)
    return "\n".join(lines)


# ==================== CLI 入口 ====================

def main():
    parser = argparse.ArgumentParser(
        description=f"Seedance 2.0 电影级提示词生成器 v{VERSION}",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  # 模板生成
  python3 seedance.py --template T1 --subject "白色运动鞋"
  python3 seedance.py --template T3 --subject "宇航员" --duration 15

  # 自定义生成
  python3 seedance.py --custom \\
      --subject "古装女子" \\
      --scene "沙漠戈壁" \\
      --style "西部电影" \\
      --emotion "苍凉孤寂"

  # 问题诊断
  python3 seedance.py --diagnose "人物变脸"
  python3 seedance.py --diagnose "运镜混乱"

  # 反模式检查
  python3 seedance.py --check "很科幻的画面，静止且冲刺"

  # 列出所有模板
  python3 seedance.py --list-templates

  # 列出所有诊断项
  python3 seedance.py --list-diagnostics
        """
    )

    # 主命令
    parser.add_argument("--template", "-t", metavar="ID",
                        help=f"使用模板 (T1-T8)")
    parser.add_argument("--custom", "-c", action="store_true",
                        help="自定义参数生成")
    parser.add_argument("--diagnose", "-d", metavar="SYMPTOM",
                        help="诊断问题（如：人物变脸、运镜混乱）")
    parser.add_argument("--check", metavar="TEXT",
                        help="对提示词进行反模式检查")

    parser.add_argument("--list-templates", action="store_true",
                        help="列出所有模板")
    parser.add_argument("--list-diagnostics", action="store_true",
                        help="列出所有诊断项")

    # 生成参数
    parser.add_argument("--subject", "-s", default="",
                        help="主体（如：白色运动鞋、古装女子）")
    parser.add_argument("--scene", default="",
                        help="场景（自定义模式必填）")
    parser.add_argument("--style", default="",
                        help="风格")
    parser.add_argument("--emotion", default="",
                        help="情绪")
    parser.add_argument("--aspect", default="16:9",
                        choices=list(ASPECT_RATIOS.keys()),
                        help="画幅比例")
    parser.add_argument("--fps", type=int, default=24,
                        help="帧率")
    parser.add_argument("--duration", type=int, default=5,
                        help="时长（秒）")
    parser.add_argument("--lighting", default="",
                        help="光影设计")
    parser.add_argument("--motion", default="缓慢推进",
                        help="镜头运动")

    # 多模态绑定
    parser.add_argument("--character-ref", default="",
                        help="人物参考图")
    parser.add_argument("--style-ref", default="",
                        help="风格参考图")
    parser.add_argument("--motion-ref", default="",
                        help="运镜参考视频")
    parser.add_argument("--audio-ref", default="",
                        help="音频参考")

    # 输出
    parser.add_argument("--output", "-o", choices=["markdown", "json"],
                        default="markdown", help="输出格式")

    args = parser.parse_args()

    # 列表操作
    if args.list_templates:
        print("🎨 Seedance 2.0 八大行业模板\n")
        for tid, t in TEMPLATES.items():
            print(f"  {tid} · {t['name']}")
            print(f"     画幅：{t['aspect']} | 帧率：{t['fps']}fps | 时长：{t['duration']}秒")
            print(f"     风格：{t['style']}\n")
        return

    if args.list_diagnostics:
        print("🩺 Seedance 问题诊断表\n")
        for key, data in DIAGNOSTICS.items():
            print(f"  • {key}")
            print(f"    症状：{data['symptom']}")
            print(f"    修复：{data['fix']}\n")
        return

    # 反模式检查
    if args.check:
        risk = run_risk_check(args.check)
        print("🔍 反模式检查报告\n")
        print(f"输入：{args.check}\n")
        if risk.is_safe and not risk.high_risk_warnings:
            print("✅ 通过检查，无明显反模式")
        else:
            if risk.abstract_words:
                print(f"❌ 抽象词：{', '.join(risk.abstract_words)}")
            if risk.conflicts:
                print(f"❌ 冲突指令：{', '.join(risk.conflicts)}")
            if risk.motion_overload:
                print(f"⚠️ 多动叠加：{', '.join(risk.motion_overload)}")
            if risk.physics_violations:
                print(f"⚠️ 违背物理：{', '.join(risk.physics_violations)}")
            for hw in risk.high_risk_warnings:
                print(f"🟡 {hw}")
        return

    # 诊断
    if args.diagnose:
        result = diagnose(args.diagnose)
        print(format_diagnosis(result))
        return

    # 构建绑定
    bindings = Bindings(
        character_ref=args.character_ref,
        style_ref=args.style_ref,
        motion_ref=args.motion_ref,
        audio_ref=args.audio_ref,
    )

    # 模板生成
    if args.template:
        try:
            output = generate_from_template(
                args.template, args.subject, args.duration, bindings
            )
        except ValueError as e:
            print(f"❌ {e}")
            sys.exit(1)
    elif args.custom:
        if not args.subject or not args.scene or not args.style:
            print("❌ 自定义模式需提供 --subject、--scene、--style")
            sys.exit(1)
        output = generate_custom(
            subject=args.subject,
            scene=args.scene,
            style=args.style,
            emotion=args.emotion,
            aspect=args.aspect,
            fps=args.fps,
            duration=args.duration,
            lighting=args.lighting,
            motion=args.motion,
            bindings=bindings,
        )
    else:
        parser.print_help()
        print("\n💡 请选择一种模式：--template / --custom / --diagnose / --check")
        sys.exit(1)

    # 输出
    if args.output == "json":
        print(json.dumps(asdict(output), ensure_ascii=False, indent=2))
    else:
        print(format_output(output))


if __name__ == "__main__":
    main()
