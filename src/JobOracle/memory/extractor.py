from __future__ import annotations

import json
import re
from typing import Any

from ..llm_client import EmploymentLLMClient
from ..profile import normalize_profile


class ProfileExtractor:
    PROFILE_EXTRACTION_SYSTEM_PROMPT = """你是一名用户画像抽取助手。

你的任务：
1. 根据最新用户消息、最近几轮上下文和已有画像，提取与求职咨询相关的结构化画像字段。
2. 只输出 JSON object，不要输出解释文字，不要输出 Markdown。
3. 如果某个字段无法确认，就不要输出该字段。
4. 不要凭空猜测；模糊信息宁可不填。
5. 列表字段请输出 JSON 数组。

允许输出的字段：
- education
- school
- major
- graduation_year
- target_cities
- target_roles
- skills
- internship
- projects
- preferred_industries
"""

    def __init__(self, llm_client: EmploymentLLMClient | None = None):
        self.llm_client = llm_client

    def merge_profile(self, existing: dict[str, Any], new_data: dict[str, Any]) -> dict[str, Any]:
        merged = dict(existing)
        for key, value in new_data.items():
            if value in (None, "", [], ()):
                continue
            if isinstance(value, list):
                existing_values = merged.get(key, [])
                if not isinstance(existing_values, list):
                    existing_values = [existing_values] if existing_values else []
                merged[key] = self._merge_list(existing_values, value)
                continue
            merged[key] = value
        return normalize_profile(merged)

    def extract_profile(
        self,
        content: str,
        *,
        existing_profile: dict[str, Any] | None = None,
        recent_messages: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        payload = self._extract_json_profile(content)
        inferred = self._infer_profile_from_text(content)
        rule_based = self.merge_profile(inferred, payload)
        llm_based = self._extract_profile_with_llm(
            content,
            existing_profile=existing_profile or {},
            recent_messages=recent_messages or [],
        )
        if llm_based:
            return self.merge_profile(rule_based, llm_based)
        return rule_based

    def _merge_list(self, existing: list[Any], incoming: list[Any]) -> list[str]:
        merged: list[str] = []
        for item in [*existing, *incoming]:
            text = " ".join(str(item).strip().split())
            if text and text not in merged:
                merged.append(text)
        return merged

    def _extract_json_profile(self, content: str) -> dict[str, Any]:
        if not content.strip().startswith("{"):
            return {}
        try:
            payload = json.loads(content)
        except Exception:
            return {}
        if not isinstance(payload, dict):
            return {}
        return normalize_profile(payload)

    def _extract_profile_with_llm(
        self,
        content: str,
        *,
        existing_profile: dict[str, Any],
        recent_messages: list[dict[str, str]],
    ) -> dict[str, Any]:
        if self.llm_client is None or not self.llm_client.config.llm_enabled:
            return {}
        user_messages = [
            f"- {item.get('role', 'unknown')}: {item.get('content', '')}"
            for item in recent_messages[-6:]
        ]
        profile_block = json.dumps(existing_profile, ensure_ascii=False, indent=2) if existing_profile else "{}"
        prompt = f"""请根据下面信息提取用户画像增量。

最新用户消息：
{content}

已有画像：
```json
{profile_block}
```

最近几轮对话：
{chr(10).join(user_messages) if user_messages else "无"}

请直接输出 JSON object。"""
        try:
            raw = self.llm_client.generate_text(
                self.PROFILE_EXTRACTION_SYSTEM_PROMPT,
                prompt,
                temperature=0.1,
            )
        except Exception:
            return {}
        parsed = self._parse_json_object(raw)
        if not parsed:
            return {}
        try:
            return normalize_profile(parsed)
        except Exception:
            return {}

    def _infer_profile_from_text(self, content: str) -> dict[str, Any]:
        profile: dict[str, Any] = {}
        compact = " ".join(content.strip().split())

        education_tokens = ("博士", "硕士", "研究生", "本科", "专科", "大专")
        for token in education_tokens:
            if token in compact:
                profile["education"] = "硕士" if token == "研究生" else ("专科" if token == "大专" else token)
                break

        year_match = re.search(r"(20\d{2})\s*年?(毕业|应届)?", compact)
        if year_match:
            profile["graduation_year"] = year_match.group(1)

        cities = ["深圳", "广州", "杭州", "上海", "北京", "成都", "武汉", "南京", "苏州", "西安"]
        target_cities = [city for city in cities if city in compact]
        if target_cities:
            profile["target_cities"] = target_cities

        role_map = {
            "数据分析": "数据分析",
            "商业分析": "商业分析",
            "算法": "算法",
            "机器学习": "机器学习",
            "产品": "产品",
            "运营": "运营",
            "前端": "前端开发",
            "后端": "后端开发",
            "开发": "开发",
            "测试": "测试",
        }
        target_roles = [value for key, value in role_map.items() if key in compact]
        if target_roles:
            profile["target_roles"] = target_roles

        skills = []
        for token in ("Python", "SQL", "Tableau", "Excel", "Power BI", "机器学习", "深度学习", "Pandas"):
            if token.lower() in compact.lower():
                skills.append(token)
        if skills:
            profile["skills"] = skills

        major_match = re.search(r"(统计学|计算机|软件工程|人工智能|经济学|金融|数学|信息管理|电子信息)", compact)
        if major_match:
            profile["major"] = major_match.group(1)

        school_match = re.search(r"([\u4e00-\u9fff]{2,20}(大学|学院))", compact)
        if school_match:
            profile["school"] = school_match.group(1)

        internship_match = re.search(r"(.{0,20}(实习|intern).{0,20})", compact, re.IGNORECASE)
        if internship_match:
            profile["internship"] = internship_match.group(1).strip("，。 ")

        return normalize_profile(profile)

    def _parse_json_object(self, raw: str) -> dict[str, Any]:
        text = raw.strip()
        try:
            parsed = json.loads(text)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            pass
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            return {}
        try:
            parsed = json.loads(match.group(0))
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
