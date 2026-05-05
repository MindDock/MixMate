from typing import Dict, List, Any, Optional
from ..models import EditDecision


class EffectEngine:
    """
    特效引擎 - 生成 FFmpeg 滤镜链
    支持滤镜、调色、缩放、变速、转场等
    """

    FILTER_PRESETS: Dict[str, Dict[str, Any]] = {
        "vibrant": {
            "eq": "eq=saturation=1.3:contrast=1.1:brightness=0.05",
            "extra": "",
        },
        "cinematic": {
            "eq": "eq=saturation=0.85:contrast=1.2:brightness=-0.02",
            "extra": "curves=preset=darker",
        },
        "warm": {
            "eq": "eq=saturation=1.1:contrast=1.05:brightness=0.03",
            "extra": "colorbalance=rs=0.05:gs=0.02:bs=-0.03",
        },
        "high_contrast": {
            "eq": "eq=saturation=1.2:contrast=1.4:brightness=0.0",
            "extra": "",
        },
        "film_grain": {
            "eq": "eq=saturation=0.9:contrast=1.1:brightness=0.0",
            "extra": "noise=alls=4:allf=t+u,vignette=angle=0.3",
        },
        "pastel": {
            "eq": "eq=saturation=0.8:contrast=0.9:brightness=0.1",
            "extra": "colorbalance=rs=0.03:gs=0.03:bs=0.05",
        },
    }

    TRANSITION_FILTERS: Dict[str, str] = {
        "cut": "",
        "crossfade": "xfade=transition=fade:duration={dur}:offset={offset}",
        "dissolve": "xfade=transition=dissolve:duration={dur}:offset={offset}",
        "glitch": "xfade=transition=slideleft:duration={dur}:offset={offset}",
        "whip": "xfade=transition=slidedown:duration={dur}:offset={offset}",
        "flash": "xfade=transition=fadeblack:duration={dur}:offset={offset}",
    }

    @classmethod
    def build_filter_chain(
        cls,
        decision: EditDecision,
        output_width: int = 1080,
        output_height: int = 1920,
        letterbox: bool = False,
    ) -> List[str]:
        filters = []

        filters.extend(cls._build_scale_filter(decision, output_width, output_height))
        filters.extend(cls._build_zoom_filter(decision))
        filters.extend(cls._build_speed_filter(decision))
        filters.extend(cls._build_color_filter(decision))
        filters.extend(cls._build_letterbox_filter(letterbox, output_width, output_height))

        return [f for f in filters if f]

    @classmethod
    def _build_scale_filter(
        cls,
        decision: EditDecision,
        out_w: int,
        out_h: int,
    ) -> List[str]:
        return [f"scale={out_w}:{out_h}:force_original_aspect_ratio=increase,crop={out_w}:{out_h}"]

    @classmethod
    def _build_zoom_filter(cls, decision: EditDecision) -> List[str]:
        if decision.zoom_start == 1.0 and decision.zoom_end == 1.0:
            return []

        if decision.zoom_start != decision.zoom_end:
            return [
                f"zoompan=z='if(lte(zoom,{decision.zoom_start}),{decision.zoom_start},max({decision.zoom_start},min({decision.zoom_end},zoom+({decision.zoom_end}-{decision.zoom_start})/on)))':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={1080}x{1920}"
            ]
        elif decision.zoom_start > 1.0:
            return [f"zoompan=z={decision.zoom_start}:d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={1080}x{1920}"]

        return []

    @classmethod
    def _build_speed_filter(cls, decision: EditDecision) -> List[str]:
        if decision.speed == 1.0:
            return []
        pts = 1.0 / decision.speed
        return [f"setpts={pts:.4f}*PTS"]

    @classmethod
    def _build_color_filter(cls, decision: EditDecision) -> List[str]:
        if not decision.filter_name or decision.filter_name not in cls.FILTER_PRESETS:
            return []

        preset = cls.FILTER_PRESETS[decision.filter_name]
        filters = []
        if preset["eq"]:
            filters.append(preset["eq"])
        if preset["extra"]:
            filters.append(preset["extra"])
        return filters

    @classmethod
    def _build_letterbox_filter(
        cls,
        enabled: bool,
        width: int,
        height: int,
    ) -> List[str]:
        if not enabled:
            return []
        bar_h = int(height * 0.1)
        return [
            f"pad={width}:{height + bar_h * 2}:0:{bar_h}:black"
        ]

    @classmethod
    def build_transition_xfade(
        cls,
        transition_type: str,
        duration: float,
        offset: float,
    ) -> str:
        template = cls.TRANSITION_FILTERS.get(transition_type, "")
        if not template:
            return ""
        return template.format(dur=duration, offset=offset)

    @classmethod
    def get_audio_filter(cls, decision: EditDecision) -> str:
        speed = decision.speed
        volume = decision.volume

        filters = []
        if speed != 1.0:
            atempo = 1.0 / speed
            if 0.5 <= atempo <= 2.0:
                filters.append(f"atempo={atempo:.4f}")
            elif atempo < 0.5:
                filters.append(f"atempo=0.5,atempo={atempo / 0.5:.4f}")
            else:
                filters.append(f"atempo=2.0,atempo={atempo / 2.0:.4f}")

        if volume != 1.0:
            filters.append(f"volume={volume:.2f}")

        return ",".join(filters) if filters else ""
