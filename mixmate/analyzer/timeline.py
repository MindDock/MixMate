import json
import os
import tempfile
from typing import List, Optional
from pathlib import Path

from ..models import (
    VideoSource, ShotSegment, TimelineAnalysis,
    ShotType, MotionIntensity, ContentTag,
)
from .shot_detector import ShotDetector
from .motion_analyzer import MotionAnalyzer
from .audio_analyzer import AudioAnalyzer
from .content_tagger import ContentTagger
from ..ai.base import VisionProvider, SpeechProvider
from ..ai.providers import AIProviderFactory, load_config


class TimelineAnalyzer:
    """
    Timeline 分析器 - 整合所有子分析器，生成完整的视频素材时间线报告
    这是系统的第一步：先理解素材，再操刀剪辑
    支持 AI Provider 增强（视觉理解/语音识别）
    """

    def __init__(
        self,
        shot_threshold: float = 0.4,
        shot_min_length: int = 15,
        motion_sample_step: int = 3,
        beat_sensitivity: float = 1.0,
        tag_person: bool = True,
        tag_face: bool = True,
        vision_provider: Optional[VisionProvider] = None,
        use_ai: bool = False,
    ):
        self.shot_detector = ShotDetector(
            threshold=shot_threshold,
            min_scene_length=shot_min_length,
        )
        self.motion_analyzer = MotionAnalyzer()
        self.audio_analyzer = AudioAnalyzer(beat_sensitivity=beat_sensitivity)

        vp = vision_provider

        if use_ai and vp is None:
            config = load_config()
            vp = AIProviderFactory.create_vision_provider(config.get("vision"))

        self.content_tagger = ContentTagger(
            person_detection_enabled=tag_person,
            face_detection_enabled=tag_face,
            vision_provider=vp,
        )
        self.speech_provider = None

    def analyze_video(
        self,
        video_path: str,
        save_thumbnails: bool = True,
        thumbnail_dir: Optional[str] = None,
    ) -> VideoSource:
        print(f"\n🎬 开始分析: {video_path}")

        info = self.audio_analyzer.get_video_info(video_path)
        video_stream = None
        audio_stream = None
        for stream in info.get("streams", []):
            if stream["codec_type"] == "video" and video_stream is None:
                video_stream = stream
            elif stream["codec_type"] == "audio" and audio_stream is None:
                audio_stream = stream

        if video_stream is None:
            raise ValueError(f"未找到视频流: {video_path}")

        fps = eval(video_stream.get("r_frame_rate", "30/1"))
        width = int(video_stream.get("width", 0))
        height = int(video_stream.get("height", 0))
        duration = float(info.get("format", {}).get("duration", 0))
        codec = video_stream.get("codec_name", "unknown")
        audio_codec = audio_stream.get("codec_name", "") if audio_stream else ""

        source = VideoSource(
            file_path=video_path,
            duration=duration,
            fps=fps,
            width=width,
            height=height,
            codec=codec,
            audio_codec=audio_codec,
        )

        print(f"  📐 分辨率: {width}x{height}, FPS: {fps:.1f}, 时长: {duration:.1f}s")

        # Step 1: 镜头分割
        print("  🔍 镜头分割中...")
        shot_segments = self.shot_detector.detect_shots(video_path)
        print(f"  ✅ 检测到 {len(shot_segments)} 个镜头")

        # Step 2: 提取音频
        audio_path = None
        if audio_stream:
            print("  🎵 音频提取中...")
            try:
                audio_path = self.audio_analyzer.extract_audio(video_path)
            except Exception as e:
                print(f"  ⚠️ 音频提取失败: {e}")

        # Step 3: 全局节拍检测
        global_beats = []
        if audio_path:
            print("  🥁 节拍检测中...")
            try:
                global_beats = self.audio_analyzer.detect_beats(audio_path)
                print(f"  ✅ 检测到 {len(global_beats)} 个节拍点")
            except Exception as e:
                print(f"  ⚠️ 节拍检测失败: {e}")

        # Step 4: 逐镜头分析
        print("  🏃 运动分析 + 内容标签中...")
        if thumbnail_dir is None and save_thumbnails:
            thumbnail_dir = tempfile.mkdtemp(prefix="mixmate_thumb_")

        for idx, (start_frame, end_frame) in enumerate(shot_segments):
            start_time = start_frame / fps
            end_time = end_frame / fps

            segment = ShotSegment(
                index=idx,
                start_time=start_time,
                end_time=end_time,
                start_frame=start_frame,
                end_frame=end_frame,
                source_file=video_path,
            )

            # 运动分析
            try:
                motion_score, motion_intensity, shot_type, sharpness, stability = (
                    self.motion_analyzer.analyze_segment_motion(
                        video_path, start_frame, end_frame
                    )
                )
                segment.motion_score = motion_score
                segment.motion_intensity = motion_intensity
                segment.shot_type = shot_type
                segment.sharpness = sharpness
                segment.stability_score = stability
            except Exception as e:
                print(f"    ⚠️ 镜头 {idx} 运动分析失败: {e}")

            # 亮度与颜色
            try:
                brightness, dominant_color = self.motion_analyzer.analyze_brightness_and_color(
                    video_path, start_frame, end_frame
                )
                segment.brightness = brightness
                segment.color_dominant = dominant_color
            except Exception as e:
                print(f"    ⚠️ 镜头 {idx} 亮度分析失败: {e}")

            # 音频分析
            if audio_path:
                try:
                    energy, has_speech, has_music, beats = (
                        self.audio_analyzer.analyze_segment_audio(
                            audio_path, start_time, end_time,
                            global_beats=global_beats,
                        )
                    )
                    segment.audio_energy = energy
                    segment.has_speech = has_speech
                    segment.has_music = has_music
                    segment.beat_positions = beats
                except Exception as e:
                    print(f"    ⚠️ 镜头 {idx} 音频分析失败: {e}")

            # 内容标签
            try:
                segment = self.content_tagger.tag_segment(segment, video_path)
            except Exception as e:
                print(f"    ⚠️ 镜头 {idx} 内容标签失败: {e}")

            # 缩略图
            if save_thumbnails and thumbnail_dir:
                try:
                    thumb_path = self._save_thumbnail(
                        video_path, start_frame, idx, thumbnail_dir
                    )
                    segment.thumbnail_path = thumb_path
                except Exception:
                    pass

            source.segments.append(segment)

            tag_str = ", ".join(t.value for t in segment.content_tags) or "无标签"
            print(
                f"    镜头 {idx:02d} | {start_time:.1f}s-{end_time:.1f}s | "
                f"{segment.shot_type.value} | 运动:{segment.motion_intensity.name} | "
                f"质量:{segment.quality_score:.2f} | [{tag_str}]"
            )

        # 清理临时音频
        if audio_path and os.path.exists(audio_path):
            try:
                os.unlink(audio_path)
            except Exception:
                pass

        print(f"  ✅ 分析完成: {len(source.segments)} 个镜头已标记\n")
        return source

    def analyze_multiple(
        self,
        video_paths: List[str],
        save_thumbnails: bool = True,
        thumbnail_dir: Optional[str] = None,
    ) -> TimelineAnalysis:
        analysis = TimelineAnalysis()

        for path in video_paths:
            source = self.analyze_video(path, save_thumbnails, thumbnail_dir)
            analysis.sources.append(source)
            analysis.all_segments.extend(source.segments)
            analysis.total_duration += source.duration

        if analysis.sources:
            first_source = analysis.sources[0]
            if first_source.segments:
                audio_path = None
                try:
                    audio_path = self.audio_analyzer.extract_audio(first_source.file_path)
                    analysis.global_beats = self.audio_analyzer.detect_beats(audio_path)
                except Exception:
                    pass
                finally:
                    if audio_path and os.path.exists(audio_path):
                        try:
                            os.unlink(audio_path)
                        except Exception:
                            pass

        print(f"\n{'='*60}")
        print(f"📊 全部素材分析汇总")
        print(f"{'='*60}")
        print(f"  素材数量: {len(analysis.sources)}")
        print(f"  总时长: {analysis.total_duration:.1f}s")
        print(f"  总镜头数: {len(analysis.all_segments)}")
        print(f"  节拍点数: {len(analysis.global_beats)}")

        high_energy = analysis.get_high_energy_segments()
        stable = analysis.get_stable_segments()
        music = analysis.get_music_segments()
        speech = analysis.get_speech_segments()

        print(f"  高能量镜头: {len(high_energy)}")
        print(f"  稳定镜头: {len(stable)}")
        print(f"  有音乐镜头: {len(music)}")
        print(f"  有语音镜头: {len(speech)}")
        print(f"{'='*60}\n")

        return analysis

    def save_report(self, analysis: TimelineAnalysis, output_path: str):
        report = analysis.to_dict()
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"📄 分析报告已保存: {output_path}")

    def _save_thumbnail(
        self,
        video_path: str,
        frame_no: int,
        index: int,
        output_dir: str,
    ) -> str:
        import cv2

        cap = cv2.VideoCapture(video_path)
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_no)
        ret, frame = cap.read()
        cap.release()

        if not ret:
            return ""

        thumb = cv2.resize(frame, (160, 90))
        filename = f"shot_{index:03d}.jpg"
        path = os.path.join(output_dir, filename)
        cv2.imwrite(path, thumb)
        return path
