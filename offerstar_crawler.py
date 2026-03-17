from __future__ import annotations

import argparse
import csv
import json
import math
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable
from urllib.parse import urlencode, urljoin

import requests
from bs4 import BeautifulSoup


BASE_URL = "https://www.offerstar.cn/recruitment"
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


@dataclass(slots=True)
class OfferStarJob:
    company: str = ""
    industry: str = ""
    work_location: str = ""
    positions: str = ""
    update_time: str = ""
    recruitment_type: str = ""
    deadline: str = ""
    apply_url: str = ""
    source_url: str = ""
    source_page: int = 1


@dataclass(slots=True)
class OfferStarQuery:
    question: str = ""
    industry: str = ""
    work_location: str = ""
    company: str = ""
    positions: str = ""
    page_from: int = 1
    page_to: int = 1
    max_items: int = 20
    timeout_seconds: int = 20
    target_rows_per_10s: int = 20
    output_dir: Path = Path("jobs_dataset")


class OfferStarCrawler:
    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)

    def infer_query(self, question: str) -> OfferStarQuery:
        question = question.strip()
        city = self._infer_city(question)
        company = self._infer_company(question)
        positions = self._infer_position(question)
        industry = self._infer_industry(question)
        return OfferStarQuery(
            question=question,
            industry=industry,
            work_location=city,
            company=company,
            positions=positions,
        )

    def crawl(
        self,
        query: OfferStarQuery,
        progress_callback: callable | None = None, # type: ignore
    ) -> list[OfferStarJob]:
        self._emit(progress_callback, "start", f"开始抓取 OfferStar，页码 {query.page_from}-{query.page_to}", 0)
        jobs: list[OfferStarJob] = []
        seen_keys: set[tuple[str, str, str, str]] = set()

        pages = list(range(query.page_from, query.page_to + 1))
        total_pages = max(1, len(pages))
        last_request_at = 0.0

        for index, page in enumerate(pages, start=1):
            if len(jobs) >= query.max_items:
                break

            elapsed_since_last = time.time() - last_request_at if last_request_at else None
            desired_interval = self._desired_interval(query, current_rows=max(len(jobs), 20))
            if elapsed_since_last is not None and elapsed_since_last < desired_interval:
                time.sleep(desired_interval - elapsed_since_last)

            url = self._build_url(query, page)
            self._emit(progress_callback, "request", f"正在抓取第 {page} 页", math.floor((index - 1) / total_pages * 100))
            response = self.session.get(url, timeout=query.timeout_seconds)
            response.raise_for_status()
            last_request_at = time.time()

            page_jobs = self._parse_jobs(response.text, page, url)
            added = 0
            for job in page_jobs:
                key = (job.company, job.work_location, job.positions, job.apply_url)
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                jobs.append(job)
                added += 1
                if len(jobs) >= query.max_items:
                    break

            progress = math.floor(index / total_pages * 100)
            self._emit(
                progress_callback,
                "page_done",
                f"第 {page} 页完成，新增 {added} 条，累计 {len(jobs)} 条",
                progress,
            )

        self._emit(progress_callback, "done", f"抓取完成，共 {len(jobs)} 条", 100)
        return jobs[: query.max_items]

    def save(self, jobs: list[OfferStarJob], query: OfferStarQuery) -> dict[str, str]:
        query.output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        slug = _slugify(query.question or query.positions or query.company or "offerstar")
        csv_path = query.output_dir / f"{timestamp}_{slug}.csv"
        json_path = query.output_dir / f"{timestamp}_{slug}.json"

        with csv_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(asdict(jobs[0]).keys()) if jobs else list(asdict(OfferStarJob()).keys()))
            writer.writeheader()
            for item in jobs:
                writer.writerow(asdict(item))

        payload = {
            "query": asdict(query),
            "count": len(jobs),
            "jobs": [asdict(item) for item in jobs],
        }
        payload["query"]["output_dir"] = str(query.output_dir)
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"csv": str(csv_path), "json": str(json_path)}

    def _build_url(self, query: OfferStarQuery, page: int) -> str:
        params = {}
        if query.industry:
            params["industry"] = query.industry
        if query.work_location:
            params["workLocation"] = query.work_location
        if query.company:
            params["company"] = query.company
        if query.positions:
            params["positions"] = query.positions
        params["page"] = page
        return BASE_URL + "?" + urlencode(params)

    def _parse_jobs(self, html: str, page: int, source_url: str) -> list[OfferStarJob]:
        soup = BeautifulSoup(html, "html.parser")
        table = soup.find("table")
        jobs: list[OfferStarJob] = []

        if table:
            headers = [self._normalize_text(th.get_text(" ", strip=True)) for th in table.find_all("th")]
            for row in table.find_all("tr"):
                cells = row.find_all("td")
                if not cells:
                    continue
                values = [self._normalize_text(td.get_text(" ", strip=True)) for td in cells]
                job = self._row_to_job(headers, cells, values, page, source_url)
                if self._looks_valid(job):
                    jobs.append(job)
            if jobs:
                return jobs

        # Fallback for non-table layouts.
        for row in soup.find_all(["div", "li"]):
            text = self._normalize_text(row.get_text(" ", strip=True))
            if not text or "投递" not in text:
                continue
            link = row.find("a", href=True)
            if not link:
                continue
            job = OfferStarJob(
                company=text[:40],
                positions=text[:80],
                apply_url=urljoin(source_url, link["href"]), # type: ignore
                source_url=source_url,
                source_page=page,
            )
            jobs.append(job)
        return jobs

    def _row_to_job(
        self,
        headers: list[str],
        cells: list,
        values: list[str],
        page: int,
        source_url: str,
    ) -> OfferStarJob:
        mapping = {header: values[idx] if idx < len(values) else "" for idx, header in enumerate(headers)}
        links = []
        for cell in cells:
            for anchor in cell.find_all("a", href=True):
                links.append(urljoin(source_url, anchor["href"]))

        job = OfferStarJob(
            company=self._first_non_empty(mapping, ["公司", "企业", "公司名称"], values, 0),
            industry=self._first_non_empty(mapping, ["行业"], values, 1),
            work_location=self._first_non_empty(mapping, ["工作地点", "地点", "城市"], values, 2),
            positions=self._first_non_empty(mapping, ["求职岗位", "岗位", "职位"], values, 3),
            update_time=self._first_non_empty(mapping, ["更新时间", "更新"], values, 4),
            recruitment_type=self._first_non_empty(mapping, ["招聘类型", "类型"], values, 5),
            deadline=self._first_non_empty(mapping, ["截止时间", "截止"], values, 6),
            apply_url=links[-1] if links else "",
            source_url=source_url,
            source_page=page,
        )
        return job

    def _first_non_empty(self, mapping: dict[str, str], candidates: list[str], values: list[str], fallback_index: int) -> str:
        for key in candidates:
            value = mapping.get(key, "")
            if value:
                return value
        if fallback_index < len(values):
            return values[fallback_index]
        return ""

    def _looks_valid(self, job: OfferStarJob) -> bool:
        return bool(job.company or job.positions or job.apply_url)

    def _normalize_text(self, text: str) -> str:
        return " ".join(text.split())

    def _desired_interval(self, query: OfferStarQuery, current_rows: int) -> float:
        assumed_rows = max(20, min(current_rows, 30))
        return max(1.5, 10 * assumed_rows / max(query.target_rows_per_10s, 1))

    def _emit(self, callback: callable | None, stage: str, message: str, progress: int) -> None: # type: ignore
        if callback:
            callback(stage, message, progress)

    def _infer_city(self, question: str) -> str:
        cities = ["深圳", "广州", "杭州", "上海", "北京", "成都", "武汉", "南京", "苏州", "西安"]
        for city in cities:
            if city in question:
                return city
        return ""

    def _infer_company(self, question: str) -> str:
        companies = ["华为", "腾讯", "阿里", "字节", "美团", "京东", "拼多多", "小米", "快手", "百度"]
        for company in companies:
            if company in question:
                return company
        return ""

    def _infer_position(self, question: str) -> str:
        if "算法" in question:
            return "算法"
        if "数据分析" in question:
            return "数据分析"
        if "产品" in question:
            return "产品"
        if "运营" in question:
            return "运营"
        if "测试" in question:
            return "测试"
        if "前端" in question:
            return "前端"
        if "后端" in question:
            return "后端"
        if "开发" in question:
            return "开发"
        if any(token in question for token in ("计算机", "软件工程", "网络工程", "人工智能", "自动化", "电子信息")):
            return "开发"
        return ""

    def _infer_industry(self, question: str) -> str:
        industries = ["人工智能", "互联网", "金融科技", "汽车", "游戏", "电商", "新能源", "医疗", "教育"]
        for industry in industries:
            if industry in question:
                return industry
        if any(token in question for token in ("计算机", "软件工程", "网络工程", "前端", "后端", "开发", "测试")):
            return "互联网"
        if any(token in question for token in ("算法", "机器学习", "深度学习", "大模型", "人工智能")):
            return "人工智能"
        return ""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Conservative OfferStar crawler for JobOracle")
    parser.add_argument("--question", default="", help="Natural language question used to infer filters")
    parser.add_argument("--industry", default="", help="Industry filter")
    parser.add_argument("--work-location", default="", help="Work location filter")
    parser.add_argument("--company", default="", help="Company filter")
    parser.add_argument("--positions", default="", help="Position filter")
    parser.add_argument("--from-page", type=int, default=1, help="Start page")
    parser.add_argument("--to-page", type=int, default=3, help="End page")
    parser.add_argument("--max-items", type=int, default=20, help="Maximum number of rows to keep")
    parser.add_argument("--timeout", type=int, default=20, help="Request timeout in seconds")
    parser.add_argument("--target-rows-per-10s", type=int, default=20, help="Throttle target, lower means slower")
    parser.add_argument("--output-dir", default="JobOracle/jobs_dataset", help="Directory to store CSV/JSON snapshots")
    return parser


