import os
import json
from typing import List, Dict, Any, Optional
from .base import NarrativeProvider


NARRATIVE_PLANNING_PROMPT = """你是一个专业的视频剪辑导演。根据以下镜头分析数据，规划一个{style}风格的视频剪辑方案。

目标时长: {duration}秒
风格要求: {style_description}

镜头数据:
{scenes_data}

请返回JSON格式的剪辑方案（不要返回其他内容）：
{{
    "narrative_structure": "叙事结构描述",
    "highlight_segments": [0, 2, 5],
    "suggested_order": [2, 0, 5, 1, 3, 4],
    "cut_rhythm": "fast/medium/slow",
    "speed_suggestions": {{"0": 1.0, "2": 0.5, "5": 1.5}},
    "transition_suggestions": {{"0": "cut", "2": "crossfade"}},
    "subtitle_suggestions": {{"0": "开场", "5": "高潮"}},
    "overall_mood": "整体情绪",
    "pacing_notes": "节奏说明"
}}"""


class OpenAINarrativeProvider(NarrativeProvider):
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4o",
        base_url: Optional[str] = None,
    ):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.model = model
        self.base_url = base_url or os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
        self._client = None

    def _get_client(self):
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        return self._client

    def is_available(self) -> bool:
        return bool(self.api_key)

    def plan_narrative(self, scenes: List[Dict], style: str, duration: float) -> Dict[str, Any]:
        client = self._get_client()

        from ..config import get_style
        try:
            style_config = get_style(style)
            style_desc = f"{style_config.display_name} - {style_config.description}"
        except ValueError:
            style_desc = style

        scenes_data = json.dumps(scenes, ensure_ascii=False, indent=2)
        prompt = NARRATIVE_PLANNING_PROMPT.format(
            style=style,
            duration=duration,
            style_description=style_desc,
            scenes_data=scenes_data,
        )

        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1000,
                temperature=0.3,
            )
            raw = response.choices[0].message.content.strip()
            return self._parse_response(raw)
        except Exception as e:
            return {"error": str(e), "narrative_structure": "AI规划失败，使用默认方案"}

    def _parse_response(self, raw: str) -> Dict[str, Any]:
        try:
            json_str = raw
            if "```json" in raw:
                json_str = raw.split("```json")[1].split("```")[0]
            elif "```" in raw:
                json_str = raw.split("```")[1].split("```")[0]
            return json.loads(json_str.strip())
        except (json.JSONDecodeError, KeyError):
            return {"narrative_structure": raw[:200], "raw_response": raw}


class RuleBasedNarrativeProvider(NarrativeProvider):
    def is_available(self) -> bool:
        return True

    def plan_narrative(self, scenes: List[Dict], style: str, duration: float) -> Dict[str, Any]:
        high_motion = [s for s in scenes if s.get("motion_score", 0) > 0.5]
        low_motion = [s for s in scenes if s.get("motion_score", 0) <= 0.5]

        if style in ("tiktok_flash", "sports_hype", "music_video"):
            ordered = high_motion + low_motion
        elif style in ("cinematic", "chill_aesthetic"):
            ordered = low_motion + high_motion
        else:
            ordered = scenes

        return {
            "narrative_structure": "规则引擎默认排序",
            "highlight_segments": [i for i, s in enumerate(ordered) if s.get("quality_score", 0) > 0.6],
            "suggested_order": list(range(len(ordered))),
            "cut_rhythm": "fast" if style in ("tiktok_flash", "sports_hype") else "medium",
            "speed_suggestions": {},
            "transition_suggestions": {},
            "subtitle_suggestions": {},
            "overall_mood": "auto",
            "pacing_notes": "基于运动强度自动排序",
        }
