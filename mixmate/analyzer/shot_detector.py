import cv2
import numpy as np
from typing import List, Tuple, Optional
from ..models import ShotSegment, ShotType, MotionIntensity


class ShotDetector:
    """
    镜头边界检测器 - 基于内容差异自动分割视频镜头
    使用 HSV 直方图差异 + 帧间差分双重检测
    """

    def __init__(
        self,
        threshold: float = 0.4,
        min_scene_length: int = 15,
        hist_bins: int = 50,
    ):
        self.threshold = threshold
        self.min_scene_length = min_scene_length
        self.hist_bins = hist_bins

    def _compute_hist_diff(self, prev_frame: np.ndarray, curr_frame: np.ndarray) -> float:
        prev_hsv = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2HSV)
        curr_hsv = cv2.cvtColor(curr_frame, cv2.COLOR_BGR2HSV)

        prev_hist = cv2.calcHist([prev_hsv], [0, 1], None, [self.hist_bins, self.hist_bins], [0, 180, 0, 256])
        curr_hist = cv2.calcHist([curr_hsv], [0, 1], None, [self.hist_bins, self.hist_bins], [0, 180, 0, 256])

        cv2.normalize(prev_hist, prev_hist)
        cv2.normalize(curr_hist, curr_hist)

        return cv2.compareHist(prev_hist, curr_hist, cv2.HISTCMP_CORREL)

    def _compute_frame_diff(self, prev_frame: np.ndarray, curr_frame: np.ndarray) -> float:
        prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
        curr_gray = cv2.cvtColor(curr_frame, cv2.COLOR_BGR2GRAY)

        prev_gray = cv2.GaussianBlur(prev_gray, (21, 21), 0)
        curr_gray = cv2.GaussianBlur(curr_gray, (21, 21), 0)

        diff = cv2.absdiff(prev_gray, curr_gray)
        _, thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)

        return np.count_nonzero(thresh) / thresh.size

    def _detect_fade(self, frame: np.ndarray) -> float:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        return np.mean(gray) / 255.0

    def detect_shots(
        self,
        video_path: str,
        sample_rate: int = 1,
    ) -> List[Tuple[int, int]]:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise FileNotFoundError(f"无法打开视频: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        boundaries = [0]
        prev_frame = None
        frame_idx = 0
        last_boundary = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx % sample_rate != 0:
                frame_idx += 1
                continue

            if prev_frame is not None:
                hist_corr = self._compute_hist_diff(prev_frame, frame)
                frame_diff = self._compute_frame_diff(prev_frame, frame)

                hist_score = 1.0 - hist_corr
                combined_score = hist_score * 0.6 + frame_diff * 0.4

                if combined_score > self.threshold and (frame_idx - last_boundary) >= self.min_scene_length:
                    boundaries.append(frame_idx)
                    last_boundary = frame_idx

            prev_frame = frame.copy()
            frame_idx += 1

        cap.release()

        if boundaries[-1] != total_frames - 1:
            boundaries.append(total_frames - 1)

        segments = []
        for i in range(len(boundaries) - 1):
            segments.append((boundaries[i], boundaries[i + 1]))

        return segments

    def detect_with_fades(
        self,
        video_path: str,
        fade_threshold: float = 0.05,
        sample_rate: int = 1,
    ) -> List[Tuple[int, int, str]]:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise FileNotFoundError(f"无法打开视频: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        boundaries = [0]
        boundary_types = ["start"]
        prev_frame = None
        prev_brightness = 1.0
        frame_idx = 0
        last_boundary = 0
        in_fade = False

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx % sample_rate != 0:
                frame_idx += 1
                continue

            brightness = self._detect_fade(frame)

            if prev_frame is not None:
                hist_corr = self._compute_hist_diff(prev_frame, frame)
                frame_diff = self._compute_frame_diff(prev_frame, frame)
                hist_score = 1.0 - hist_corr
                combined_score = hist_score * 0.6 + frame_diff * 0.4

                if brightness < fade_threshold and not in_fade:
                    in_fade = True
                elif brightness > fade_threshold and in_fade:
                    in_fade = False
                    if (frame_idx - last_boundary) >= self.min_scene_length:
                        boundaries.append(frame_idx)
                        boundary_types.append("fade")
                        last_boundary = frame_idx

                if combined_score > self.threshold and (frame_idx - last_boundary) >= self.min_scene_length:
                    boundaries.append(frame_idx)
                    boundary_types.append("cut")
                    last_boundary = frame_idx

            prev_frame = frame.copy()
            prev_brightness = brightness
            frame_idx += 1

        cap.release()

        if boundaries[-1] != total_frames - 1:
            boundaries.append(total_frames - 1)
            boundary_types.append("end")

        segments = []
        for i in range(len(boundaries) - 1):
            segments.append((boundaries[i], boundaries[i + 1], boundary_types[i]))

        return segments
