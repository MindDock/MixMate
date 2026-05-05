import os
import json
import base64
from typing import List, Dict, Any, Optional
from .base import VisionProvider, SceneUnderstanding


SCENE_ANALYSIS_PROMPT = """你是一个专业的视频内容分析师。请分析这个视频帧/镜头，返回JSON格式的内容描述。

必须返回以下JSON结构（不要返回其他内容）：
{
    "description": "一句话描述这个镜头在做什么",
    "actions": ["动作1", "动作2"],
    "objects": ["主要物体1", "主要物体2"],
    "mood": "情绪氛围（如：欢快/紧张/平静/浪漫/悲伤）",
    "scene_type": "场景类型（如：室内/室外/舞台/运动场/街道/自然）",
    "people_count": 人数,
    "is_dancing": 是否在跳舞,
    "is_sports": 是否在运动,
    "is_talking": 是否在说话/对话,
    "is_walking": 是否在行走,
    "is_closeup": 是否是特写镜头,
    "is_landscape": 是否是风景/空镜,
    "is_group_activity": 是否是群体活动,
    "narrative_role": "叙事角色（opening/buildup/climax/transition/ending）",
    "suggested_cut_style": "建议剪辑方式（fast_cut/slow_reveal/beat_sync/flow）",
    "confidence": 0.0到1.0的置信度
}"""

SEGMENT_ANALYSIS_PROMPT = """你是一个专业的视频内容分析师。请分析这组连续视频帧（代表一个镜头片段），返回JSON格式的内容描述。

这是同一个镜头中均匀采样的多帧画面，请综合判断整个镜头的内容。

必须返回以下JSON结构（不要返回其他内容）：
{
    "description": "一句话描述这个镜头在做什么",
    "actions": ["动作1", "动作2"],
    "objects": ["主要物体1", "主要物体2"],
    "mood": "情绪氛围",
    "scene_type": "场景类型",
    "people_count": 人数,
    "is_dancing": 是否在跳舞,
    "is_sports": 是否在运动,
    "is_talking": 是否在说话/对话,
    "is_walking": 是否在行走,
    "is_closeup": 是否是特写镜头,
    "is_landscape": 是否是风景/空镜,
    "is_group_activity": 是否是群体活动,
    "narrative_role": "叙事角色（opening/buildup/climax/transition/ending）",
    "suggested_cut_style": "建议剪辑方式",
    "confidence": 置信度
}"""


class OpenAIVisionProvider(VisionProvider):
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4o",
        base_url: Optional[str] = None,
        max_tokens: int = 500,
    ):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.model = model
        self.base_url = base_url or os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
        self.max_tokens = max_tokens
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI(
                    api_key=self.api_key,
                    base_url=self.base_url,
                )
            except ImportError:
                raise ImportError("请安装 openai: pip install openai")
        return self._client

    def is_available(self) -> bool:
        if not self.api_key:
            return False
        try:
            self._get_client()
            return True
        except Exception:
            return False

    def analyze_frame(self, image_base64: str, prompt: str = "") -> SceneUnderstanding:
        return self._call_vision_api([image_base64], prompt or SCENE_ANALYSIS_PROMPT)

    def analyze_segment(self, frames_base64: List[str], prompt: str = "") -> SceneUnderstanding:
        return self._call_vision_api(frames_base64, prompt or SEGMENT_ANALYSIS_PROMPT)

    def _call_vision_api(self, images: List[str], prompt: str) -> SceneUnderstanding:
        client = self._get_client()

        content = [{"type": "text", "text": prompt}]
        for img_b64 in images:
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{img_b64}",
                    "detail": "low",
                },
            })

        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": content}],
                max_tokens=self.max_tokens,
                temperature=0.1,
            )
            raw = response.choices[0].message.content.strip()
            return self._parse_response(raw)
        except Exception as e:
            return SceneUnderstanding(
                description=f"AI分析失败: {e}",
                confidence=0.0,
                raw_response=str(e),
            )

    def _parse_response(self, raw: str) -> SceneUnderstanding:
        try:
            json_str = raw
            if "```json" in raw:
                json_str = raw.split("```json")[1].split("```")[0]
            elif "```" in raw:
                json_str = raw.split("```")[1].split("```")[0]

            data = json.loads(json_str.strip())

            return SceneUnderstanding(
                description=str(data.get("description", "")),
                actions=data.get("actions", []),
                objects=data.get("objects", []),
                mood=str(data.get("mood", "")),
                scene_type=str(data.get("scene_type", "")),
                people_count=int(data.get("people_count", 0) or 0),
                is_dancing=bool(data.get("is_dancing", False)),
                is_sports=bool(data.get("is_sports", False)),
                is_talking=bool(data.get("is_talking", False)),
                is_walking=bool(data.get("is_walking", False)),
                is_closeup=bool(data.get("is_closeup", False)),
                is_landscape=bool(data.get("is_landscape", False)),
                is_group_activity=bool(data.get("is_group_activity", False)),
                narrative_role=str(data.get("narrative_role", "")),
                suggested_cut_style=str(data.get("suggested_cut_style", "")),
                confidence=float(data.get("confidence", 0.5) or 0.5),
                raw_response=raw,
            )
        except (json.JSONDecodeError, KeyError) as e:
            return SceneUnderstanding(
                description=raw[:200],
                confidence=0.2,
                raw_response=raw,
            )


