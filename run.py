#!/usr/bin/env python3
"""
MixMate 一键运行脚本
用法: python run.py <视频文件或目录> [选项]

示例:
  python run.py dance_clip.mp4
  python run.py ./raw_videos/ --style tiktok_flash,cinematic --count 2
  python run.py video1.mp4 video2.mp4 --style vlog_light --duration 30
"""

import argparse
import os
import sys
import glob


def collect_videos(path_or_pattern: str) -> list:
    if os.path.isfile(path_or_pattern):
        return [os.path.abspath(path_or_pattern)]

    if os.path.isdir(path_or_pattern):
        video_exts = {".mp4", ".mov", ".avi", ".mkv", ".flv", ".webm", ".m4v"}
        videos = []
        for f in os.listdir(path_or_pattern):
            ext = os.path.splitext(f)[1].lower()
            if ext in video_exts:
                videos.append(os.path.abspath(os.path.join(path_or_pattern, f)))
        return sorted(videos)

    return [os.path.abspath(p) for p in glob.glob(path_or_pattern)]


def main():
    parser = argparse.ArgumentParser(
        description="MixMate - AI自动视频剪辑 | 自动剪辑收割机",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=""'
示例:
  python run.py dance.mp4                          # 默认抖音快闪风格
  python run.py ./videos/ --style tiktok_flash,cinematic --count 2
  python run.py v1.mp4 v2.mp4 --style vlog_light --duration 30 --music bgm.mp3
  python run.py video.mp4 --analyze-only           # 仅分析，不剪辑
        ''',
    )

    parser.add_argument(
        "inputs", nargs="+",
        help="视频文件路径或目录",
    )
    parser.add_argument(
        "-s", "--style", default="tiktok_flash",
        help="剪辑风格，逗号分隔 (默认: tiktok_flash)",
    )
    parser.add_argument(
        "-c", "--count", type=int, default=1,
        help="每种风格生成几条 (默认: 1)",
    )
    parser.add_argument(
        "-d", "--duration", type=float, default=15.0,
        help="目标时长秒数 (默认: 15)",
    )
    parser.add_argument(
        "-m", "--music", default=None,
        help="背景音乐文件",
    )
    parser.add_argument(
        "-o", "--output", default="./mixmate_output",
        help="输出目录 (默认: ./mixmate_output)",
    )
    parser.add_argument(
        "--analyze-only", action="store_true",
        help="仅分析素材，不进行剪辑",
    )
    parser.add_argument(
        "--plan-only", action="store_true",
        help="仅生成剪辑方案，不渲染视频",
    )

    args = parser.parse_args()

    video_paths = []
    for inp in args.inputs:
        video_paths.extend(collect_videos(inp))

    if not video_paths:
        print("❌ 未找到任何视频文件")
        sys.exit(1)

    print(f"\n🎬 MixMate - AI自动视频剪辑系统")
    print(f"{'='*60}")
    print(f"  素材: {len(video_paths)} 个文件")
    for p in video_paths:
        print(f"    📁 {p}")
    print(f"  风格: {args.style}")
    print(f"  数量: {args.count} 条/风格")
    print(f"  时长: {args.duration}s")
    print(f"  输出: {args.output}")
    print(f"{'='*60}")

    os.makedirs(args.output, exist_ok=True)

    # Step 1: Timeline 分析
    from mixmate.analyzer import TimelineAnalyzer

    analyzer = TimelineAnalyzer()
    analysis = analyzer.analyze_multiple(
        video_paths,
        save_thumbnails=True,
        thumbnail_dir=os.path.join(args.output, "thumbnails"),
    )

    report_path = os.path.join(args.output, "analysis_report.json")
    analyzer.save_report(analysis, report_path)

    if args.analyze_only:
        print(f"\n✅ 仅分析模式完成！报告: {report_path}")
        return

    # Step 2: 生成剪辑方案
    from mixmate.editor import AutoEditor

    styles = [s.strip() for s in args.style.split(",")]
    plans = []

    for style_name in styles:
        try:
            editor = AutoEditor(style_name)
            for v in range(args.count):
                plan_name = f"{style_name}_v{v+1}"
                plan = editor.create_edit_plan(
                    analysis,
                    target_duration=args.duration,
                    plan_name=plan_name,
                )
                plans.append(plan)

                plan_path = os.path.join(args.output, f"plan_{plan_name}.json")
                editor.save_plan(plan, plan_path)
        except Exception as e:
            print(f"❌ 风格 {style_name} 方案生成失败: {e}")

    if args.plan_only:
        print(f"\n✅ 仅方案模式完成！方案目录: {args.output}")
        return

    # Step 3: 渲染输出
    from mixmate.renderer import FFmpegWrapper

    ffmpeg = FFmpegWrapper()
    if not ffmpeg.check_available():
        print(f"\n❌ FFmpeg 未安装或不在 PATH 中")
        print(f"   请先安装: brew install ffmpeg")
        sys.exit(1)

    from mixmate.renderer.batch_renderer import BatchRenderer

    renderer = BatchRenderer(output_dir=args.output)
    bg_music = args.music if args.music and os.path.exists(args.music) else None

    results = []
    for plan in plans:
        try:
            result = renderer.render_single(
                plan,
                background_music=bg_music,
            )
            results.append(result)
        except Exception as e:
            print(f"❌ 渲染失败 [{plan.name}]: {e}")

    print(f"\n🎉 MixMate 完成！")
    print(f"   生成视频: {len(results)} 条")
    print(f"   输出目录: {args.output}")
    for r in results:
        size_mb = r.file_size / 1024 / 1024
        print(f"   📹 {r.plan_name} | {r.duration:.1f}s | {size_mb:.1f}MB")


if __name__ == "__main__":
    main()
