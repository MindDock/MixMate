import cv2
import numpy as np
from typing import List, Set, Optional
from ..models import ShotSegment, ContentTag, ShotType, MotionIntensity
from ..ai.base import VisionProvider, SceneUnderstanding
from ..ai.providers import AIProviderFactory, extract_segment_frames


class ContentTagger:
    """
    内容标签器 - 为每个镜头片段自动打上语义标签
    优先使用 AI 视觉理解，回退到传统CV算法
    """

    def __init__(
        self,
        person_detection_enabled: bool = False,
        face_detection_enabled: bool = True,
        vision_provider: Optional[VisionProvider] = None,
    ):
        self.person_detection_enabled = person_detection_enabled
        self.face_detection_enabled = face_detection_enabled
        self._face_cascade = None
        self._hog = None
        self._vision_provider = vision_provider

    def _get_face_cascade(self):
        if self._face_cascade is None:
            cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            self._face_cascade = cv2.CascadeClassifier(cascade_path)
        return self._face_cascade

    def _get_hog(self):
        if self._hog is None:
            self._hog = cv2.HOGDescriptor()
            self._hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
        return self._hog

    def tag_segment(
        self,
        segment: ShotSegment,
        video_path: str,
        sample_count: int = 5,
    ) -> ShotSegment:
        if self._vision_provider and self._vision_provider.is_available():
            try:
                return self._tag_by_ai(segment, video_path)
            except Exception as e:
                print(f"    ⚠️ AI标签失败，回退规则引擎: {e}")

        tags = set()

        tags.update(self._tag_by_motion(segment))
        tags.update(self._tag_by_visual(video_path, segment, sample_count))
        tags.update(self._tag_by_audio(segment))
        tags.update(self._tag_by_position(segment))

        segment.content_tags = list(tags)

        segment.quality_score = self._compute_quality_score(segment)

        return segment

    def _tag_by_ai(self, segment: ShotSegment, video_path: str) -> ShotSegment:
        frames = extract_segment_frames(
            video_path, segment.start_frame, segment.end_frame, count=3
        )
        if not frames:
            return self._tag_fallback(segment, video_path)

        scene = self._vision_provider.analyze_segment(frames)

        tags = set()
        if scene.is_dancing:
            tags.add(ContentTag.DANCE)
        if scene.is_sports:
            tags.add(ContentTag.SPORTS)
        if scene.is_talking:
            tags.add(ContentTag.TALKING)
        if scene.is_walking:
            tags.add(ContentTag.WALKING)
        if scene.is_closeup:
            tags.add(ContentTag.CLOSEUP)
        if scene.is_landscape:
            tags.add(ContentTag.LANDSCAPE)
            tags.add(ContentTag.BROLL)
        if scene.is_group_activity:
            tags.add(ContentTag.GROUP)
        if scene.people_count >= 1 and not scene.is_group_activity:
            tags.add(ContentTag.SOLO)
        if scene.people_count == 0 and not scene.is_landscape:
            tags.add(ContentTag.BROLL)
        if scene.narrative_role == "opening":
            tags.add(ContentTag.INTRO)
        if scene.narrative_role == "ending":
            tags.add(ContentTag.OUTRO)
        if scene.mood in ("欢快", "紧张", "激烈"):
            tags.add(ContentTag.ACTION)
        if scene.mood in ("温馨", "感动", "浪漫"):
            tags.add(ContentTag.EMOTION)

        if not tags:
            tags.update(self._tag_by_motion(segment))
            tags.update(self._tag_by_audio(segment))

        segment.content_tags = list(tags)

        if scene.confidence > 0.5:
            segment.quality_score = max(segment.quality_score, scene.confidence)

        return segment

    def _tag_fallback(self, segment: ShotSegment, video_path: str) -> ShotSegment:
        tags = set()
        tags.update(self._tag_by_motion(segment))
        tags.update(self._tag_by_audio(segment))
        tags.update(self._tag_by_position(segment))
        segment.content_tags = list(tags)
        segment.quality_score = self._compute_quality_score(segment)
        return segment

    def _tag_by_motion(self, segment: ShotSegment) -> Set[ContentTag]:
        tags = set()

        if segment.motion_intensity in (MotionIntensity.HIGH, MotionIntensity.EXTREME):
            tags.add(ContentTag.ACTION)
            if segment.shot_type in (ShotType.TRACKING, ShotType.HANDHELD):
                tags.add(ContentTag.DANCE)
                tags.add(ContentTag.SPORTS)

        if segment.motion_intensity == MotionIntensity.STILL:
            if segment.shot_type == ShotType.STATIC:
                tags.add(ContentTag.CLOSEUP)

        return tags

    def _tag_by_visual(
        self,
        video_path: str,
        segment: ShotSegment,
        sample_count: int,
    ) -> Set[ContentTag]:
        tags = set()
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return tags

        total_frames = segment.end_frame - segment.start_frame
        step = max(1, total_frames // sample_count)

        face_count_max = 0
        person_count_max = 0
        has_closeup = False

        for offset in range(0, total_frames, step):
            cap.set(cv2.CAP_PROP_POS_FRAMES, segment.start_frame + offset)
            ret, frame = cap.read()
            if not ret:
                continue

            small = cv2.resize(frame, (640, 360))

            if self.face_detection_enabled:
                faces = self._detect_faces(small)
                face_count_max = max(face_count_max, len(faces))
                if len(faces) > 0 and self._is_closeup(small, faces):
                    has_closeup = True

            if self.person_detection_enabled:
                persons = self._detect_persons(small)
                person_count_max = max(person_count_max, len(persons))

        cap.release()

        if face_count_max > 0:
            tags.add(ContentTag.EMOTION)
            if has_closeup:
                tags.add(ContentTag.CLOSEUP)

        if person_count_max >= 3:
            tags.add(ContentTag.GROUP)
        elif person_count_max >= 1:
            tags.add(ContentTag.SOLO)

        if person_count_max == 0 and face_count_max == 0:
            tags.add(ContentTag.LANDSCAPE)
            tags.add(ContentTag.BROLL)

        return tags

    def _tag_by_audio(self, segment: ShotSegment) -> Set[ContentTag]:
        tags = set()
        if segment.has_speech:
            tags.add(ContentTag.TALKING)
        if segment.has_music:
            tags.add(ContentTag.MUSIC)
        if not segment.has_speech and not segment.has_music and segment.audio_energy < 0.01:
            tags.add(ContentTag.SILENCE)
        return tags

    def _tag_by_position(self, segment: ShotSegment) -> Set[ContentTag]:
        tags = set()
        if segment.index == 0:
            tags.add(ContentTag.INTRO)
        return tags

    def _detect_faces(self, frame: np.ndarray) -> List:
        cascade = self._get_face_cascade()
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = cascade.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30)
        )
        return faces

    def _detect_persons(self, frame: np.ndarray) -> List:
        try:
            hog = self._get_hog()
            small = cv2.resize(frame, (frame.shape[1] // 2, frame.shape[0] // 2))
            boxes, _ = hog.detectMultiScale(
                small, winStride=(8, 8), padding=(4, 4), scale=1.05
            )
            return boxes
        except Exception:
            return []

    def _is_closeup(self, frame: np.ndarray, faces) -> bool:
        if len(faces) == 0:
            return False
        face = faces[0]
        face_area = face[2] * face[3]
        frame_area = frame.shape[0] * frame.shape[1]
        return face_area / frame_area > 0.1

    def _compute_quality_score(self, segment: ShotSegment) -> float:
        score = 0.5

        sharpness = float(segment.sharpness or 0)
        stability = float(segment.stability_score or 0.5)
        brightness = float(segment.brightness or 0.5)
        motion_val = segment.motion_intensity.value if isinstance(segment.motion_intensity, MotionIntensity) else int(segment.motion_intensity or 0)

        if sharpness > 0.5:
            score += 0.15
        elif sharpness < 0.1:
            score -= 0.2

        if stability > 0.7:
            score += 0.1
        elif stability < 0.3:
            score -= 0.15

        if 0.3 <= brightness <= 0.8:
            score += 0.1
        elif brightness < 0.1 or brightness > 0.95:
            score -= 0.2

        if motion_val in (MotionIntensity.MEDIUM.value, MotionIntensity.HIGH.value):
            score += 0.1

        if segment.has_speech or segment.has_music:
            score += 0.05

        return max(0.0, min(1.0, score))