class LocalVisionProvider(VisionProvider):
    """
    本地视觉理解 Provider - 使用本地多模态模型
    支持 Ollama 运行的本地模型（如 llava, qwen-vl 等）
    """

    def __init__(
        self,
        model: str = "moondream:v2",
        ollama_url: str = "http://localhost:11434",
    ):
        self.model = model
        self.ollama_url = ollama_url.rstrip("/")
        self._resolved_model = None

    def _get_available_models(self) -> list:
        try:
            import urllib.request
            import json as _json
            req = urllib.request.Request(f"{self.ollama_url}/api/tags")
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = _json.loads(resp.read().decode("utf-8"))
                return [m.get("name", "") for m in data.get("models", [])]
        except Exception:
            return []

    def _resolve_model(self) -> str:
        if self._resolved_model:
            return self._resolved_model
        models = self._get_available_models()
        if self.model in models:
            self._resolved_model = self.model
            return self.model
        for m in models:
            if m.startswith(self.model + ":") or m.startswith(self.model + "-"):
                self._resolved_model = m
                return m
        if models:
            self._resolved_model = models[0]
            return models[0]
        return self.model

    def is_available(self) -> bool:
        try:
            models = self._get_available_models()
            if not models:
                return False
            resolved = self._resolve_model()
            return resolved in models
        except Exception:
            return False

    def analyze_frame(self, image_base64: str, prompt: str = "") -> SceneUnderstanding:
        return self._call_ollama([image_base64], prompt or SCENE_ANALYSIS_PROMPT)

    def analyze_segment(self, frames_base64: List[str], prompt: str = "") -> SceneUnderstanding:
        return self._call_ollama(frames_base64[:3], prompt or SEGMENT_ANALYSIS_PROMPT)

    def _call_ollama(self, images: List[str], prompt: str) -> SceneUnderstanding:
        try:
            import urllib.request
            import json as _json

            payload = {
                "model": self._resolve_model(),
                "prompt": prompt,
                "images": images,
                "stream": False,
                "options": {"temperature": 0.1},
            }

            data = _json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                f"{self.ollama_url}/api/generate",
                data=data,
                headers={"Content-Type": "application/json"},
            )

            with urllib.request.urlopen(req, timeout=60) as resp:
                result = _json.loads(resp.read().decode("utf-8"))
                raw = result.get("response", "")

            return self._parse_response(raw)
        except Exception as e:
            return SceneUnderstanding(
                description=f"本地模型分析失败: {e}",
                confidence=0.0,
                raw_response=str(e),
            )

    def _parse_response(self, raw: str) -> SceneUnderstanding:
        try:
            json_str = raw
            if "{" in raw:
                start = raw.index("{")
                end = raw.rindex("}") + 1
                json_str = raw[start:end]

            data = json.loads(json_str)
            return SceneUnderstanding(
                description=str(data.get("description", "")),
                actions=data.get("actions", []),
                objects=data.get("objects", []),
                mood=str(data.get("mood", "")),
                scene_type=str(data.get("scene_type", "")),
                people_count=int(data.get("people_count", 0) or 0),
                is_dancing=bool(data.get("is_dancing", False)),
                is_sports=bool(data.get("is_sports", False)),
                is_talking=bool(data.get("is_talking", False)),
                is_walking=bool(data.get("is_walking", False)),
                is_closeup=bool(data.get("is_closeup", False)),
                is_landscape=bool(data.get("is_landscape", False)),
                is_group_activity=bool(data.get("is_group_activity", False)),
                narrative_role=str(data.get("narrative_role", "")),
                suggested_cut_style=str(data.get("suggested_cut_style", "")),
                confidence=float(data.get("confidence", 0.3) or 0.3),
                raw_response=raw,
            )
        except (json.JSONDecodeError, ValueError):
            return SceneUnderstanding(
                description=raw[:200],
                confidence=0.1,
                raw_response=raw,
            )


class RuleBasedVisionProvider(VisionProvider):
    """
    规则引擎 Provider - 系统默认的回退方案
    基于传统CV算法，不需要AI API
    """

    def is_available(self) -> bool:
        return True

    def analyze_frame(self, image_base64: str, prompt: str = "") -> SceneUnderstanding:
        return SceneUnderstanding(description="规则引擎不支持单帧分析", confidence=0.1)

    def analyze_segment(self, frames_base64: List[str], prompt: str = "") -> SceneUnderstanding:
        return SceneUnderstanding(description="规则引擎不支持多帧分析", confidence=0.1)
