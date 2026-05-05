from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class SceneUnderstanding:
    description: str = ""
    actions: List[str] = field(default_factory=list)
    objects: List[str] = field(default_factory=list)
    mood: str = ""
    scene_type: str = ""
    people_count: int = 0
    is_dancing: bool = False
    is_sports: bool = False
    is_talking: bool = False
    is_walking: bool = False
    is_closeup: bool = False
    is_landscape: bool = False
    is_group_activity: bool = False
    narrative_role: str = ""
    suggested_cut_style: str = ""
    confidence: float = 0.0
    raw_response: str = ""


@dataclass
class SpeechSegment:
    start_time: float
    end_time: float
    text: str
    language: str = ""
    confidence: float = 0.0


@dataclass
class AIAnalysisResult:
    scene: SceneUnderstanding = field(default_factory=SceneUnderstanding)
    speech: List[SpeechSegment] = field(default_factory=list)
    full_transcript: str = ""
    narrative_structure: str = ""
    suggested_highlights: List[Dict[str, Any]] = field(default_factory=list)


class VisionProvider(ABC):
    @abstractmethod
    def analyze_frame(self, image_base64: str, prompt: str) -> SceneUnderstanding:
        pass

    @abstractmethod
    def analyze_segment(self, frames_base64: List[str], prompt: str) -> SceneUnderstanding:
        pass

    @abstractmethod
    def is_available(self) -> bool:
        pass


class SpeechProvider(ABC):
    @abstractmethod
    def transcribe(self, audio_path: str) -> List[SpeechSegment]:
        pass

    @abstractmethod
    def is_available(self) -> bool:
        pass


class NarrativeProvider(ABC):
    @abstractmethod
    def plan_narrative(self, scenes: List[Dict], style: str, duration: float) -> Dict[str, Any]:
        pass

    @abstractmethod
    def is_available(self) -> bool:
        pass
