from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any
from pathlib import Path
import numpy as np


def _f(v):
    try:
        return round(float(v), 3)
    except (TypeError, ValueError):
        return v


class ShotType(Enum):
    STATIC = "static"
    PAN = "pan"
    TILT = "tilt"
    ZOOM = "zoom"
    TRACKING = "tracking"
    HANDHELD = "handheld"
    TRANSITION = "transition"


class ContentTag(Enum):
    DANCE = "dance"
    SPORTS = "sports"
    TALKING = "talking"
    WALKING = "walking"
    CLOSEUP = "closeup"
    LANDSCAPE = "landscape"
    GROUP = "group"
    SOLO = "solo"
    ACTION = "action"
    EMOTION = "emotion"
    INTRO = "intro"
    OUTRO = "outro"
    BROLL = "broll"
    SILENCE = "silence"
    MUSIC = "music"


class MotionIntensity(Enum):
    STILL = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    EXTREME = 4


@dataclass
class ShotSegment:
    index: int
    start_time: float
    end_time: float
    start_frame: int
    end_frame: int
    shot_type: ShotType = ShotType.STATIC
    motion_intensity: MotionIntensity = MotionIntensity.STILL
    motion_score: float = 0.0
    content_tags: List[ContentTag] = field(default_factory=list)
    brightness: float = 0.0
    color_dominant: tuple = (0, 0, 0)
    sharpness: float = 0.0
    stability_score: float = 1.0
    quality_score: float = 0.5
    audio_energy: float = 0.0
    has_speech: bool = False
    has_music: bool = False
    beat_positions: List[float] = field(default_factory=list)
    source_file: str = ""
    thumbnail_path: Optional[str] = None

    @property
    def duration(self) -> float:
        return self.end_time - self.start_time

    @property
    def frame_count(self) -> int:
        return self.end_frame - self.start_frame

    def to_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "start_time": _f(self.start_time),
            "end_time": _f(self.end_time),
            "duration": _f(self.duration),
            "shot_type": self.shot_type.value,
            "motion_intensity": self.motion_intensity.value,
            "motion_score": _f(self.motion_score),
            "content_tags": [t.value for t in self.content_tags],
            "brightness": _f(self.brightness),
            "sharpness": _f(self.sharpness),
            "stability_score": _f(self.stability_score),
            "quality_score": _f(self.quality_score),
            "audio_energy": _f(self.audio_energy),
            "has_speech": self.has_speech,
            "has_music": self.has_music,
            "beat_count": len(self.beat_positions),
            "source_file": self.source_file,
        }


@dataclass
class VideoSource:
    file_path: str
    duration: float = 0.0
    fps: float = 0.0
    width: int = 0
    height: int = 0
    codec: str = ""
    audio_codec: str = ""
    segments: List[ShotSegment] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_path": self.file_path,
            "duration": _f(self.duration),
            "fps": _f(self.fps),
            "resolution": f"{self.width}x{self.height}",
            "codec": self.codec,
            "audio_codec": self.audio_codec,
            "segment_count": len(self.segments),
            "segments": [s.to_dict() for s in self.segments],
        }


@dataclass
class TimelineAnalysis:
    sources: List[VideoSource] = field(default_factory=list)
    all_segments: List[ShotSegment] = field(default_factory=list)
    global_beats: List[float] = field(default_factory=list)
    total_duration: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_count": len(self.sources),
            "total_duration": _f(self.total_duration),
            "total_segments": len(self.all_segments),
            "global_beat_count": len(self.global_beats),
            "sources": [s.to_dict() for s in self.sources],
            "segments": [s.to_dict() for s in self.all_segments],
        }

    def get_high_energy_segments(self, threshold: float = 0.6) -> List[ShotSegment]:
        return [s for s in self.all_segments if s.motion_score >= threshold or s.audio_energy >= threshold]

    def get_segments_by_tag(self, tag: ContentTag) -> List[ShotSegment]:
        return [s for s in self.all_segments if tag in s.content_tags]

    def get_stable_segments(self, min_stability: float = 0.7) -> List[ShotSegment]:
        return [s for s in self.all_segments if s.stability_score >= min_stability]

    def get_music_segments(self) -> List[ShotSegment]:
        return [s for s in self.all_segments if s.has_music]

    def get_speech_segments(self) -> List[ShotSegment]:
        return [s for s in self.all_segments if s.has_speech]


@dataclass
class EditDecision:
    segment: ShotSegment
    trim_start: float = 0.0
    trim_end: float = 0.0
    speed: float = 1.0
    transition_in: str = "cut"
    transition_out: str = "cut"
    transition_duration: float = 0.3
    filter_name: str = ""
    zoom_start: float = 1.0
    zoom_end: float = 1.0
    subtitle_text: str = ""
    volume: float = 1.0
    music_track: str = ""

    @property
    def effective_duration(self) -> float:
        raw = self.segment.duration - self.trim_start - self.trim_end
        return raw / self.speed if self.speed > 0 else raw


@dataclass
class EditPlan:
    name: str
    style: str
    decisions: List[EditDecision] = field(default_factory=list)
    total_duration: float = 0.0
    output_resolution: tuple = (1080, 1920)
    output_fps: float = 30.0
    output_codec: str = "libx264"
    background_music: str = ""
    watermark: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "style": self.style,
            "total_duration": _f(self.total_duration),
            "clip_count": len(self.decisions),
            "output_resolution": f"{self.output_resolution[0]}x{self.output_resolution[1]}",
            "output_fps": self.output_fps,
            "clips": [
                {
                    "source": d.segment.source_file,
                    "segment_index": d.segment.index,
                    "start": _f(d.segment.start_time + d.trim_start),
                    "end": _f(d.segment.end_time - d.trim_end),
                    "speed": d.speed,
                    "transition_in": d.transition_in,
                    "transition_out": d.transition_out,
                    "filter": d.filter_name,
                    "zoom": f"{d.zoom_start:.1f}->{d.zoom_end:.1f}",
                    "subtitle": d.subtitle_text,
                }
                for d in self.decisions
            ],
        }


@dataclass
class RenderResult:
    output_path: str
    duration: float
    file_size: int
    style: str
    plan_name: str
