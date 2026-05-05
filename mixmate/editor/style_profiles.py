from typing import Dict, List, Any
from ..config import StyleConfig, STYLES, get_style


class StyleProfiles:
    """
    风格配置管理器 - 将风格配置转化为具体的剪辑策略
    """

    @staticmethod
    def get_cut_strategy(style: StyleConfig) -> Dict[str, Any]:
        if style.cut_style == "beat":
            return {
                "mode": "beat_sync",
                "snap_to_beat": True,
                "beat_division": 1,
                "allow_offbeat": False,
            }
        elif style.cut_style == "flow":
            return {
                "mode": "flow",
                "snap_to_beat": False,
                "min_overlap": 0.5,
                "prefer_smooth": True,
            }
        elif style.cut_style == "natural":
            return {
                "mode": "natural",
                "snap_to_beat": False,
                "respect_speech": True,
                "pause_between": 0.1,
            }
        return {"mode": "basic"}

    @staticmethod
    def get_transition_strategy(style: StyleConfig) -> Dict[str, Any]:
        strategies = {
            "cut": {"type": "cut", "duration": 0},
            "crossfade": {"type": "crossfade", "duration": style.transition_duration},
            "dissolve": {"type": "dissolve", "duration": style.transition_duration},
            "glitch": {
                "type": "glitch",
                "duration": style.transition_duration,
                "intensity": 0.8,
                "rgb_split": True,
            },
            "whip": {
                "type": "whip",
                "duration": style.transition_duration,
                "direction": "auto",
                "blur_amount": 12,
            },
            "flash": {
                "type": "flash",
                "duration": style.transition_duration,
                "color": "white",
                "intensity": 0.9,
            },
        }
        return strategies.get(style.transition_type, {"type": "cut", "duration": 0})

    @staticmethod
    def get_speed_strategy(style: StyleConfig) -> Dict[str, Any]:
        return {
            "base_speed": 1.0,
            "min_speed": style.speed_range[0],
            "max_speed": style.speed_range[1],
            "speed_ramp": style.speed_ramp,
            "ramp_curve": "ease_in_out",
            "high_motion_slowdown": style.speed_ramp,
            "slowmo_factor": 0.3,
        }

    @staticmethod
    def get_zoom_strategy(style: StyleConfig) -> Dict[str, Any]:
        return {
            "min_zoom": style.zoom_range[0],
            "max_zoom": style.zoom_range[1],
            "zoom_on_beat": style.beat_sync,
            "zoom_on_action": style.prefer_high_motion,
            "ken_burns": style.cut_style == "flow",
            "zoom_speed": 0.5,
        }

    @staticmethod
    def get_filter_strategy(style: StyleConfig) -> Dict[str, Any]:
        filters = {
            "vibrant": {
                "saturation": 1.3,
                "contrast": 1.1,
                "brightness": 0.05,
            },
            "cinematic": {
                "saturation": 0.85,
                "contrast": 1.2,
                "brightness": -0.02,
                "shadows_tint": "teal",
                "highlights_tint": "orange",
            },
            "warm": {
                "saturation": 1.1,
                "contrast": 1.05,
                "temperature": 0.15,
                "brightness": 0.03,
            },
            "high_contrast": {
                "saturation": 1.2,
                "contrast": 1.4,
                "brightness": 0.0,
            },
            "film_grain": {
                "saturation": 0.9,
                "contrast": 1.1,
                "grain_amount": 0.04,
                "vignette": 0.3,
            },
            "pastel": {
                "saturation": 0.8,
                "contrast": 0.9,
                "brightness": 0.1,
                "temperature": 0.05,
            },
        }
        return filters.get(style.filter_name, {})

    @staticmethod
    def get_subtitle_strategy(style: StyleConfig) -> Dict[str, Any]:
        styles_map = {
            "tiktok": {
                "font_size": 24,
                "position": "bottom_center",
                "bg_color": "black",
                "text_color": "white",
                "outline": True,
                "animation": "pop",
                "bold": True,
            },
            "cinematic": {
                "font_size": 18,
                "position": "bottom_center",
                "bg_color": "transparent",
                "text_color": "white",
                "outline": True,
                "animation": "fade",
                "italic": True,
            },
            "vlog": {
                "font_size": 20,
                "position": "bottom_left",
                "bg_color": "semi_black",
                "text_color": "white",
                "outline": False,
                "animation": "slide",
            },
            "impact": {
                "font_size": 32,
                "position": "center",
                "bg_color": "transparent",
                "text_color": "yellow",
                "outline": True,
                "animation": "shake",
                "bold": True,
            },
            "minimal": {
                "font_size": 16,
                "position": "bottom_center",
                "bg_color": "transparent",
                "text_color": "white",
                "outline": True,
                "animation": "fade",
            },
            "lyrics": {
                "font_size": 22,
                "position": "center",
                "bg_color": "semi_black",
                "text_color": "white",
                "outline": True,
                "animation": "word_by_word",
                "bold": True,
            },
        }
        return styles_map.get(style.subtitle_style, {})

    @staticmethod
    def get_full_profile(style_name: str) -> Dict[str, Any]:
        style = get_style(style_name)
        return {
            "style": style,
            "cut": StyleProfiles.get_cut_strategy(style),
            "transition": StyleProfiles.get_transition_strategy(style),
            "speed": StyleProfiles.get_speed_strategy(style),
            "zoom": StyleProfiles.get_zoom_strategy(style),
            "filter": StyleProfiles.get_filter_strategy(style),
            "subtitle": StyleProfiles.get_subtitle_strategy(style),
        }
