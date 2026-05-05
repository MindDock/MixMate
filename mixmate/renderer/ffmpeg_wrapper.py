import subprocess
import os
import json
from typing import List, Optional, Dict, Any
from ..models import EditPlan, EditDecision, RenderResult
from ..editor.effect_engine import EffectEngine
from ..editor.subtitle_engine import SubtitleEngine


class FFmpegWrapper:
    """
    FFmpeg 封装器 - 将剪辑方案转化为 FFmpeg 命令并执行
    """

    def __init__(self, ffmpeg_path: str = "ffmpeg", ffprobe_path: str = "ffprobe"):
        self.ffmpeg_path = ffmpeg_path
        self.ffprobe_path = ffprobe_path

    def check_available(self) -> bool:
        try:
            result = subprocess.run(
                [self.ffmpeg_path, "-version"],
                capture_output=True, text=True, timeout=5,
            )
            return result.returncode == 0
        except Exception:
            return False

    def check_drawtext_available(self) -> bool:
        try:
            result = subprocess.run(
                [self.ffmpeg_path, "-filters"],
                capture_output=True, text=True, timeout=5,
            )
            return "drawtext" in result.stdout
        except Exception:
            return False

    def render_plan(
        self,
        plan: EditPlan,
        output_path: str,
        background_music: Optional[str] = None,
        watermark: Optional[str] = None,
        overwrite: bool = True,
    ) -> RenderResult:
        print(f"\n🎞️ 开始渲染: {plan.name}")
        print(f"  输出: {output_path}")

        self._drawtext_available = self.check_drawtext_available()
        if not self._drawtext_available:
            print("  ⚠️ FFmpeg 不支持 drawtext 滤镜，跳过字幕叠加")

        if len(plan.decisions) == 1:
            cmd = self._build_single_clip_command(plan, output_path, overwrite)
        else:
            cmd = self._build_concat_command(plan, output_path, overwrite)

        if background_music:
            cmd = self._add_background_music(cmd, background_music, plan.total_duration)

        if watermark:
            cmd = self._add_watermark(cmd, watermark)

        print(f"  执行命令: {' '.join(cmd[:80])}...")
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            print(f"  ❌ 渲染失败: {result.stderr[-500:]}")
            raise RuntimeError(f"FFmpeg 渲染失败: {result.stderr[-300:]}")

        file_size = os.path.getsize(output_path) if os.path.exists(output_path) else 0
        print(f"  ✅ 渲染完成: {output_path} ({file_size / 1024 / 1024:.1f}MB)")

        return RenderResult(
            output_path=output_path,
            duration=plan.total_duration,
            file_size=file_size,
            style=plan.style,
            plan_name=plan.name,
        )

    def _build_single_clip_command(
        self,
        plan: EditPlan,
        output_path: str,
        overwrite: bool,
    ) -> List[str]:
        decision = plan.decisions[0]
        seg = decision.segment
        out_w, out_h = plan.output_resolution

        cmd = [self.ffmpeg_path]
        if overwrite:
            cmd.append("-y")

        cmd.extend([
            "-i", seg.source_file,
            "-ss", str(seg.start_time + decision.trim_start),
            "-to", str(seg.end_time - decision.trim_end),
        ])

        vfilters = EffectEngine.build_filter_chain(
            decision, out_w, out_h,
            letterbox=False,
        )

        if decision.subtitle_text and getattr(self, '_drawtext_available', True):
            style_name = self._get_subtitle_style(plan.style)
            sub_filter = SubtitleEngine.build_drawtext_filter(
                decision.subtitle_text, style_name,
                enable_start=0.0,
                enable_end=decision.effective_duration,
            )
            if sub_filter:
                vfilters.append(sub_filter)

        if vfilters:
            cmd.extend(["-vf", ",".join(vfilters)])

        afilters = []
        audio_filter = EffectEngine.get_audio_filter(decision)
        if audio_filter:
            afilters.append(audio_filter)

        if afilters:
            cmd.extend(["-af", ",".join(afilters)])

        cmd.extend([
            "-c:v", plan.output_codec,
            "-r", str(plan.output_fps),
            "-preset", "medium",
            "-crf", "18",
            "-c:a", "aac",
            "-b:a", "192k",
            "-movflags", "+faststart",
            output_path,
        ])

        return cmd

    def _build_concat_command(
        self,
        plan: EditPlan,
        output_path: str,
        overwrite: bool,
    ) -> List[str]:
        import tempfile

        out_w, out_h = plan.output_resolution
        tmp_dir = tempfile.mkdtemp(prefix="mixmate_render_")
        clip_paths = []

        for i, decision in enumerate(plan.decisions):
            clip_path = os.path.join(tmp_dir, f"clip_{i:04d}.mp4")
            cmd = self._render_single_clip(
                decision, clip_path, out_w, out_h,
                plan.output_fps, plan.output_codec, plan.style,
                overwrite=True,
            )
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                print(f"  ⚠️ 片段 {i} 渲染失败: {result.stderr[-200:]}")
                continue
            clip_paths.append(clip_path)
            print(f"  📎 片段 {i+1}/{len(plan.decisions)} 完成")

        concat_file = os.path.join(tmp_dir, "concat.txt")
        with open(concat_file, "w", encoding="utf-8") as f:
            for path in clip_paths:
                f.write(f"file '{path}'\n")

        cmd = [self.ffmpeg_path]
        if overwrite:
            cmd.append("-y")
        cmd.extend([
            "-f", "concat",
            "-safe", "0",
            "-i", concat_file,
            "-c:v", plan.output_codec,
            "-c:a", "aac",
            "-b:a", "192k",
            "-movflags", "+faststart",
            output_path,
        ])

        return cmd

    def _render_single_clip(
        self,
        decision: EditDecision,
        output_path: str,
        out_w: int,
        out_h: int,
        fps: float,
        codec: str,
        style_name: str,
        overwrite: bool = True,
    ) -> List[str]:
        seg = decision.segment
        cmd = [self.ffmpeg_path]

        if overwrite:
            cmd.append("-y")

        cmd.extend([
            "-i", seg.source_file,
            "-ss", str(seg.start_time + decision.trim_start),
            "-to", str(seg.end_time - decision.trim_end),
        ])

        vfilters = EffectEngine.build_filter_chain(decision, out_w, out_h)

        if decision.subtitle_text and getattr(self, '_drawtext_available', True):
            sub_style = self._get_subtitle_style(style_name)
            sub_filter = SubtitleEngine.build_drawtext_filter(
                decision.subtitle_text, sub_style,
                enable_start=0.0,
                enable_end=decision.effective_duration,
            )
            if sub_filter:
                vfilters.append(sub_filter)

        if vfilters:
            cmd.extend(["-vf", ",".join(vfilters)])

        afilters = []
        audio_filter = EffectEngine.get_audio_filter(decision)
        if audio_filter:
            afilters.append(audio_filter)

        if afilters:
            cmd.extend(["-af", ",".join(afilters)])

        cmd.extend([
            "-c:v", codec,
            "-r", str(fps),
            "-preset", "fast",
            "-crf", "20",
            "-c:a", "aac",
            "-b:a", "192k",
            "-movflags", "+faststart",
            output_path,
        ])

        return cmd

    def _add_background_music(
        self,
        cmd: List[str],
        music_path: str,
        duration: float,
    ) -> List[str]:
        idx = cmd.index("-i") if "-i" in cmd else 0
        new_cmd = cmd[:idx]

        new_cmd.extend(["-i", music_path])

        new_cmd.extend(cmd[idx:])

        new_cmd.extend([
            "-map", "0:v:0",
            "-map", "0:a:0",
            "-map", "1:a:0",
            "-filter_complex",
            f"[1:a]volume=0.3,afade=t=in:st=0:d=1,afade=t=out:st={duration-2}:d=2[music];"
            f"[0:a][music]amix=inputs=2:duration=first:dropout_transition=2[aout]",
            "-map", "[aout]",
        ])

        return new_cmd

    def _add_watermark(
        self,
        cmd: List[str],
        watermark_path: str,
    ) -> List[str]:
        idx = cmd.index("-i") if "-i" in cmd else 0
        new_cmd = cmd[:idx]
        new_cmd.extend(["-i", watermark_path])
        new_cmd.extend(cmd[idx:])

        new_cmd.extend([
            "-filter_complex",
            "[1:v]scale=100:-1[wm];[0:v][wm]overlay=W-w-10:10",
        ])

        return new_cmd

    def _get_subtitle_style(self, style_name: str) -> str:
        style_map = {
            "tiktok_flash": "tiktok",
            "cinematic": "cinematic",
            "vlog_light": "vlog",
            "sports_hype": "impact",
            "chill_aesthetic": "minimal",
            "music_video": "lyrics",
        }
        return style_map.get(style_name, "tiktok")

    def get_video_info(self, video_path: str) -> Dict[str, Any]:
        cmd = [
            self.ffprobe_path, "-v", "quiet",
            "-print_format", "json",
            "-show_format", "-show_streams",
            video_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return json.loads(result.stdout)

    def extract_thumbnail(self, video_path: str, output_path: str, time_offset: float = 1.0, width: int = 320) -> bool:
        cmd = [
            self.ffmpeg_path, "-y",
            "-ss", str(time_offset),
            "-i", video_path,
            "-vframes", "1",
            "-vf", f"scale={width}:-1",
            "-q:v", "4",
            output_path,
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            return result.returncode == 0 and os.path.exists(output_path)
        except Exception:
            return False
