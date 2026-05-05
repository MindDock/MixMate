import random
from typing import List, Optional, Tuple
from ..models import (
    ShotSegment, EditDecision, TimelineAnalysis,
    ContentTag, MotionIntensity, ShotType,
)
from ..config import StyleConfig
from .style_profiles import StyleProfiles


class CutEngine:
    """
    剪辑决策引擎 - 根据风格配置和素材分析结果，生成剪辑决策列表
    核心逻辑：选片 → 排序 → 裁剪 → 对齐
    """

    def __init__(self, style: StyleConfig):
        self.style = style
        self.profile = StyleProfiles.get_full_profile(style.name)

    def generate_edit_plan(
        self,
        analysis: TimelineAnalysis,
        target_duration: Optional[float] = None,
    ) -> List[EditDecision]:
        duration = target_duration or self.style.target_duration

        candidates = self._select_candidates(analysis)
        if not candidates:
            return []

        ordered = self._order_segments(candidates, analysis)
        trimmed = self._trim_to_duration(ordered, duration)
        decisions = self._apply_style_effects(trimmed, analysis)

        return decisions

    def _select_candidates(self, analysis: TimelineAnalysis) -> List[ShotSegment]:
        segments = list(analysis.all_segments)
        scored = []

        for seg in segments:
            score = self._score_segment(seg)
            scored.append((score, seg))

        scored.sort(key=lambda x: x[0], reverse=True)

        max_segments = max(5, int(self.style.target_duration / self.style.min_clip_duration) * 2)
        candidates = [seg for _, seg in scored[:max_segments]]

        return candidates

    def _score_segment(self, segment: ShotSegment) -> float:
        score = segment.quality_score

        if self.style.prefer_high_motion:
            if segment.motion_intensity in (MotionIntensity.HIGH, MotionIntensity.EXTREME):
                score += 0.3
            elif segment.motion_intensity == MotionIntensity.MEDIUM:
                score += 0.1
        else:
            if segment.motion_intensity == MotionIntensity.STILL:
                score += 0.1

        if self.style.prefer_stable:
            score += segment.stability_score * 0.2

        if self.style.prefer_speech and segment.has_speech:
            score += 0.25

        if self.style.beat_sync and segment.beat_positions:
            score += min(len(segment.beat_positions) * 0.05, 0.2)

        if ContentTag.INTRO in segment.content_tags:
            score += 0.15

        if ContentTag.ACTION in segment.content_tags and self.style.prefer_high_motion:
            score += 0.2

        if ContentTag.LANDSCAPE in segment.content_tags and not self.style.prefer_high_motion:
            score += 0.1

        if segment.duration < self.style.min_clip_duration:
            score -= 0.3

        if segment.sharpness < 0.1:
            score -= 0.2

        return score

    def _order_segments(
        self,
        segments: List[ShotSegment],
        analysis: TimelineAnalysis,
    ) -> List[ShotSegment]:
        if self.style.cut_style == "beat" and analysis.global_beats:
            return self._order_by_beat(segments, analysis.global_beats)
        elif self.style.cut_style == "flow":
            return self._order_by_flow(segments)
        else:
            return self._order_natural(segments)

    def _order_by_beat(
        self,
        segments: List[ShotSegment],
        beats: List[float],
    ) -> List[ShotSegment]:
        if not beats or not segments:
            return segments

        ordered = []
        used = set()
        current_time = 0.0

        for beat_time in beats:
            if beat_time < current_time:
                continue

            best_seg = None
            best_score = -1

            for i, seg in enumerate(segments):
                if i in used:
                    continue
                score = self._score_segment(seg)
                if seg.duration >= self.style.min_clip_duration:
                    score += 0.1

                if score > best_score:
                    best_score = score
                    best_seg = i

            if best_seg is not None:
                ordered.append(segments[best_seg])
                used.add(best_seg)
                current_time = beat_time + self.style.preferred_clip_duration

            if len(used) >= len(segments):
                break

        for i, seg in enumerate(segments):
            if i not in used:
                ordered.append(seg)

        return ordered

    def _order_by_flow(self, segments: List[ShotSegment]) -> List[ShotSegment]:
        ordered = []

        intro_segs = [s for s in segments if ContentTag.INTRO in s.content_tags]
        action_segs = [s for s in segments if ContentTag.ACTION in s.content_tags]
        emotion_segs = [s for s in segments if ContentTag.EMOTION in s.content_tags]
        landscape_segs = [s for s in segments if ContentTag.LANDSCAPE in s.content_tags]
        other_segs = [s for s in segments if s not in intro_segs + action_segs + emotion_segs + landscape_segs]

        ordered.extend(intro_segs)
        ordered.extend(landscape_segs[:1])
        ordered.extend(action_segs)
        ordered.extend(emotion_segs)
        ordered.extend(other_segs)

        return ordered

    def _order_natural(self, segments: List[ShotSegment]) -> List[ShotSegment]:
        return sorted(segments, key=lambda s: s.start_time)

    def _trim_to_duration(
        self,
        segments: List[ShotSegment],
        target_duration: float,
    ) -> List[Tuple[ShotSegment, float, float]]:
        result = []
        total = 0.0

        for seg in segments:
            remaining = target_duration - total
            if remaining <= 0:
                break

            clip_duration = min(
                seg.duration,
                self.style.max_clip_duration,
                remaining,
            )

            if clip_duration < self.style.min_clip_duration:
                continue

            trim_start = 0.0
            trim_end = seg.duration - clip_duration

            if trim_end > 0:
                trim_start = trim_end * 0.3
                trim_end = trim_end * 0.7

            result.append((seg, trim_start, trim_end))
            total += clip_duration

        return result

    def _apply_style_effects(
        self,
        trimmed: List[Tuple[ShotSegment, float, float]],
        analysis: TimelineAnalysis,
    ) -> List[EditDecision]:
        decisions = []
        speed_strategy = self.profile["speed"]
        zoom_strategy = self.profile["zoom"]

        for i, (seg, trim_start, trim_end) in enumerate(trimmed):
            speed = self._compute_speed(seg, speed_strategy, i, len(trimmed))
            zoom_start, zoom_end = self._compute_zoom(seg, zoom_strategy, i, len(trimmed))
            transition_in = self._get_transition(i, "in")
            transition_out = self._get_transition(i, "out")

            decision = EditDecision(
                segment=seg,
                trim_start=trim_start,
                trim_end=trim_end,
                speed=speed,
                transition_in=transition_in,
                transition_out=transition_out,
                transition_duration=self.style.transition_duration,
                filter_name=self.style.filter_name,
                zoom_start=zoom_start,
                zoom_end=zoom_end,
                volume=1.0,
            )

            decisions.append(decision)

        return decisions

    def _compute_speed(
        self,
        segment: ShotSegment,
        strategy: dict,
        index: int,
        total: int,
    ) -> float:
        base = strategy["base_speed"]

        if strategy.get("high_motion_slowdown") and segment.motion_intensity in (
            MotionIntensity.HIGH, MotionIntensity.EXTREME
        ):
            return strategy.get("slowmo_factor", 0.3)

        if strategy.get("speed_ramp"):
            progress = index / max(total - 1, 1)
            if progress < 0.2:
                factor = strategy["min_speed"] + (base - strategy["min_speed"]) * (progress / 0.2)
            elif progress > 0.8:
                factor = base + (strategy["max_speed"] - base) * ((progress - 0.8) / 0.2)
            else:
                factor = base
            return max(strategy["min_speed"], min(strategy["max_speed"], factor))

        return base

    def _compute_zoom(
        self,
        segment: ShotSegment,
        strategy: dict,
        index: int,
        total: int,
    ) -> Tuple[float, float]:
        zoom_start = strategy["min_zoom"]
        zoom_end = strategy["min_zoom"]

        if strategy.get("zoom_on_beat") and segment.beat_positions:
            zoom_end = min(strategy["max_zoom"], zoom_start + 0.2)

        if strategy.get("zoom_on_action") and segment.motion_intensity in (
            MotionIntensity.HIGH, MotionIntensity.EXTREME
        ):
            zoom_end = min(strategy["max_zoom"], zoom_start + 0.3)

        if strategy.get("ken_burns"):
            zoom_end = zoom_start + 0.05

        return zoom_start, zoom_end

    def _get_transition(self, index: int, direction: str) -> str:
        transition_strategy = self.profile["transition"]
        return transition_strategy.get("type", "cut")
