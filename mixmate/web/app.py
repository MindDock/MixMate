import os
import uuid
import json
import threading
from pathlib import Path
from typing import Dict, Optional
from flask import Flask, render_template, request, jsonify, send_file, send_from_directory

from mixmate.analyzer import TimelineAnalyzer
from mixmate.models import TimelineAnalysis, VideoSource, ShotSegment
from mixmate.editor import AutoEditor
from mixmate.config import list_styles, get_style
from mixmate.renderer import FFmpegWrapper, BatchRenderer


UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

app = Flask(
    __name__,
    template_folder=os.path.join(os.path.dirname(__file__), "templates"),
    static_folder=os.path.join(os.path.dirname(__file__), "static"),
)
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024 * 1024


@app.after_request
def add_no_cache_headers(response):
    if response.content_type and (
        "javascript" in response.content_type
        or "css" in response.content_type
        or "html" in response.content_type
    ):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

LAST_ANALYSIS_PATH = os.path.join(OUTPUT_DIR, "last_analysis.json")

tasks: Dict[str, dict] = {}


def _save_last_analysis(analysis_dict: dict):
    try:
        with open(LAST_ANALYSIS_PATH, "w", encoding="utf-8") as f:
            json.dump(analysis_dict, f, ensure_ascii=False)
    except Exception:
        pass


