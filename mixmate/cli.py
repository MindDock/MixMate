#!/usr/bin/env python3
"""
MixMate CLI - AI驱动的自动视频剪辑系统
命令行入口

用法:
  # 分析素材（先看懂再剪）
  mixmate analyze video1.mp4 video2.mp4

  # 一键生成（分析+剪辑+渲染）
  mixmate auto video1.mp4 video2.mp4 --style tiktok_flash --count 3

  # 批量多风格生成
  mixmate auto video1.mp4 --style tiktok_flash,cinematic,vlog_light --count 2

  # 查看可用风格
  mixmate styles

  # 仅生成剪辑方案（不渲染）
  mixmate plan video1.mp4 --style cinematic --duration 30
"""

import argparse
import json
import os
import sys
from pathlib import Path


def cmd_analyze(args):
    from mixmate.analyzer import TimelineAnalyzer

    analyzer = TimelineAnalyzer(
        shot_threshold=args.threshold,
        beat_sensitivity=args.beat_sensitivity,
    )

    video_paths = [os.path.abspath(p) for p in args.videos]
    for p in video_paths:
        if not os.path.exists(p):
            print(f"❌ 文件不存在: {p}")
            sys.exit(1)

    analysis = analyzer.analyze_multiple(
        video_paths,
        save_thumbnails=True,
        thumbnail_dir=os.path.join(args.output, "thumbnails"),
    )

    report_path = os.path.join(args.output, "analysis_report.json")
    os.makedirs(args.output, exist_ok=True)
    analyzer.save_report(analysis, report_path)

    print(f"\n✅ 分析完成！报告已保存至: {report_path}")
    print(f"   使用 'mixmate plan' 或 'mixmate auto' 继续操作")


def cmd_styles(args):
    from mixmate.config import list_styles

    styles = list_styles()
    print(f"\n🎨 可用风格列表")
    print(f"{'─'*60}")
    for s in styles:
        print(f"  {s['name']:<20} | {s['display_name']:<8} | {s['description']}")
        print(f"  {'':<20} | 目标时长: {s['target_duration']}s")
    print(f"{'─'*60}\n")


def cmd_plan(args):
    from mixmate.analyzer import TimelineAnalyzer
    from mixmate.editor import AutoEditor

    video_paths = [os.path.abspath(p) for p in args.videos]
    for p in video_paths:
        if not os.path.exists(p):
            print(f"❌ 文件不存在: {p}")
            sys.exit(1)

    analyzer = TimelineAnalyzer()
    analysis = analyzer.analyze_multiple(video_paths)

    styles = args.style.split(",")
    os.makedirs(args.output, exist_ok=True)

    for style_name in styles:
        try:
            editor = AutoEditor(style_name.strip())
            plan = editor.create_edit_plan(
                analysis,
                target_duration=args.duration,
            )
            plan_path = os.path.join(args.output, f"plan_{style_name.strip()}.json")
            editor.save_plan(plan, plan_path)
        except Exception as e:
            print(f"❌ 风格 {style_name} 方案生成失败: {e}")

    print(f"\n✅ 剪辑方案已保存至: {args.output}/")


def cmd_auto(args):
    from mixmate.renderer import BatchRenderer

    video_paths = [os.path.abspath(p) for p in args.videos]
    for p in video_paths:
        if not os.path.exists(p):
            print(f"❌ 文件不存在: {p}")
            sys.exit(1)

    styles = args.style.split(",")
    renderer = BatchRenderer(output_dir=args.output)

    bg_music = args.music if args.music and os.path.exists(args.music) else None

    results = renderer.render_quick(
        video_paths=video_paths,
        styles=styles,
        count=args.count,
        target_duration=args.duration,
        background_music=bg_music,
    )

    if results:
        print(f"\n🎉 全部完成！共生成 {len(results)} 条视频")
        print(f"   输出目录: {args.output}")
    else:
        print(f"\n⚠️ 未生成任何视频，请检查素材和配置")


def cmd_web(args):
    from mixmate.web import run_server
    run_server(host=args.host, port=args.port, debug=args.debug)


def main():
    parser = argparse.ArgumentParser(
        prog="mixmate",
        description="MixMate - AI驱动的自动视频剪辑系统 | 先理解素材，再操刀剪辑",
    )
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # web
    p_web = subparsers.add_parser("web", help="启动 Web UI")
    p_web.add_argument("-p", "--port", type=int, default=5000, help="端口号 (默认: 5000)")
    p_web.add_argument("--host", default="0.0.0.0", help="绑定地址 (默认: 0.0.0.0)")
    p_web.add_argument("--debug", action="store_true", help="调试模式")

    # analyze
    p_analyze = subparsers.add_parser("analyze", help="分析视频素材（Timeline识别）")
    p_analyze.add_argument("videos", nargs="+", help="视频文件路径")
    p_analyze.add_argument("-o", "--output", default="./mixmate_output", help="输出目录")
    p_analyze.add_argument("--threshold", type=float, default=0.4, help="镜头分割阈值")
    p_analyze.add_argument("--beat-sensitivity", type=float, default=1.0, help="节拍检测灵敏度")

    # styles
    p_styles = subparsers.add_parser("styles", help="查看可用风格")

    # plan
    p_plan = subparsers.add_parser("plan", help="生成剪辑方案（不渲染）")
    p_plan.add_argument("videos", nargs="+", help="视频文件路径")
    p_plan.add_argument("-s", "--style", default="tiktok_flash", help="风格（逗号分隔多种）")
    p_plan.add_argument("-d", "--duration", type=float, default=15.0, help="目标时长（秒）")
    p_plan.add_argument("-o", "--output", default="./mixmate_output", help="输出目录")

    # auto
    p_auto = subparsers.add_parser("auto", help="一键自动剪辑（分析+方案+渲染）")
    p_auto.add_argument("videos", nargs="+", help="视频文件路径")
    p_auto.add_argument("-s", "--style", default="tiktok_flash", help="风格（逗号分隔多种）")
    p_auto.add_argument("-c", "--count", type=int, default=1, help="每风格生成条数")
    p_auto.add_argument("-d", "--duration", type=float, default=15.0, help="目标时长（秒）")
    p_auto.add_argument("-m", "--music", default=None, help="背景音乐文件路径")
    p_auto.add_argument("-o", "--output", default="./mixmate_output", help="输出目录")

    args = parser.parse_args()

    if args.command == "analyze":
        cmd_analyze(args)
    elif args.command == "styles":
        cmd_styles(args)
    elif args.command == "plan":
        cmd_plan(args)
    elif args.command == "auto":
        cmd_auto(args)
    elif args.command == "web":
        cmd_web(args)
    else:
        parser.print_help()
        print(f"\n💡 快速开始: mixmate web    # 启动 Web UI")
        print(f"   命令行: mixmate auto your_video.mp4 --style tiktok_flash")


if __name__ == "__main__":
    main()
