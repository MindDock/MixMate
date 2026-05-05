import os
import json
import time
from typing import List, Optional
from pathlib import Path
from ..models import EditPlan, RenderResult, TimelineAnalysis
from ..editor.auto_editor import AutoEditor
from .ffmpeg_wrapper import FFmpegWrapper


class BatchRenderer:
    """
    批量渲染器 - 一键生成多条不同风格的成品视频
    """

    def __init__(
        self,
        output_dir: str = "./output",
        ffmpeg_path: str = "ffmpeg",
        ffprobe_path: str = "ffprobe",
    ):
        self.output_dir = output_dir
        self.ffmpeg = FFmpegWrapper(ffmpeg_path, ffprobe_path)
        os.makedirs(output_dir, exist_ok=True)

    def render_single(
        self,
        plan: EditPlan,
        background_music: Optional[str] = None,
        watermark: Optional[str] = None,
        filename: Optional[str] = None,
    ) -> RenderResult:
        if filename is None:
            filename = f"{plan.name}.mp4"
        output_path = os.path.join(self.output_dir, filename)

        return self.ffmpeg.render_plan(
            plan, output_path,
            background_music=background_music,
            watermark=watermark,
        )

    def render_batch(
        self,
        analysis: TimelineAnalysis,
        styles: List[str],
        count_per_style: int = 1,
        target_duration: Optional[float] = None,
        background_music: Optional[str] = None,
        watermark: Optional[str] = None,
    ) -> List[RenderResult]:
        print(f"\n🚀 批量渲染启动")
        print(f"  风格数: {len(styles)}")
        print(f"  每风格生成: {count_per_style} 条")
        print(f"  总计: {len(styles) * count_per_style} 条视频")
        print(f"{'='*60}")

        results = []
        editor = AutoEditor()

        for style_name in styles:
            for v in range(count_per_style):
                try:
                    plan_name = f"{style_name}_v{v+1}"
                    editor = AutoEditor(style_name)
                    plan = editor.create_edit_plan(
                        analysis,
                        target_duration=target_duration,
                        plan_name=plan_name,
                    )

                    filename = f"{plan_name}_{int(time.time())}.mp4"
                    result = self.render_single(
                        plan,
                        background_music=background_music,
                        watermark=watermark,
                        filename=filename,
                    )
                    results.append(result)

                except Exception as e:
                    print(f"  ❌ 渲染失败 [{style_name} v{v+1}]: {e}")

        self._print_batch_summary(results)
        return results

    def render_quick(
        self,
        video_paths: List[str],
        styles: Optional[List[str]] = None,
        count: int = 3,
        target_duration: float = 15.0,
        background_music: Optional[str] = None,
    ) -> List[RenderResult]:
        from ..analyzer import TimelineAnalyzer

        if styles is None:
            styles = ["tiktok_flash", "vlog_light", "cinematic"]

        print(f"\n🎯 MixMate 快速模式")
        print(f"  素材: {len(video_paths)} 个文件")
        print(f"  风格: {', '.join(styles)}")
        print(f"  数量: {count} 条/风格")
        print(f"  时长: {target_duration}s")
        print(f"{'='*60}")

        analyzer = TimelineAnalyzer()
        analysis = analyzer.analyze_multiple(video_paths)

        report_path = os.path.join(self.output_dir, "analysis_report.json")
        analyzer.save_report(analysis, report_path)

        results = self.render_batch(
            analysis,
            styles=styles,
            count_per_style=count,
            target_duration=target_duration,
            background_music=background_music,
        )

        return results

    def _print_batch_summary(self, results: List[RenderResult]):
        print(f"\n{'='*60}")
        print(f"📊 批量渲染汇总")
        print(f"{'='*60}")
        print(f"  成功: {len(results)} 条")

        total_size = 0
        for r in results:
            size_mb = r.file_size / 1024 / 1024
            total_size += size_mb
            print(f"  ✅ {r.plan_name} | {r.duration:.1f}s | {size_mb:.1f}MB | {r.output_path}")

        print(f"  总大小: {total_size:.1f}MB")
        print(f"  输出目录: {self.output_dir}")
        print(f"{'='*60}\n")
