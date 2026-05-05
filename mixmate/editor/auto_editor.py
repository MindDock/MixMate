import json
import random
from typing import List, Optional
from ..models import (
    TimelineAnalysis, EditPlan, EditDecision,
    ShotSegment, ContentTag,
)
from ..config import StyleConfig, get_style
from .cut_engine import CutEngine
from .effect_engine import EffectEngine
from .subtitle_engine import SubtitleEngine
from .style_profiles import StyleProfiles


class AutoEditor:
    """
    自动剪辑器 - 系统的核心调度器
    整合 Timeline 分析 + 风格配置 + 剪辑引擎，一键生成剪辑方案
    """

    def __init__(self, style_name: str = "tiktok_flash"):
        self.style = get_style(style_name)
        self.cut_engine = CutEngine(self.style)

    def create_edit_plan(
        self,
        analysis: TimelineAnalysis,
        target_duration: Optional[float] = None,
        plan_name: Optional[str] = None,
    ) -> EditPlan:
        duration = target_duration or self.style.target_duration
        name = plan_name or f"{self.style.display_name}_{duration}s"

        print(f"\n✂️ 生成剪辑方案: {name}")
        print(f"  风格: {self.style.display_name}")
        print(f"  目标时长: {duration}s")

        decisions = self.cut_engine.generate_edit_plan(analysis, duration)

        if self.style.subtitle_enabled:
            for decision in decisions:
                if not decision.subtitle_text:
                    decision.subtitle_text = SubtitleEngine.generate_subtitle_text(decision)

        total = sum(d.effective_duration for d in decisions)

        plan = EditPlan(
            name=name,
            style=self.style.name,
            decisions=decisions,
            total_duration=total,
            output_resolution=self.style.output_resolution,
            output_fps=self.style.output_fps,
            output_codec=self.style.output_codec,
        )

        print(f"  剪辑片段: {len(decisions)}")
        print(f"  实际时长: {total:.1f}s")
        self._print_plan_summary(decisions)

        return plan

    def create_multiple_plans(
        self,
        analysis: TimelineAnalysis,
        style_names: List[str],
        target_duration: Optional[float] = None,
        variations_per_style: int = 1,
    ) -> List[EditPlan]:
        plans = []

        for style_name in style_names:
            for v in range(variations_per_style):
                editor = AutoEditor(style_name)
                plan_name = f"{editor.style.display_name}_v{v+1}"
                plan = editor.create_edit_plan(
                    analysis,
                    target_duration=target_duration,
                    plan_name=plan_name,
                )
                plans.append(plan)

        return plans

    def save_plan(self, plan: EditPlan, output_path: str):
        data = plan.to_dict()
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"💾 剪辑方案已保存: {output_path}")

    def _print_plan_summary(self, decisions: List[EditDecision]):
        print(f"\n  {'─'*50}")
        print(f"  {'序号':>4} | {'来源':>6} | {'时间':>12} | {'速度':>5} | {'转场':>8} | {'缩放':>8}")
        print(f"  {'─'*50}")

        for i, d in enumerate(decisions):
            seg = d.segment
            time_range = f"{seg.start_time:.1f}-{seg.end_time:.1f}s"
            zoom = f"{d.zoom_start:.1f}→{d.zoom_end:.1f}"
            print(
                f"  {i+1:>4} | 镜头{seg.index:>2} | {time_range:>12} | "
                f"{d.speed:.2f}x | {d.transition_in:>8} | {zoom:>8}"
            )

        print(f"  {'─'*50}\n")
