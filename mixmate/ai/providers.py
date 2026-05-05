import os
import json
import base64
from typing import Optional, Dict, Any, List
from pathlib import Path
from dataclasses import dataclass, field

from .base import VisionProvider, SpeechProvider, NarrativeProvider, SceneUnderstanding, SpeechSegment
from .vision import OpenAIVisionProvider, LocalVisionProvider, RuleBasedVisionProvider
from .speech import WhisperSpeechProvider, SimpleSpeechProvider
from .narrative import OpenAINarrativeProvider, RuleBasedNarrativeProvider


_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(_PROJECT_DIR, "ai_config.json")

DEFAULT_CONFIG = {
    "vision": {
        "provider": "local",
        "openai": {
            "api_key": "",
            "model": "gpt-4o",
            "base_url": "https://api.openai.com/v1",
        },
        "local": {
            "model": "moondream:v2",
            "ollama_url": "http://localhost:11434",
        },
    },
    "speech": {
        "provider": "simple",
        "whisper": {
            "mode": "local",
            "model_size": "base",
            "language": "zh",
        },
        "openai": {
            "api_key": "",
            "base_url": "https://api.openai.com/v1",
        },
    },
    "narrative": {
        "provider": "rule_based",
        "openai": {
            "api_key": "",
            "model": "gpt-4o",
            "base_url": "https://api.openai.com/v1",
        },
    },
    "analysis": {
        "vision_sample_frames": 3,
        "vision_max_segments": 30,
        "speech_enabled": True,
        "narrative_enabled": True,
    },
}


def load_config() -> Dict[str, Any]:
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            saved = json.load(f)
        config = _deep_merge(DEFAULT_CONFIG.copy(), saved)
        return config
    return DEFAULT_CONFIG.copy()


def save_config(config: Dict[str, Any]):
    try:
        config_dir = os.path.dirname(CONFIG_PATH)
        os.makedirs(config_dir, exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except PermissionError:
        import tempfile
        alt_dir = os.path.join(tempfile.gettempdir(), "mixmate")
        os.makedirs(alt_dir, exist_ok=True)
        alt_path = os.path.join(alt_dir, "ai_config.json")
        with open(alt_path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)


def _deep_merge(base: dict, override: dict) -> dict:
    for k, v in override.items():
        if k in base and isinstance(base[k], dict) and isinstance(v, dict):
            base[k] = _deep_merge(base[k], v)
        else:
            base[k] = v
    return base


class AIProviderFactory:
    """
    AI Provider 工厂 - 根据配置创建对应的 Provider 实例
    """

    @staticmethod
    def create_vision_provider(config: Optional[Dict] = None) -> VisionProvider:
        if config is None:
            config = load_config().get("vision", {})

        provider_name = config.get("provider", "rule_based")

        if provider_name == "openai":
            openai_cfg = config.get("openai", {})
            api_key = openai_cfg.get("api_key", "") or os.environ.get("OPENAI_API_KEY", "")
            provider = OpenAIVisionProvider(
                api_key=api_key,
                model=openai_cfg.get("model", "gpt-4o"),
                base_url=openai_cfg.get("base_url"),
            )
            if provider.is_available():
                print(f"  🤖 视觉理解: OpenAI {openai_cfg.get('model', 'gpt-4o')}")
                return provider
            else:
                print(f"  ⚠️ OpenAI 不可用，回退到规则引擎")

        elif provider_name == "local":
            local_cfg = config.get("local", {})
            provider = LocalVisionProvider(
                model=local_cfg.get("model", "llava"),
                ollama_url=local_cfg.get("ollama_url", "http://localhost:11434"),
            )
            if provider.is_available():
                resolved = provider._resolve_model()
                print(f"  🤖 视觉理解: 本地模型 {resolved}")
                return provider
            else:
                print(f"  ⚠️ 本地模型 {local_cfg.get('model', 'llava')} 不可用（Ollama 未运行或模型未安装），回退到规则引擎")

        print(f"  📐 视觉理解: 规则引擎（传统CV算法）")
        return RuleBasedVisionProvider()

    @staticmethod
    def create_speech_provider(config: Optional[Dict] = None) -> SpeechProvider:
        if config is None:
            config = load_config().get("speech", {})

        provider_name = config.get("provider", "simple")

        if provider_name == "whisper_local":
            whisper_cfg = config.get("whisper", {})
            provider = WhisperSpeechProvider(
                mode="local",
                model_size=whisper_cfg.get("model_size", "base"),
                language=whisper_cfg.get("language", "zh"),
            )
            if provider.is_available():
                print(f"  🎙️ 语音识别: Whisper 本地 ({whisper_cfg.get('model_size', 'base')})")
                return provider
            else:
                print(f"  ⚠️ Whisper 本地不可用，回退到简单检测")

        elif provider_name == "whisper_api":
            openai_cfg = config.get("openai", {})
            api_key = openai_cfg.get("api_key", "") or os.environ.get("OPENAI_API_KEY", "")
            provider = WhisperSpeechProvider(
                mode="api",
                api_key=api_key,
                base_url=openai_cfg.get("base_url"),
                language=config.get("whisper", {}).get("language", "zh"),
            )
            if provider.is_available():
                print(f"  🎙️ 语音识别: Whisper API")
                return provider
            else:
                print(f"  ⚠️ Whisper API 不可用，回退到简单检测")

        print(f"  🔊 语音识别: 简单能量检测")
        return SimpleSpeechProvider()

    @staticmethod
    def create_narrative_provider(config: Optional[Dict] = None) -> NarrativeProvider:
        if config is None:
            config = load_config().get("narrative", {})

        provider_name = config.get("provider", "rule_based")

        if provider_name == "openai":
            openai_cfg = config.get("openai", {})
            api_key = openai_cfg.get("api_key", "") or os.environ.get("OPENAI_API_KEY", "")
            provider = OpenAINarrativeProvider(
                api_key=api_key,
                model=openai_cfg.get("model", "gpt-4o"),
                base_url=openai_cfg.get("base_url"),
            )
            if provider.is_available():
                print(f"  🧠 叙事规划: OpenAI {openai_cfg.get('model', 'gpt-4o')}")
                return provider
            else:
                print(f"  ⚠️ OpenAI 叙事规划不可用，回退到规则引擎")

        print(f"  📋 叙事规划: 规则引擎")
        return RuleBasedNarrativeProvider()


def encode_frame_to_base64(frame) -> str:
    import cv2
    _, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
    return base64.b64encode(buffer).decode("utf-8")


def extract_segment_frames(
    video_path: str,
    start_frame: int,
    end_frame: int,
    count: int = 3,
) -> List[str]:
    import cv2

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return []

    total = end_frame - start_frame
    step = max(1, total // count)
    frames = []

    for offset in range(0, total, step):
        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame + offset)
        ret, frame = cap.read()
        if ret:
            frames.append(encode_frame_to_base64(frame))
        if len(frames) >= count:
            break

    cap.release()
    return frames
