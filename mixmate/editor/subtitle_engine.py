from typing import List, Dict, Any, Optional
from ..models import EditDecision, ContentTag


class SubtitleEngine:
    """
    字幕引擎 - 根据内容标签和风格生成字幕
    支持多种字幕样式和动画效果
    """

    CONTENT_LABELS: Dict[str, str] = {
        "dance": "💃 舞蹈",
        "sports": "🏅 运动",
        "talking": "🗣 对话",
        "walking": "🚶 行走",
        "closeup": "🔍 特写",
        "landscape": "🌄 风景",
        "group": "👥 群像",
        "solo": "👤 独角",
        "action": "⚡ 动作",
        "emotion": "😊 情感",
        "intro": "🎬 开场",
        "outro": "🎬 结尾",
        "broll": "📹 空镜",
        "music": "🎵 音乐",
    }

    STYLE_TEMPLATES: Dict[str, Dict[str, Any]] = {
        "tiktok": {
            "fontfile": "/System/Library/Fonts/PingFang.ttc",
            "fontsize": 24,
            "fontcolor": "white",
            "borderw": 2,
            "bordercolor": "black",
            "box": 1,
            "boxcolor": "black@0.5",
            "boxborderw": 5,
            "x": "(w-text_w)/2",
            "y": "h-th-40",
        },
        "cinematic": {
            "fontfile": "/System/Library/Fonts/PingFang.ttc",
            "fontsize": 18,
            "fontcolor": "white",
            "borderw": 1,
            "bordercolor": "black@0.8",
            "x": "(w-text_w)/2",
            "y": "h-th-80",
        },
        "vlog": {
            "fontfile": "/System/Library/Fonts/PingFang.ttc",
            "fontsize": 20,
            "fontcolor": "white",
            "borderw": 1,
            "bordercolor": "black@0.6",
            "box": 1,
            "boxcolor": "black@0.4",
            "boxborderw": 3,
            "x": "30",
            "y": "h-th-40",
        },
        "impact": {
            "fontfile": "/System/Library/Fonts/PingFang.ttc",
            "fontsize": 32,
            "fontcolor": "yellow",
            "borderw": 3,
            "bordercolor": "black",
            "x": "(w-text_w)/2",
            "y": "(h-text_h)/2",
        },
        "minimal": {
            "fontfile": "/System/Library/Fonts/PingFang.ttc",
            "fontsize": 16,
            "fontcolor": "white@0.8",
            "borderw": 1,
            "bordercolor": "black@0.5",
            "x": "(w-text_w)/2",
            "y": "h-th-30",
        },
        "lyrics": {
            "fontfile": "/System/Library/Fonts/PingFang.ttc",
            "fontsize": 22,
            "fontcolor": "white",
            "borderw": 2,
            "bordercolor": "black@0.7",
            "box": 1,
            "boxcolor": "black@0.5",
            "boxborderw": 5,
            "x": "(w-text_w)/2",
            "y": "(h-text_h)/2",
        },
    }

    @classmethod
    def generate_subtitle_text(cls, decision: EditDecision) -> str:
        tags = decision.segment.content_tags
        if not tags:
            return ""

        primary_tag = tags[0].value if tags else ""
        return cls.CONTENT_LABELS.get(primary_tag, "")

    @classmethod
    def build_drawtext_filter(
        cls,
        text: str,
        style_name: str = "tiktok",
        enable_start: float = 0.0,
        enable_end: float = 1.0,
    ) -> str:
        if not text:
            return ""

        template = cls.STYLE_TEMPLATES.get(style_name, cls.STYLE_TEMPLATES["tiktok"])

        escaped_text = text.replace("'", "\\'").replace(":", "\\:")

        params = []
        params.append(f"text='{escaped_text}'")

        for key in ["fontfile", "fontsize", "fontcolor", "borderw", "bordercolor",
                     "box", "boxcolor", "boxborderw", "x", "y"]:
            if key in template:
                val = template[key]
                if isinstance(val, str) and not val.startswith("(") and key not in ("fontfile",):
                    params.append(f"{key}={val}")
                else:
                    params.append(f"{key}={val}")

        if enable_start > 0 or enable_end > 0:
            params.append(f"enable='between(t,{enable_start:.3f},{enable_end:.3f})'")

        return f"drawtext={':'.join(params)}"

    @classmethod
    def generate_srt_file(
        cls,
        decisions: List[EditDecision],
        style_name: str = "tiktok",
        output_path: str = "subtitles.srt",
    ) -> str:
        entries = []
        current_time = 0.0

        for i, decision in enumerate(decisions):
            text = cls.generate_subtitle_text(decision)
            if not text:
                current_time += decision.effective_duration
                continue

            start = current_time
            end = current_time + decision.effective_duration

            start_fmt = cls._format_srt_time(start)
            end_fmt = cls._format_srt_time(end)

            entry = f"{i + 1}\n{start_fmt} --> {end_fmt}\n{text}\n"
            entries.append(entry)

            current_time = end

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(entries))

        return output_path

    @classmethod
    def _format_srt_time(cls, seconds: float) -> str:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
