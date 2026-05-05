from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from pathlib import Path


@dataclass
class StyleConfig:
    name: str
    display_name: str
    description: str
    target_duration: float = 15.0
    min_clip_duration: float = 0.3
    max_clip_duration: float = 3.0
    preferred_clip_duration: float = 1.0
    cut_style: str = "beat"
    transition_type: str = "cut"
    transition_duration: float = 0.2
    speed_range: tuple = (0.8, 1.5)
    zoom_range: tuple = (1.0, 1.3)
    filter_name: str = ""
    color_grade: str = ""
    letterbox: bool = False
    subtitle_style: str = ""
    subtitle_enabled: bool = False
    music_mix: bool = False
    prefer_high_motion: bool = False
    prefer_stable: bool = False
    prefer_speech: bool = False
    beat_sync: bool = False
    speed_ramp: bool = False
    output_resolution: tuple = (1080, 1920)
    output_fps: float = 30.0
    output_codec: str = "libx264"
    output_bitrate: str = "8M"
    metadata: Dict[str, Any] = field(default_factory=dict)


STYLES: Dict[str, StyleConfig] = {
    "tiktok_flash": StyleConfig(
        name="tiktok_flash",
        display_name="抖音快闪",
        description="快节奏卡点剪辑，适合15-30秒短视频",
        target_duration=15.0,
        min_clip_duration=0.2,
        max_clip_duration=1.5,
        preferred_clip_duration=0.5,
        cut_style="beat",
        transition_type="glitch",
        transition_duration=0.1,
        speed_range=(1.0, 2.0),
        zoom_range=(1.0, 1.5),
        filter_name="vibrant",
        subtitle_style="tiktok",
        subtitle_enabled=True,
        prefer_high_motion=True,
        beat_sync=True,
        speed_ramp=True,
        output_resolution=(1080, 1920),
        output_fps=30.0,
        output_bitrate="8M",
    ),
    "cinematic": StyleConfig(
        name="cinematic",
        display_name="电影感",
        description="慢节奏宽画幅，色彩浓郁有氛围感",
        target_duration=30.0,
        min_clip_duration=1.5,
        max_clip_duration=5.0,
        preferred_clip_duration=3.0,
        cut_style="flow",
        transition_type="crossfade",
        transition_duration=0.8,
        speed_range=(0.5, 1.0),
        zoom_range=(1.0, 1.1),
        filter_name="cinematic",
        color_grade="teal_orange",
        letterbox=True,
        subtitle_style="cinematic",
        subtitle_enabled=False,
        prefer_stable=True,
        beat_sync=False,
        output_resolution=(1920, 1080),
        output_fps=24.0,
        output_bitrate="12M",
    ),
    "vlog_light": StyleConfig(
        name="vlog_light",
        display_name="Vlog轻快",
        description="自然流畅的Vlog风格，轻快节奏",
        target_duration=30.0,
        min_clip_duration=0.8,
        max_clip_duration=4.0,
        preferred_clip_duration=2.0,
        cut_style="natural",
        transition_type="dissolve",
        transition_duration=0.3,
        speed_range=(0.9, 1.3),
        zoom_range=(1.0, 1.2),
        filter_name="warm",
        subtitle_style="vlog",
        subtitle_enabled=True,
        prefer_speech=True,
        prefer_stable=True,
        beat_sync=False,
        output_resolution=(1080, 1920),
        output_fps=30.0,
        output_bitrate="6M",
    ),
    "sports_hype": StyleConfig(
        name="sports_hype",
        display_name="运动燃剪",
        description="高燃运动混剪，速度感拉满",
        target_duration=20.0,
        min_clip_duration=0.15,
        max_clip_duration=2.0,
        preferred_clip_duration=0.6,
        cut_style="beat",
        transition_type="whip",
        transition_duration=0.08,
        speed_range=(0.3, 2.5),
        zoom_range=(1.0, 1.8),
        filter_name="high_contrast",
        subtitle_style="impact",
        subtitle_enabled=True,
        prefer_high_motion=True,
        beat_sync=True,
        speed_ramp=True,
        output_resolution=(1080, 1920),
        output_fps=60.0,
        output_bitrate="10M",
    ),
    "chill_aesthetic": StyleConfig(
        name="chill_aesthetic",
        display_name="氛围慢调",
        description="慢节奏氛围感，适合风景/日常",
        target_duration=30.0,
        min_clip_duration=2.0,
        max_clip_duration=6.0,
        preferred_clip_duration=3.5,
        cut_style="flow",
        transition_type="crossfade",
        transition_duration=1.0,
        speed_range=(0.5, 0.9),
        zoom_range=(1.0, 1.05),
        filter_name="film_grain",
        color_grade="pastel",
        letterbox=False,
        subtitle_style="minimal",
        subtitle_enabled=False,
        prefer_stable=True,
        beat_sync=False,
        output_resolution=(1080, 1920),
        output_fps=24.0,
        output_bitrate="8M",
    ),
    "music_video": StyleConfig(
        name="music_video",
        display_name="MV卡点",
        description="音乐视频风格，严格卡点",
        target_duration=30.0,
        min_clip_duration=0.15,
        max_clip_duration=2.0,
        preferred_clip_duration=0.5,
        cut_style="beat",
        transition_type="flash",
        transition_duration=0.05,
        speed_range=(0.5, 2.0),
        zoom_range=(1.0, 1.6),
        filter_name="vibrant",
        subtitle_style="lyrics",
        subtitle_enabled=True,
        prefer_high_motion=True,
        beat_sync=True,
        speed_ramp=True,
        output_resolution=(1080, 1920),
        output_fps=30.0,
        output_bitrate="10M",
    ),
}


def get_style(name: str) -> StyleConfig:
    if name not in STYLES:
        available = ", ".join(STYLES.keys())
        raise ValueError(f"未知风格 '{name}'，可用风格: {available}")
    return STYLES[name]


def list_styles() -> List[Dict[str, str]]:
    return [
        {
            "name": s.name,
            "display_name": s.display_name,
            "description": s.description,
            "target_duration": str(s.target_duration),
        }
        for s in STYLES.values()
    ]


def create_custom_style(name: str, display_name: str, base_style: str = "vlog_light", **overrides) -> StyleConfig:
    base = get_style(base_style)
    config_dict = {
        "name": name,
        "display_name": display_name,
        "description": overrides.pop("description", f"基于 {base.display_name} 的自定义风格"),
    }
    for k, v in base.__dict__.items():
        if k not in config_dict:
            config_dict[k] = overrides.pop(k, v)
    return StyleConfig(**config_dict)