def run_cli(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    crawler = OfferStarCrawler()
    inferred = crawler.infer_query(args.question) if args.question else OfferStarQuery()
    query = OfferStarQuery(
        question=args.question or inferred.question,
        industry=args.industry or inferred.industry,
        work_location=args.work_location or inferred.work_location,
        company=args.company or inferred.company,
        positions=args.positions or inferred.positions,
        page_from=args.from_page,
        page_to=max(args.to_page, args.from_page),
        max_items=args.max_items,
        timeout_seconds=args.timeout,
        target_rows_per_10s=args.target_rows_per_10s,
        output_dir=Path(args.output_dir),
    )

    def progress(stage: str, message: str, progress_value: int) -> None:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {message} ({progress_value}%)")

    jobs = crawler.crawl(query, progress_callback=progress)
    paths = crawler.save(jobs, query)
    print(f"\n抓取完成，共保存 {len(jobs)} 条")
    print(f"CSV: {paths['csv']}")
    print(f"JSON: {paths['json']}")
    return 0


def _slugify(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"_", "-"} or "\u4e00" <= ch <= "\u9fff" else "_" for ch in value)
    cleaned = "_".join(part for part in cleaned.split("_") if part)
    return cleaned[:50] or "offerstar"


if __name__ == "__main__":
    raise SystemExit(run_cli())