def _load_last_analysis() -> Optional[dict]:
    try:
        if os.path.exists(LAST_ANALYSIS_PATH):
            with open(LAST_ANALYSIS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return None


def _task_worker(task_id: str, video_paths: list, styles: list, count: int, duration: float, bg_music: Optional[str]):
    try:
        tasks[task_id]["status"] = "analyzing"
        tasks[task_id]["progress"] = 10
        tasks[task_id]["message"] = "正在分析素材..."

        analyzer = TimelineAnalyzer(use_ai=True)
        analysis = analyzer.analyze_multiple(video_paths, save_thumbnails=False)

        report_path = os.path.join(OUTPUT_DIR, task_id, "analysis_report.json")
        os.makedirs(os.path.dirname(report_path), exist_ok=True)
        analyzer.save_report(analysis, report_path)

        tasks[task_id]["status"] = "planning"
        tasks[task_id]["progress"] = 40
        tasks[task_id]["message"] = "正在生成剪辑方案..."
        tasks[task_id]["analysis"] = analysis.to_dict()

        plans = []
        for style_name in styles:
            for v in range(count):
                try:
                    editor = AutoEditor(style_name)
                    plan_name = f"{style_name}_v{v+1}"
                    plan = editor.create_edit_plan(analysis, target_duration=duration, plan_name=plan_name)
                    plans.append(plan)

                    plan_path = os.path.join(OUTPUT_DIR, task_id, f"plan_{plan_name}.json")
                    editor.save_plan(plan, plan_path)
                except Exception as e:
                    tasks[task_id]["warnings"] = tasks[task_id].get("warnings", [])
                    tasks[task_id]["warnings"].append(f"风格 {style_name} 方案失败: {e}")

        tasks[task_id]["status"] = "rendering"
        tasks[task_id]["progress"] = 60
        tasks[task_id]["message"] = "正在渲染视频..."
        tasks[task_id]["plan_count"] = len(plans)

        task_output_dir = os.path.join(OUTPUT_DIR, task_id)
        os.makedirs(task_output_dir, exist_ok=True)

        ffmpeg = FFmpegWrapper()
        results = []
        for i, plan in enumerate(plans):
            try:
                filename = f"{plan.name}.mp4"
                output_path = os.path.join(task_output_dir, filename)
                result = ffmpeg.render_plan(plan, output_path, background_music=bg_music)
                results.append({
                    "name": plan.name,
                    "style": plan.style,
                    "duration": round(result.duration, 1),
                    "file_size": result.file_size,
                    "filename": filename,
                })
            except Exception as e:
                tasks[task_id]["warnings"] = tasks[task_id].get("warnings", [])
                tasks[task_id]["warnings"].append(f"渲染 {plan.name} 失败: {e}")

            pct = 60 + int(35 * (i + 1) / max(len(plans), 1))
            tasks[task_id]["progress"] = min(pct, 95)
            tasks[task_id]["message"] = f"渲染中 ({i+1}/{len(plans)})..."

        tasks[task_id]["status"] = "done"
        tasks[task_id]["progress"] = 100
        tasks[task_id]["message"] = f"完成！共生成 {len(results)} 条视频"
        tasks[task_id]["results"] = results

    except Exception as e:
        tasks[task_id]["status"] = "error"
        tasks[task_id]["progress"] = 0
        tasks[task_id]["message"] = f"任务失败: {str(e)}"


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/styles", methods=["GET"])
def api_styles():
    return jsonify({"styles": list_styles()})


@app.route("/api/upload", methods=["POST"])
def api_upload():
    files = request.files.getlist("videos")
    if not files:
        return jsonify({"error": "未选择文件"}), 400

    uploaded = []
    for f in files:
        if f.filename == "":
            continue
        ext = os.path.splitext(f.filename)[1].lower()
        if ext not in (".mp4", ".mov", ".avi", ".mkv", ".flv", ".webm", ".m4v"):
            continue
        uid = str(uuid.uuid4())[:8]
        safe_name = f"{uid}_{f.filename}"
        save_path = os.path.join(UPLOAD_DIR, safe_name)
        f.save(save_path)
        uploaded.append({"name": f.filename, "path": save_path, "id": uid})

    return jsonify({"files": uploaded, "count": len(uploaded)})


@app.route("/api/uploaded-files", methods=["GET"])
def api_uploaded_files():
    files = []
    for f in os.listdir(UPLOAD_DIR):
        fpath = os.path.join(UPLOAD_DIR, f)
        if os.path.isfile(fpath) and f.lower().endswith(('.mp4', '.mov', '.avi', '.mkv', '.flv', '.webm', '.m4v')):
            name = f.split('_', 1)[-1] if '_' in f else f
            uid = f.split('_')[0] if '_' in f else ''
            files.append({"name": name, "path": fpath, "id": uid})
    return jsonify({"files": files, "count": len(files)})


@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    data = request.get_json()
    video_paths = data.get("videos", [])
    if not video_paths:
        return jsonify({"error": "未提供视频路径"}), 400

    task_id = str(uuid.uuid4())[:12]
    tasks[task_id] = {
        "status": "analyzing",
        "progress": 5,
        "message": "正在分析素材...",
        "results": [],
        "warnings": [],
        "analysis": None,
    }

    thread = threading.Thread(
        target=_analyze_worker,
        args=(task_id, video_paths),
        daemon=True,
    )
    thread.start()

    return jsonify({"task_id": task_id})


def _analyze_worker(task_id: str, video_paths: list):
    try:
        total = len(video_paths)
        tasks[task_id]["message"] = f"准备分析 {total} 个视频..."
        tasks[task_id]["progress"] = 5
        tasks[task_id]["video_progress"] = []

        analyzer = TimelineAnalyzer(use_ai=True)

        analysis = TimelineAnalysis()

        for i, path in enumerate(video_paths):
            fname = os.path.basename(path)
            short_name = fname.split('_', 1)[-1] if '_' in fname else fname

            video_prog = {
                "name": short_name,
                "status": "processing",
                "step": "初始化",
                "step_index": 0,
                "total_steps": 5,
            }
            tasks[task_id]["video_progress"].append(video_prog)

            base_pct = 10 + int((i / total) * 80)
            tasks[task_id]["progress"] = base_pct
            tasks[task_id]["message"] = f"正在分析第 {i+1}/{total} 个视频: {short_name}"

            info = analyzer.audio_analyzer.get_video_info(path)
            video_stream = None
            audio_stream = None
            for stream in info.get("streams", []):
                if stream["codec_type"] == "video" and video_stream is None:
                    video_stream = stream
                elif stream["codec_type"] == "audio" and audio_stream is None:
                    audio_stream = stream

            if video_stream is None:
                video_prog["status"] = "error"
                video_prog["step"] = "无法读取视频流"
                continue

            fps = eval(video_stream.get("r_frame_rate", "30/1"))
            width = int(video_stream.get("width", 0))
            height = int(video_stream.get("height", 0))
            duration = float(info.get("format", {}).get("duration", 0))

            video_prog["resolution"] = f"{width}x{height}"
            video_prog["fps"] = round(fps, 1)
            video_prog["duration"] = round(duration, 1)

            source = VideoSource(
                file_path=path,
                duration=duration,
                fps=fps,
                width=width,
                height=height,
                codec=video_stream.get("codec_name", "unknown"),
                audio_codec=audio_stream.get("codec_name", "") if audio_stream else "",
            )

            # Step 1: 镜头分割
            video_prog["step"] = "镜头分割"
            video_prog["step_index"] = 1
            tasks[task_id]["progress"] = base_pct + int((1 / 5) * (80 / total))

            shot_segments = analyzer.shot_detector.detect_shots(path)
            video_prog["shot_count"] = len(shot_segments)

            # Step 2: 音频提取
            video_prog["step"] = "音频提取"
            video_prog["step_index"] = 2
            tasks[task_id]["progress"] = base_pct + int((2 / 5) * (80 / total))

            audio_path = None
            if audio_stream:
                try:
                    audio_path = analyzer.audio_analyzer.extract_audio(path)
                except Exception:
                    pass

            # Step 3: 节拍检测
            video_prog["step"] = "节拍检测"
            video_prog["step_index"] = 3
            tasks[task_id]["progress"] = base_pct + int((3 / 5) * (80 / total))

            global_beats = []
            if audio_path:
                try:
                    global_beats = analyzer.audio_analyzer.detect_beats(audio_path)
                    video_prog["beat_count"] = len(global_beats)
                except Exception:
                    pass

            # Step 4: 逐镜头分析
            video_prog["step"] = "运动分析 + 内容标签"
            video_prog["step_index"] = 4
            tasks[task_id]["progress"] = base_pct + int((4 / 5) * (80 / total))

            for idx, (start_frame, end_frame) in enumerate(shot_segments):
                start_time = start_frame / fps
                end_time = end_frame / fps

                segment = ShotSegment(
                    index=idx,
                    start_time=start_time,
                    end_time=end_time,
                    start_frame=start_frame,
                    end_frame=end_frame,
                    source_file=path,
                )

                try:
                    motion_score, motion_intensity, shot_type, sharpness, stability = (
                        analyzer.motion_analyzer.analyze_segment_motion(path, start_frame, end_frame)
                    )
                    segment.motion_score = motion_score
                    segment.motion_intensity = motion_intensity
                    segment.shot_type = shot_type
                    segment.sharpness = sharpness
                    segment.stability_score = stability
                except Exception:
                    pass

                try:
                    brightness, dominant_color = analyzer.motion_analyzer.analyze_brightness_and_color(
                        path, start_frame, end_frame
                    )
                    segment.brightness = brightness
                    segment.color_dominant = dominant_color
                except Exception:
                    pass

                if audio_path:
                    try:
                        energy, has_speech, has_music, beats = (
                            analyzer.audio_analyzer.analyze_segment_audio(
                                audio_path, start_time, end_time,
                                global_beats=global_beats,
                            )
                        )
                        segment.audio_energy = energy
                        segment.has_speech = has_speech
                        segment.has_music = has_music
                        segment.beat_positions = beats
                    except Exception:
                        pass

                try:
                    segment = analyzer.content_tagger.tag_segment(segment, path)
                except Exception:
                    pass

                source.segments.append(segment)

            if audio_path and os.path.exists(audio_path):
                try:
                    os.unlink(audio_path)
                except Exception:
                    pass

            # Step 5: 完成
            video_prog["step"] = "完成"
            video_prog["step_index"] = 5
            video_prog["status"] = "done"
            tasks[task_id]["progress"] = base_pct + int((5 / 5) * (80 / total))

            analysis.sources.append(source)
            analysis.all_segments.extend(source.segments)
            analysis.total_duration += source.duration

        if analysis.sources:
            first_source = analysis.sources[0]
            if first_source.segments:
                audio_path = None
                try:
                    audio_path = analyzer.audio_analyzer.extract_audio(first_source.file_path)
                    analysis.global_beats = analyzer.audio_analyzer.detect_beats(audio_path)
                except Exception:
                    pass
                finally:
                    if audio_path and os.path.exists(audio_path):
                        try:
                            os.unlink(audio_path)
                        except Exception:
                            pass

        tasks[task_id]["status"] = "done"
        tasks[task_id]["progress"] = 100
        tasks[task_id]["message"] = f"分析完成！共 {len(analysis.all_segments)} 个镜头"
        analysis_dict = analysis.to_dict()
        tasks[task_id]["analysis"] = analysis_dict
        _save_last_analysis(analysis_dict)
    except Exception as e:
        import traceback
        traceback.print_exc()
        tasks[task_id]["status"] = "error"
        tasks[task_id]["progress"] = 0
        tasks[task_id]["message"] = f"分析失败: {str(e)}"


@app.route("/api/render", methods=["POST"])
def api_render():
    data = request.get_json()
    video_paths = data.get("videos", [])
    styles = data.get("styles", ["tiktok_flash"])
    count = data.get("count", 1)
    duration = data.get("duration", 15.0)
    bg_music = data.get("bg_music", None)

    if not video_paths:
        return jsonify({"error": "未提供视频路径"}), 400

    task_id = str(uuid.uuid4())[:12]
    tasks[task_id] = {
        "status": "queued",
        "progress": 0,
        "message": "任务已排队...",
        "results": [],
        "warnings": [],
    }

    thread = threading.Thread(
        target=_task_worker,
        args=(task_id, video_paths, styles, count, duration, bg_music),
        daemon=True,
    )
    thread.start()

    return jsonify({"task_id": task_id})


@app.route("/api/last-analysis", methods=["GET"])
def api_last_analysis():
    analysis = _load_last_analysis()
    if analysis:
        return jsonify({"has_analysis": True, "analysis": analysis})
    return jsonify({"has_analysis": False})


@app.route("/api/last-analysis", methods=["DELETE"])
def api_clear_last_analysis():
    try:
        if os.path.exists(LAST_ANALYSIS_PATH):
            os.remove(LAST_ANALYSIS_PATH)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/active-task", methods=["GET"])
def api_active_task():
    for tid, t in tasks.items():
        if t.get("status") in ("analyzing", "planning", "rendering", "queued"):
            return jsonify({"has_active": True, "task_id": tid, "status": t["status"], "progress": t.get("progress", 0), "message": t.get("message", "")})
    return jsonify({"has_active": False})


@app.route("/api/video", methods=["GET"])
def api_video_stream():
    filepath = request.args.get("path", "")
    if not filepath or not os.path.exists(filepath):
        return jsonify({"error": "文件不存在"}), 404
    resp = send_file(filepath, mimetype="video/mp4")
    resp.headers["Accept-Ranges"] = "bytes"
    return resp


@app.route("/api/thumbnail", methods=["GET"])
def api_thumbnail():
    filepath = request.args.get("path", "")
    if not filepath or not os.path.exists(filepath):
        return jsonify({"error": "文件不存在"}), 404
    thumb_dir = os.path.join(OUTPUT_DIR, "thumbnails")
    os.makedirs(thumb_dir, exist_ok=True)
    thumb_hash = str(hash(filepath)) + "_" + os.path.basename(filepath)
    thumb_path = os.path.join(thumb_dir, thumb_hash + ".jpg")
    if os.path.exists(thumb_path):
        return send_file(thumb_path, mimetype="image/jpeg")
    try:
        ffmpeg = FFmpegWrapper()
        ffmpeg.extract_thumbnail(filepath, thumb_path, time_offset=1.0)
        if os.path.exists(thumb_path):
            return send_file(thumb_path, mimetype="image/jpeg")
    except Exception:
        pass
    return jsonify({"error": "缩略图生成失败"}), 404


@app.route("/api/task/<task_id>", methods=["GET"])
def api_task_status(task_id):
    if task_id not in tasks:
        return jsonify({"error": "任务不存在"}), 404
    return jsonify(tasks[task_id])


@app.route("/api/download/<task_id>/<filename>", methods=["GET"])
def api_download(task_id, filename):
    file_path = os.path.join(OUTPUT_DIR, task_id, filename)
    if not os.path.exists(file_path):
        return jsonify({"error": "文件不存在"}), 404
    return send_file(file_path, as_attachment=True)


@app.route("/api/ffmpeg-check", methods=["GET"])
def api_ffmpeg_check():
    ffmpeg = FFmpegWrapper()
    return jsonify({"available": ffmpeg.check_available()})


@app.route("/api/ai/config", methods=["GET"])
def api_ai_config():
    from mixmate.ai import load_config
    config = load_config()
    return jsonify({"config": config})


@app.route("/api/ai/config", methods=["POST"])
def api_ai_config_save():
    from mixmate.ai import save_config
    try:
        data = request.get_json()
        config = data.get("config", {})
        save_config(config)
        return jsonify({"ok": True, "message": "AI配置已保存"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/ai/check", methods=["GET"])
def api_ai_check():
    from mixmate.ai import AIProviderFactory, load_config
    config = load_config()

    vision = AIProviderFactory.create_vision_provider(config.get("vision"))
    speech = AIProviderFactory.create_speech_provider(config.get("speech"))
    narrative = AIProviderFactory.create_narrative_provider(config.get("narrative"))

    return jsonify({
        "vision": {
            "available": vision.is_available(),
            "provider": config.get("vision", {}).get("provider", "rule_based"),
        },
        "speech": {
            "available": speech.is_available(),
            "provider": config.get("speech", {}).get("provider", "simple"),
        },
        "narrative": {
            "available": narrative.is_available(),
            "provider": config.get("narrative", {}).get("provider", "rule_based"),
        },
    })


def run_server(host: str = "0.0.0.0", port: int = 5000, debug: bool = False):
    print(f"\n🎬 MixMate Web UI 启动中...")
    print(f"   地址: http://localhost:{port}")
    print(f"   按 Ctrl+C 停止\n")
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    run_server(debug=True)
