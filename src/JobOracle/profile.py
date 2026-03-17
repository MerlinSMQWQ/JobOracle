from __future__ import annotations

from typing import Any


PROFILE_KEY_ALIASES: dict[str, tuple[str, ...]] = {
    "education": ("education", "学历"),
    "school": ("school", "学校", "院校"),
    "major": ("major", "专业"),
    "graduation_year": ("graduation_year", "毕业年份", "毕业时间"),
    "target_cities": ("target_cities", "cities", "目标城市", "意向城市"),
    "target_roles": ("target_roles", "roles", "目标岗位", "意向岗位"),
    "skills": ("skills", "技能", "技术栈"),
    "internship": ("internship", "internships", "实习经历"),
    "projects": ("projects", "项目经历"),
    "preferred_industries": ("preferred_industries", "industries", "目标行业", "意向行业"),
}

ORDERED_PROFILE_FIELDS = (
    "education",
    "school",
    "major",
    "graduation_year",
    "target_cities",
    "target_roles",
    "skills",
    "internship",
    "projects",
    "preferred_industries",
)


def normalize_profile(raw: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("profile 必须是 JSON object")

    normalized: dict[str, Any] = {}
    for canonical_key, aliases in PROFILE_KEY_ALIASES.items():
        value = _first_present_value(raw, aliases)
        if value in (None, "", [], ()):
            continue
        if canonical_key in {"target_cities", "target_roles", "skills", "preferred_industries"}:
            items = _normalize_list(value)
            if items:
                normalized[canonical_key] = items
            continue
        if canonical_key in {"internship", "projects"}:
            items = _normalize_list(value)
            if not items:
                continue
            normalized[canonical_key] = items if len(items) > 1 else items[0]
            continue
        text = _normalize_text(value)
        if text:
            normalized[canonical_key] = text

    for key, value in raw.items():
        if any(key in aliases for aliases in PROFILE_KEY_ALIASES.values()):
            continue
        if value in (None, "", [], ()):
            continue
        normalized[key] = value

    return {key: normalized[key] for key in ORDERED_PROFILE_FIELDS if key in normalized} | {
        key: value for key, value in normalized.items() if key not in ORDERED_PROFILE_FIELDS
    }


def summarize_profile(profile: dict[str, Any]) -> str:
    if not profile:
        return "未提供"

    parts: list[str] = []
    for key in ORDERED_PROFILE_FIELDS:
        value = profile.get(key)
        if value in (None, "", [], ()):
            continue
        label = _field_label(key)
        if isinstance(value, list):
            parts.append(f"{label}: {', '.join(str(item) for item in value)}")
        else:
            parts.append(f"{label}: {value}")

    extras = [key for key in profile.keys() if key not in ORDERED_PROFILE_FIELDS]
    if extras:
        parts.append(f"其他字段: {', '.join(extras)}")

    return " | ".join(parts) if parts else "未提供"


def _first_present_value(raw: dict[str, Any], aliases: tuple[str, ...]) -> Any:
    for key in aliases:
        if key in raw:
            return raw[key]
    return None


def _normalize_list(value: Any) -> list[str]:
    if isinstance(value, list):
        items = value
    elif isinstance(value, tuple):
        items = list(value)
    elif isinstance(value, str):
        items = value.replace("、", ",").replace("，", ",").split(",")
    else:
        items = [value]

    normalized: list[str] = []
    for item in items:
        text = _normalize_text(item)
        if text and text not in normalized:
            normalized.append(text)
    return normalized


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).strip().split())


def _field_label(key: str) -> str:
    labels = {
        "education": "学历",
        "school": "学校",
        "major": "专业",
        "graduation_year": "毕业年份",
        "target_cities": "目标城市",
        "target_roles": "目标岗位",
        "skills": "技能",
        "internship": "实习经历",
        "projects": "项目经历",
        "preferred_industries": "目标行业",
    }
    return labels.get(key, key)
