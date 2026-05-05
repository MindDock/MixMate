import numpy as np
from typing import List, Tuple, Optional
from pathlib import Path
import subprocess
import json
import tempfile
import os


class AudioAnalyzer:
    """
    音频分析器 - 节拍检测、能量分析、语音/音乐分类
    使用 librosa 进行音频特征提取
    """

    def __init__(
        self,
        beat_sensitivity: float = 1.0,
        hop_length: int = 512,
        sr: int = 22050,
    ):
        self.beat_sensitivity = beat_sensitivity
        self.hop_length = hop_length
        self.sr = sr
        self._beat_cache = {}
        self._audio_cache = {}

    def extract_audio(self, video_path: str, output_path: Optional[str] = None) -> str:
        if output_path is None:
            tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            output_path = tmp.name
            tmp.close()

        cmd = [
            "ffmpeg", "-y", "-i", video_path,
            "-vn", "-acodec", "pcm_s16le",
            "-ar", str(self.sr), "-ac", "1",
            output_path
        ]
        result = subprocess.run(cmd, capture_output=True, check=True, timeout=120)
        return output_path

    def detect_beats(self, audio_path: str) -> List[float]:
        if audio_path in self._beat_cache:
            return self._beat_cache[audio_path]

        try:
            import librosa
        except ImportError:
            beats = self._detect_beats_simple(audio_path)
            self._beat_cache[audio_path] = beats
            return beats

        y, sr = librosa.load(audio_path, sr=self.sr)
        tempo, beat_frames = librosa.beat.beat_track(
            y=y, sr=sr, hop_length=self.hop_length,
            units="frames"
        )
        beat_times = librosa.frames_to_time(beat_frames, sr=sr, hop_length=self.hop_length)
        beats = [float(t) for t in beat_times]
        self._beat_cache[audio_path] = beats
        return beats

    def _detect_beats_simple(self, audio_path: str) -> List[float]:
        try:
            from scipy.io import wavfile
            from scipy.signal import find_peaks
        except ImportError:
            return []

        sr, data = wavfile.read(audio_path)
        if data.ndim > 1:
            data = data.mean(axis=1)

        frame_size = self.hop_length
        n_frames = len(data) // frame_size
        energy = np.zeros(n_frames)

        for i in range(n_frames):
            frame = data[i * frame_size : (i + 1) * frame_size]
            energy[i] = np.sqrt(np.mean(frame.astype(float) ** 2))

        diff = np.diff(energy)
        diff[diff < 0] = 0

        threshold = np.mean(diff) + np.std(diff) * self.beat_sensitivity
        peaks, _ = find_peaks(diff, height=threshold, distance=sr // frame_size // 2)

        beat_times = [float(p * frame_size / sr) for p in peaks]
        return beat_times

    def compute_energy_profile(
        self,
        audio_path: str,
        frame_duration: float = 0.1,
    ) -> List[Tuple[float, float]]:
        try:
            from scipy.io import wavfile
        except ImportError:
            return []

        sr, data = wavfile.read(audio_path)
        if data.ndim > 1:
            data = data.mean(axis=1)

        frame_size = int(sr * frame_duration)
        n_frames = len(data) // frame_size
        profile = []

        for i in range(n_frames):
            frame = data[i * frame_size : (i + 1) * frame_size]
            rms = np.sqrt(np.mean(frame.astype(float) ** 2))
            time = i * frame_duration
            profile.append((time, float(rms)))

        return profile

    def detect_speech_segments(
        self,
        audio_path: str,
        min_duration: float = 0.3,
        energy_threshold: float = 0.02,
    ) -> List[Tuple[float, float]]:
        try:
            from scipy.io import wavfile
        except ImportError:
            return []

        sr, data = wavfile.read(audio_path)
        if data.ndim > 1:
            data = data.mean(axis=1)

        frame_duration = 0.02
        frame_size = int(sr * frame_duration)
        n_frames = len(data) // frame_size

        is_speech = []
        for i in range(n_frames):
            frame = data[i * frame_size : (i + 1) * frame_size]
            rms = np.sqrt(np.mean(frame.astype(float) ** 2))
            is_speech.append(rms > energy_threshold)

        segments = []
        in_segment = False
        start = 0.0

        for i, speech in enumerate(is_speech):
            t = i * frame_duration
            if speech and not in_segment:
                start = t
                in_segment = True
            elif not speech and in_segment:
                duration = t - start
                if duration >= min_duration:
                    segments.append((start, t))
                in_segment = False

        if in_segment:
            segments.append((start, n_frames * frame_duration))

        return segments

    def analyze_segment_audio(
        self,
        audio_path: str,
        start_time: float,
        end_time: float,
        global_beats: Optional[List[float]] = None,
    ) -> Tuple[float, bool, bool, List[float]]:
        try:
            from scipy.io import wavfile
        except ImportError:
            return 0.0, False, False, []

        sr, data = wavfile.read(audio_path)
        if data.ndim > 1:
            data = data.mean(axis=1)

        start_sample = int(start_time * sr)
        end_sample = int(end_time * sr)
        start_sample = max(0, start_sample)
        end_sample = min(len(data), end_sample)

        segment_data = data[start_sample:end_sample].astype(float)
        if len(segment_data) == 0:
            return 0.0, False, False, []

        rms = float(np.sqrt(np.mean(segment_data ** 2)))
        normalized_rms = min(rms / 32768.0, 1.0)

        has_speech = normalized_rms > 0.02
        has_music = normalized_rms > 0.05

        if global_beats is not None:
            segment_beats = [b for b in global_beats if start_time <= b <= end_time]
        else:
            segment_beats = [b for b in self.detect_beats(audio_path) if start_time <= b <= end_time]

        return normalized_rms, has_speech, has_music, segment_beats

    def get_video_info(self, video_path: str) -> dict:
        cmd = [
            "ffprobe", "-v", "quiet",
            "-print_format", "json",
            "-show_format", "-show_streams",
            video_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return json.loads(result.stdout)
