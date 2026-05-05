import cv2
import numpy as np
from typing import List, Tuple
from ..models import ShotSegment, ShotType, MotionIntensity


class MotionAnalyzer:
    """
    运动分析器 - 分析每个镜头的运动强度、类型和稳定性
    使用光流法 + 帧间差分综合判断
    """

    def __init__(
        self,
        flow_threshold_low: float = 1.0,
        flow_threshold_high: float = 4.0,
        stability_window: int = 10,
    ):
        self.flow_threshold_low = flow_threshold_low
        self.flow_threshold_high = flow_threshold_high
        self.stability_window = stability_window

    def analyze_segment_motion(
        self,
        video_path: str,
        start_frame: int,
        end_frame: int,
        sample_step: int = 3,
    ) -> Tuple[float, MotionIntensity, ShotType, float, float]:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return 0.0, MotionIntensity.STILL, ShotType.STATIC, 0.0, 1.0

        fps = cap.get(cv2.CAP_PROP_FPS)
        prev_gray = None
        flow_magnitudes = []
        flow_angles = []
        sharpness_scores = []

        total_frames = end_frame - start_frame
        if total_frames > 300:
            sample_step = max(sample_step, total_frames // 100)

        frame_idx = start_frame
        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

        while frame_idx <= end_frame:
            ret, frame = cap.read()
            if not ret:
                break

            small = cv2.resize(frame, (320, 180))
            gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
            sharpness = self._compute_sharpness(gray)
            sharpness_scores.append(sharpness)

            if prev_gray is not None and (frame_idx - start_frame) % sample_step == 0:
                flow = cv2.calcOpticalFlowFarneback(
                    prev_gray, gray, None, 0.5, 3, 15, 3, 5, 1.2, 0
                )
                magnitude, angle = cv2.cartToPolar(flow[..., 0], flow[..., 1])
                mean_mag = np.mean(magnitude)
                mean_angle = np.mean(angle)

                flow_magnitudes.append(mean_mag)
                flow_angles.append(mean_angle)

            prev_gray = gray.copy()
            frame_idx += 1

        cap.release()

        if not flow_magnitudes:
            avg_sharpness = np.mean(sharpness_scores) if sharpness_scores else 0.0
            return 0.0, MotionIntensity.STILL, ShotType.STATIC, avg_sharpness, 1.0

        avg_motion = np.mean(flow_magnitudes)
        max_motion = np.max(flow_magnitudes)
        motion_intensity = self._classify_intensity(avg_motion)
        shot_type = self._classify_shot_type(flow_magnitudes, flow_angles)
        stability = self._compute_stability(flow_magnitudes)
        avg_sharpness = np.mean(sharpness_scores) if sharpness_scores else 0.0

        return avg_motion, motion_intensity, shot_type, avg_sharpness, stability

    def _compute_sharpness(self, gray: np.ndarray) -> float:
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        return min(np.var(laplacian) / 1000.0, 1.0)

    def _classify_intensity(self, avg_motion: float) -> MotionIntensity:
        if avg_motion < self.flow_threshold_low * 0.3:
            return MotionIntensity.STILL
        elif avg_motion < self.flow_threshold_low:
            return MotionIntensity.LOW
        elif avg_motion < self.flow_threshold_high * 0.5:
            return MotionIntensity.MEDIUM
        elif avg_motion < self.flow_threshold_high:
            return MotionIntensity.HIGH
        else:
            return MotionIntensity.EXTREME

    def _classify_shot_type(
        self,
        magnitudes: List[float],
        angles: List[float],
    ) -> ShotType:
        if not magnitudes:
            return ShotType.STATIC

        avg_mag = np.mean(magnitudes)
        if avg_mag < self.flow_threshold_low * 0.3:
            return ShotType.STATIC

        angle_std = np.std(angles) if len(angles) > 1 else 0
        mag_std = np.std(magnitudes) if len(magnitudes) > 1 else 0

        if mag_std > avg_mag * 0.8:
            return ShotType.HANDHELD

        if angle_std < 0.3:
            mean_angle = np.mean(angles)
            if mean_angle < np.pi / 4 or mean_angle > 7 * np.pi / 4:
                return ShotType.PAN
            elif np.pi / 4 <= mean_angle <= 3 * np.pi / 4:
                return ShotType.TRACKING
            else:
                return ShotType.TILT

        if np.std(magnitudes[:len(magnitudes)//2]) > np.std(magnitudes[len(magnitudes)//2:]):
            return ShotType.ZOOM

        return ShotType.TRACKING

    def _compute_stability(self, magnitudes: List[float]) -> float:
        if len(magnitudes) < 2:
            return 1.0

        window = min(self.stability_window, len(magnitudes))
        stability_scores = []

        for i in range(len(magnitudes) - window + 1):
            window_mags = magnitudes[i:i + window]
            variation = np.std(window_mags) / (np.mean(window_mags) + 1e-6)
            stability_scores.append(1.0 / (1.0 + variation))

        return float(np.mean(stability_scores))

    def analyze_brightness_and_color(
        self,
        video_path: str,
        start_frame: int,
        end_frame: int,
        sample_frames: int = 5,
    ) -> Tuple[float, Tuple[int, int, int]]:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return 0.5, (128, 128, 128)

        total_frames = end_frame - start_frame
        step = max(1, total_frames // sample_frames)

        brightness_values = []
        color_samples = []

        for offset in range(0, total_frames, step):
            cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame + offset)
            ret, frame = cap.read()
            if not ret:
                continue

            small = cv2.resize(frame, (160, 90))
            hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
            brightness_values.append(np.mean(hsv[:, :, 2]) / 255.0)

            pixels = small.reshape(-1, 3).astype(np.float32)
            criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
            _, _, centers = cv2.kmeans(pixels, 1, None, criteria, 1, cv2.KMEANS_RANDOM_CENTERS)
            dominant = tuple(int(c) for c in centers[0])
            color_samples.append(dominant)

        cap.release()

        avg_brightness = float(np.mean(brightness_values)) if brightness_values else 0.5
        dominant_color = color_samples[0] if color_samples else (128, 128, 128)

        return avg_brightness, dominant_color
