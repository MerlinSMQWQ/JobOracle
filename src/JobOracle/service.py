from __future__ import annotations

from collections.abc import Callable

from .agents import AdvisorAgent, AnalystAgent, ResearcherAgent
from .config import get_config
from .llm_client import EmploymentLLMClient
from .models import AgentNote, EmploymentReport, EmploymentRequest
from .memory.models import RuntimeContext
from .report_writer import save_markdown
from .search import EmploymentSearchAgency


GUIDANCE_HINTS = ("我", "适合", "怎么找", "怎么准备", "简历", "转行", "面试", "求职")
MARKET_HINTS = ("行情", "趋势", "前景", "需求", "薪资", "岗位", "城市", "行业")


class EmploymentAdvisor:
    def __init__(self) -> None:
        self.config = get_config()
        self.llm_client = EmploymentLLMClient(self.config)
        self.search_agency = EmploymentSearchAgency(self.config)
        self.researcher = ResearcherAgent(self.llm_client)
        self.analyst = AnalystAgent(self.llm_client)
        self.advisor = AdvisorAgent(self.llm_client)

    def analyze(
        self,
        request: EmploymentRequest,
        progress_callback: Callable[[str, str, int, dict[str, object] | None], None] | None = None,
    ) -> EmploymentReport:
        self._emit_progress(progress_callback, "init", "正在初始化就业分析流程", 5)
        mode = self._resolve_mode(request)
        self._emit_progress(
            progress_callback,
            "mode",
            f"已确定分析模式: {mode}",
            10,
            {"mode": mode},
        )
        search_plan = self.search_agency.build_search_plan(request, mode)
        self._emit_progress(
            progress_callback,
            "search_plan",
            f"已生成 {len(search_plan.queries)} 条检索查询",
            20,
            {"queries": search_plan.queries, "tool_name": search_plan.tool_name},
        )
        search_results = self.search_agency.search(request, mode, progress_callback=progress_callback)
        self._emit_progress(
            progress_callback,
            "search_done",
            f"信息检索完成，获得 {len(search_results)} 条证据",
            40,
            {"results_count": len(search_results)},
        )
        researcher_note, researcher_used_llm = self.researcher.run(request, mode, search_results)
        self._emit_progress(
            progress_callback,
            "researcher_done",
            "Researcher 已完成检索整理",
            58,
            {"used_llm": researcher_used_llm},
        )
        analyst_note, analyst_used_llm = self.analyst.run(request, mode, researcher_note, search_results)
        self._emit_progress(
            progress_callback,
            "analyst_done",
            "Analyst 已完成结构化分析",
            76,
            {"used_llm": analyst_used_llm},
        )
        markdown, advisor_used_llm = self.advisor.run(request, mode, researcher_note, analyst_note, search_results)
        self._emit_progress(
            progress_callback,
            "advisor_done",
            "Advisor 已完成最终报告生成",
            92,
            {"used_llm": advisor_used_llm},
        )

        title = self._build_title(request, mode)
        output_path = save_markdown(self.config.report_dir, request.query, markdown) if request.save else None
        agent_notes = [
            AgentNote(role="researcher", content=researcher_note),
            AgentNote(role="analyst", content=analyst_note),
        ]
        report = EmploymentReport(
            title=title,
            mode=mode,
            markdown=markdown,
            used_llm=researcher_used_llm or analyst_used_llm or advisor_used_llm,
            used_search=bool(search_results),
            search_results=search_results,
            agent_notes=agent_notes,
            output_path=output_path,
        )
        self._emit_progress(
            progress_callback,
            "done",
            "分析完成",
            100,
            {"output_path": output_path, "title": title},
        )
        return report

    def analyze_with_context(
        self,
        request: EmploymentRequest,
        runtime_context: RuntimeContext,
        progress_callback: Callable[[str, str, int, dict[str, object] | None], None] | None = None,
    ) -> EmploymentReport:
        enriched_request = EmploymentRequest(
            query=request.query,
            mode=request.mode,
            profile=runtime_context.profile or request.profile,
            save=request.save,
            use_offerstar=request.use_offerstar,
            offerstar_page_from=request.offerstar_page_from,
            offerstar_page_to=request.offerstar_page_to,
            offerstar_max_items=request.offerstar_max_items,
            session_id=runtime_context.session_id,
            conversation_summary=runtime_context.conversation_summary,
            recent_messages=[
                {"role": message.role, "content": message.content}
                for message in runtime_context.recent_messages
            ],
            active_goals=runtime_context.active_goals,
            open_questions=runtime_context.open_questions,
        )
        return self.analyze(enriched_request, progress_callback=progress_callback)

    def _resolve_mode(self, request: EmploymentRequest) -> str:
        if request.mode in {"market", "guidance"}:
            return request.mode
        query = request.query
        if any(token in query for token in GUIDANCE_HINTS):
            return "guidance"
        if any(token in query for token in MARKET_HINTS):
            return "market"
        return "market"

    def _build_title(self, request: EmploymentRequest, mode: str) -> str:
        suffix = "就业指导报告" if mode == "guidance" else "就业行情分析报告"
        return f"{request.query} - {suffix}"

    def _emit_progress(
        self,
        callback: Callable[[str, str, int, dict[str, object] | None], None] | None,
        stage: str,
        message: str,
        progress: int,
        meta: dict[str, object] | None = None,
    ) -> None:
        if callback is not None:
            callback(stage, message, progress, meta)
