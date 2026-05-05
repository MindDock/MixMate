import os
import json
import tempfile
from typing import List, Optional
from .base import SpeechProvider, SpeechSegment


class WhisperSpeechProvider(SpeechProvider):
    """
    OpenAI Whisper 语音转文字 Provider
    支持 API 调用和本地模型两种方式
    """

    def __init__(
        self,
        mode: str = "local",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model_size: str = "base",
        language: str = "zh",
    ):
        self.mode = mode
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.base_url = base_url or os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
        self.model_size = model_size
        self.language = language
        self._local_model = None

    def is_available(self) -> bool:
        if self.mode == "api":
            return bool(self.api_key)
        else:
            try:
                import whisper
                return True
            except ImportError:
                return False

    def transcribe(self, audio_path: str) -> List[SpeechSegment]:
        if self.mode == "api":
            return self._transcribe_api(audio_path)
        else:
            return self._transcribe_local(audio_path)

    def _transcribe_local(self, audio_path: str) -> List[SpeechSegment]:
        try:
            import whisper
        except ImportError:
            raise ImportError("请安装 whisper: pip install openai-whisper")

        if self._local_model is None:
            print(f"  🤖 加载 Whisper 模型: {self.model_size}...")
            self._local_model = whisper.load_model(self.model_size)

        print(f"  🎙️ 语音识别中...")
        result = self._local_model.transcribe(
            audio_path,
            language=self.language,
            fp16=False,
        )

        segments = []
        for seg in result.get("segments", []):
            segments.append(SpeechSegment(
                start_time=seg["start"],
                end_time=seg["end"],
                text=seg["text"].strip(),
                language=result.get("language", self.language),
                confidence=seg.get("avg_logprob", 0.0),
            ))

        return segments

    def _transcribe_api(self, audio_path: str) -> List[SpeechSegment]:
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("请安装 openai: pip install openai")

        client = OpenAI(api_key=self.api_key, base_url=self.base_url)

        with open(audio_path, "rb") as f:
            response = client.audio.transcriptions.create(
                model="whisper-1",
                file=f,
                response_format="verbose_json",
                timestamp_granularities=["segment"],
                language=self.language,
            )

        segments = []
        for seg in response.segments:
            segments.append(SpeechSegment(
                start_time=seg.start,
                end_time=seg.end,
                text=seg.text.strip(),
                language=self.language,
                confidence=0.9,
            ))

        return segments


class SimpleSpeechProvider(SpeechProvider):
    """
    简单语音检测 Provider - 基于能量阈值
    系统默认回退方案，只能检测有声/无声，不能识别内容
    """

    def is_available(self) -> bool:
        return True

    def transcribe(self, audio_path: str) -> List[SpeechSegment]:
        try:
            from scipy.io import wavfile
            import numpy as np
        except ImportError:
            return []

        try:
            sr, data = wavfile.read(audio_path)
        except Exception:
            return []

        if data.ndim > 1:
            data = data.mean(axis=1)

        frame_duration = 0.5
        frame_size = int(sr * frame_duration)
        segments = []

        for i in range(0, len(data) - frame_size, frame_size):
            frame = data[i:i + frame_size].astype(float)
            rms = np.sqrt(np.mean(frame ** 2))
            if rms > 500:
                segments.append(SpeechSegment(
                    start_time=i / sr,
                    end_time=(i + frame_size) / sr,
                    text="[有声片段]",
                    confidence=0.3,
                ))

        return segments
