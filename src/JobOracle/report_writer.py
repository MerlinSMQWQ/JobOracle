from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path


def slugify(value: str, limit: int = 40) -> str:
    cleaned = re.sub(r"[^\w\u4e00-\u9fff-]+", "_", value).strip("_")
    return (cleaned or "employment_report")[:limit]


def save_markdown(report_dir: Path, query: str, markdown: str) -> str:
    report_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = report_dir / f"{timestamp}_{slugify(query)}.md"
    file_path.write_text(markdown, encoding="utf-8")
    return str(file_path)
