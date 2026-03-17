from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import requests

from .config import EmploymentConfig
from .models import EmploymentRequest, EmploymentSearchResult
from .offerstar_crawler import OfferStarCrawler, OfferStarQuery
from .profile import summarize_profile


@dataclass(slots=True)
class SearchPlan:
    queries: list[str]
    tool_name: str


class EmploymentSearchAgency:
    """Lightweight search layer inspired by BettaFish QueryEngine tools."""

    TAVILY_URL = "https://api.tavily.com/search"

    def __init__(self, config: EmploymentConfig):
        self.config = config
        self.offerstar_crawler = OfferStarCrawler()

    def build_search_plan(self, request: EmploymentRequest, mode: str) -> SearchPlan:
        base = request.query.strip()
        education = self._infer_education_level(request)
        role_focus = self._infer_role_focus(base)
        role_tracks = self._infer_role_tracks(base)
        target_roles = request.profile.get("target_roles") if isinstance(request.profile.get("target_roles"), list) else []
        target_cities = request.profile.get("target_cities") if isinstance(request.profile.get("target_cities"), list) else []
        preferred_industries = (
            request.profile.get("preferred_industries")
            if isinstance(request.profile.get("preferred_industries"), list)
            else []
        )
        queries = [base]
        lower = base.lower()

        if mode == "market":
            queries.extend(
                [
                    f"{base} 招聘 趋势",
                    f"{base} 技能 要求",
                    f"{base} 薪资 城市 公司",
                    f"{base} 中厂 小厂 招聘 机会",
                    f"{base} 民营 公司 创业公司 岗位",
                ]
            )
        else:
            queries.extend(
                [
                    f"{base} 求职 建议",
                    f"{base} 技能 要求 简历 面试",
                    f"{base} 岗位 城市 公司 机会",
                    f"{base} 中厂 小厂 更容易进入的岗位",
                    f"{base} 非大厂 岗位 成长 路径",
                ]
            )

        if education != "未说明":
            queries.extend(
                [
                    f"{education} {role_focus} 求职 门槛",
                    f"{education} {role_focus} 中小厂 机会",
                ]
            )

        for track in role_tracks[:3]:
            queries.extend(
                [
                    f"{track} 招聘 要求",
                    f"{track} 中厂 小厂 机会",
                ]
            )

        skills = request.profile.get("skills")
        if isinstance(skills, list) and skills:
            joined = " ".join(str(item) for item in skills[:4])
            queries.append(f"{base} {joined} 岗位 匹配")
        school = request.profile.get("school")
        major = request.profile.get("major")
        internship = request.profile.get("internship")
        if school and major:
            queries.append(f"{school} {major} {role_focus} 求职 方向")
        elif major:
            queries.append(f"{major} {role_focus} 求职 方向")
        if target_roles:
            for role in target_roles[:2]:
                if target_cities:
                    queries.append(f"{' '.join(target_cities[:2])} {role} 校招 招聘")
                else:
                    queries.append(f"{role} 校招 招聘")
        if preferred_industries:
            queries.append(f"{' '.join(preferred_industries[:2])} {role_focus} 招聘")
        if internship:
            internship_text = internship if isinstance(internship, str) else " ".join(str(item) for item in internship[:2])
            queries.append(f"{base} {internship_text} 经验 匹配")

        if "校招" in lower or "应届" in base:
            queries.append(f"{base} 校招 应届 岗位 要求")

        deduped = []
        for item in queries:
            if item not in deduped:
                deduped.append(item)
        return SearchPlan(queries=deduped[:6], tool_name="tavily_search")

    def search(
        self,
        request: EmploymentRequest,
        mode: str,
        progress_callback: Callable[[str, str, int, dict[str, object] | None], None] | None = None,
    ) -> list[EmploymentSearchResult]:
        plan = self.build_search_plan(request, mode)
        merged_results: list[EmploymentSearchResult] = []

        if request.use_offerstar:
            try:
                self._emit_progress(
                    progress_callback,
                    "offerstar_start",
                    "正在调用 OfferStar 公开岗位汇总页",
                    28,
                    None,
                )
                offerstar_results = self._search_with_offerstar(request)
                merged_results.extend(offerstar_results)
                self._emit_progress(
                    progress_callback,
                    "offerstar_done",
                    f"OfferStar 抓取完成，获得 {len(offerstar_results)} 条岗位记录",
                    35,
                    {"results_count": len(offerstar_results)},
                )
            except Exception:
                self._emit_progress(
                    progress_callback,
                    "offerstar_error",
                    "OfferStar 抓取失败，已跳过并继续其他检索",
                    35,
                    None,
                )

        if self.config.search_enabled and self.config.search_provider == "tavily":
            try:
                results = self._search_with_tavily(plan)
                if results:
                    merged_results.extend(results)
            except Exception:
                pass

        merged_results = self._dedupe_results(merged_results)
        if merged_results:
            return self._limit_results_with_source_balance(merged_results)
        return self._fallback_results(plan.queries, request, mode)

    def _search_with_tavily(self, plan: SearchPlan) -> list[EmploymentSearchResult]:
        merged: list[EmploymentSearchResult] = []
        seen: set[str] = set()

        for query in plan.queries:
            payload = {
                "api_key": self.config.search_api_key,
                "query": query,
                "topic": "general",
                "search_depth": "basic",
                "max_results": self.config.max_search_results,
                "include_answer": False,
            }
            response = requests.post(
                self.TAVILY_URL,
                json=payload,
                timeout=self.config.search_timeout_seconds,
            )
            response.raise_for_status()
            data = response.json()
            for item in data.get("results", []):
                url = item.get("url") or ""
                if not url or url in seen:
                    continue
                seen.add(url)
                merged.append(
                    EmploymentSearchResult(
                        title=item.get("title") or query,
                        url=url,
                        snippet=item.get("content") or "",
                        query=query,
                        source="tavily",
                        published_date=item.get("published_date"),
                    )
                )
        return merged[: self.config.max_search_results]

    def _fallback_results(
        self,
        queries: list[str],
        request: EmploymentRequest,
        mode: str,
    ) -> list[EmploymentSearchResult]:
        seeds: list[EmploymentSearchResult] = []
        question = request.query
        synthetic_snippets = self._build_synthetic_snippets(question, mode, request.profile)
        for idx, snippet in enumerate(synthetic_snippets, start=1):
            query = queries[min(idx - 1, len(queries) - 1)]
            seeds.append(
                EmploymentSearchResult(
                    title=f"本地推断证据 {idx}",
                    url=f"local://employment-evidence/{idx}",
                    snippet=snippet,
                    query=query,
                    source="local_fallback",
                    published_date=None,
                )
            )
        return seeds

    def _build_synthetic_snippets(self, question: str, mode: str, profile: dict[str, object]) -> list[str]:
        education = self._infer_education_level_from_inputs(question, profile)
        role_tracks = self._infer_role_tracks(question)
        snippets = [
            "就业分析至少应同时观察岗位需求、技能门槛、城市机会和企业稳定性，不能只看社交平台热度。",
            "真实岗位判断更适合从持续招聘、JD 高频技能、业务场景和对经验的要求四个维度切入。",
            "如果用户问题涉及具体城市，应重点比较城市中的行业密度、公司类型分布和竞争强度。",
            "大厂岗位通常曝光高但门槛更高，真正更适合大多数人的机会往往分散在中厂、小厂、区域龙头和业务稳定的民营公司。",
        ]
        if "算法" in question or "AI" in question or "ai" in question.lower():
            snippets.append("AI/算法方向常见要求包括 Python、机器学习基础、模型调参、工程落地和业务场景理解；中小厂更可能要求一人覆盖建模、数据处理和上线协作。")
        if "数据分析" in question:
            snippets.append("数据分析岗位通常看重 SQL、Python、统计学基础、指标体系、业务分析和可视化表达能力；中厂和小厂更偏好能直接支持业务、报表和增长分析的人。")
        if "产品" in question:
            snippets.append("产品岗位往往强调行业理解、需求拆解、跨团队协作、数据意识和推动项目落地的能力；非大厂环境里通常更强调执行力和多面手能力。")
        if education == "专科":
            snippets.append("专科学历求职时，更现实的路径通常是优先选择业务明确的中小厂、区域公司、服务型团队或对学历要求没那么硬的岗位。")
        elif education == "本科":
            snippets.append("本科学历通常有更广的岗位覆盖面，但实际能否拿到机会，往往取决于项目经历、实习经历和技能证明，而不是学历标签本身。")
        elif education in {"硕士", "博士"}:
            snippets.append("研究生学历在算法、数据、研究型岗位上更容易获得面试机会，但企业仍会看重工程能力、项目落地和业务理解。")
        if role_tracks:
            snippets.append(f"当前问题可以进一步拆成这些更具体的岗位切口：{', '.join(role_tracks)}。")
        if mode == "guidance":
            snippets.append("求职指导不只是判断行情，更要判断候选人的现有能力能否被岗位快速验证，并且优先选择成功率更高的公司层级。")
        if profile:
            snippets.append(f"当前已提供的用户画像字段包括：{', '.join(sorted(profile.keys()))}，这些信息可以帮助缩小建议范围。")
            snippets.append(f"画像摘要：{summarize_profile(profile)}。")
        return snippets[: self.config.max_search_results]

    def _search_with_offerstar(self, request: EmploymentRequest) -> list[EmploymentSearchResult]:
        inferred = self.offerstar_crawler.infer_query(request.query)
        query = OfferStarQuery(
            question=request.query,
            industry=inferred.industry,
            work_location=inferred.work_location,
            company=inferred.company,
            positions=inferred.positions,
            page_from=max(1, request.offerstar_page_from),
            page_to=max(request.offerstar_page_from, request.offerstar_page_to),
            max_items=max(1, request.offerstar_max_items),
            target_rows_per_10s=20,
        )
        jobs = self.offerstar_crawler.crawl(query)
        if jobs:
            self.offerstar_crawler.save(jobs, query)
        results: list[EmploymentSearchResult] = []
        for job in jobs:
            snippet_parts = [
                part
                for part in [
                    f"行业: {job.industry}" if job.industry else "",
                    f"地点: {job.work_location}" if job.work_location else "",
                    f"类型: {job.recruitment_type}" if job.recruitment_type else "",
                    f"截止: {job.deadline}" if job.deadline else "",
                ]
                if part
            ]
            results.append(
                EmploymentSearchResult(
                    title=f"{job.company} - {job.positions}".strip(" -"),
                    url=job.apply_url or job.source_url,
                    snippet=" | ".join(snippet_parts) or "OfferStar 公开岗位汇总记录",
                    query=request.query,
                    source="offerstar",
                    published_date=job.update_time or None,
                )
            )
        return results

    def _dedupe_results(self, results: list[EmploymentSearchResult]) -> list[EmploymentSearchResult]:
        deduped: list[EmploymentSearchResult] = []
        seen: set[tuple[str, str]] = set()
        for item in results:
            key = (item.title, item.url)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)
        return deduped

    def _limit_results_with_source_balance(
        self,
        results: list[EmploymentSearchResult],
    ) -> list[EmploymentSearchResult]:
        limit = max(1, self.config.max_search_results)
        if len(results) <= limit:
            return results

        grouped: dict[str, list[EmploymentSearchResult]] = {}
        order: list[str] = []
        for item in results:
            source = item.source or "unknown"
            if source not in grouped:
                grouped[source] = []
                order.append(source)
            grouped[source].append(item)

        selected: list[EmploymentSearchResult] = []
        seen: set[tuple[str, str]] = set()

        # First pass: keep at least one result from each source if possible.
        for source in order:
            if len(selected) >= limit:
                break
            item = grouped[source][0]
            key = (item.title, item.url)
            if key not in seen:
                seen.add(key)
                selected.append(item)

        # Second pass: fill the remaining capacity in original grouped order.
        for source in order:
            for item in grouped[source][1:]:
                if len(selected) >= limit:
                    break
                key = (item.title, item.url)
                if key in seen:
                    continue
                seen.add(key)
                selected.append(item)
            if len(selected) >= limit:
                break

        return selected[:limit]

    def _emit_progress(
        self,
        callback: Callable[[str, str, int, dict[str, object] | None], None] | None,
        stage: str,
        message: str,
        progress: int,
        meta: dict[str, object] | None,
    ) -> None:
        if callback is not None:
            callback(stage, message, progress, meta)

    def _infer_education_level(self, request: EmploymentRequest) -> str:
        return self._infer_education_level_from_inputs(request.query, request.profile)

    def _infer_education_level_from_inputs(self, question: str, profile: dict[str, object]) -> str:
        joined = f"{question} {profile}".lower()
        if "博士" in joined:
            return "博士"
        if "硕士" in joined or "研究生" in joined:
            return "硕士"
        if "本科" in joined:
            return "本科"
        if "专科" in joined or "大专" in joined:
            return "专科"
        if "中专" in joined:
            return "中专"
        return "未说明"

    def _infer_role_focus(self, question: str) -> str:
        if "算法" in question or "大模型" in question or "ai" in question.lower():
            return "算法岗"
        if "数据分析" in question:
            return "数据分析岗"
        if "产品" in question:
            return "产品岗"
        if "运营" in question:
            return "运营岗"
        if "开发" in question or "后端" in question or "前端" in question:
            return "开发岗"
        return "目标岗位"

    def _infer_role_tracks(self, question: str) -> list[str]:
        tracks: list[str] = []
        lower = question.lower()
        if "数据分析" in question:
            tracks.extend(["业务数据分析", "BI数据分析", "增长分析", "商业分析"])
        if "算法" in question or "大模型" in question or "ai" in lower:
            tracks.extend(["算法工程师", "机器学习工程师", "AI应用工程师", "数据挖掘工程师"])
        if "产品" in question:
            tracks.extend(["B端产品经理", "数据产品经理", "增长产品经理", "行业产品经理"])
        if "运营" in question:
            tracks.extend(["内容运营", "用户运营", "增长运营", "活动运营"])
        if "后端" in question or "前端" in question or "开发" in question:
            tracks.extend(["后端开发", "前端开发", "全栈开发", "测试开发"])
        if not tracks:
            tracks.extend(["目标岗位", "相关执行岗", "相关支持岗"])

        deduped: list[str] = []
        for item in tracks:
            if item not in deduped:
                deduped.append(item)
        return deduped
