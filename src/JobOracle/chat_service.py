from __future__ import annotations

from dataclasses import dataclass, field

from .config import get_config
from .conversation import ConversationDecision, ConversationPlanner
from .memory import MemoryManager, RuntimeContext
from .models import EmploymentRequest, EmploymentReport, EmploymentSearchResult
from .prompts import CHAT_SYSTEM_PROMPT, build_chat_prompt
from .service import EmploymentAdvisor


@dataclass(slots=True)
class ChatResponse:
    session_id: str
    mode: str
    message: str
    follow_up_question: str = ""
    report_markdown: str = ""
    report_output_path: str | None = None
    suggested_actions: list[str] = field(default_factory=list)
    runtime_context: RuntimeContext | None = None
    used_llm: bool = False
    used_search: bool = False
    search_results: list[EmploymentSearchResult] = field(default_factory=list)


class ChatService:
    def __init__(self) -> None:
        self.config = get_config()
        self.advisor = EmploymentAdvisor()
        self.memory = MemoryManager(self.config.memory_db_path, self.advisor.llm_client)
        self.planner = ConversationPlanner()

    def start_session(self, title: str = "新会话") -> str:
        return self.memory.start_session(title)

    def handle_message(
        self,
        content: str,
        session_id: str | None = None,
        *,
        mode: str = "auto",
        save_report: bool = True,
        use_offerstar: bool = False,
        offerstar_page_from: int = 1,
        offerstar_page_to: int = 1,
        offerstar_max_items: int = 20,
    ) -> ChatResponse:
        resolved_session_id = session_id or self.start_session()
        context = self.memory.ingest_user_message(resolved_session_id, content)
        decision = self.planner.decide(context)
        if decision.mode == "report":
            report = self._generate_report(
                content=content,
                context=context,
                mode=mode,
                save_report=save_report,
                use_offerstar=use_offerstar,
                offerstar_page_from=offerstar_page_from,
                offerstar_page_to=offerstar_page_to,
                offerstar_max_items=offerstar_max_items,
            )
            assistant_message = "我已经根据当前会话内容生成了一份完整报告。"
            self.memory.ingest_assistant_message(resolved_session_id, assistant_message)
            self.memory.update_last_report_brief(resolved_session_id, self._build_report_brief(report))
            return ChatResponse(
                session_id=resolved_session_id,
                mode="report",
                message=assistant_message,
                report_markdown=report.markdown,
                report_output_path=report.output_path,
                suggested_actions=["导出 Markdown", "继续分析"],
                runtime_context=self.memory.build_runtime_context(resolved_session_id),
                used_llm=report.used_llm,
                used_search=report.used_search,
                search_results=report.search_results,
            )

        chat_search_results = self._search_for_chat(context, decision, mode=mode)
        assistant_message, used_llm = self._generate_chat_reply(
            context=context,
            decision=decision,
            search_results=chat_search_results,
        )
        updated_context = self.memory.ingest_assistant_message(resolved_session_id, assistant_message)
        return ChatResponse(
            session_id=resolved_session_id,
            mode="chat",
            message=assistant_message,
            follow_up_question=decision.follow_up_question,
            suggested_actions=decision.suggested_actions,
            runtime_context=updated_context,
            used_llm=used_llm,
            used_search=bool(chat_search_results),
            search_results=chat_search_results,
        )

    def _generate_report(
        self,
        *,
        content: str,
        context: RuntimeContext,
        mode: str,
        save_report: bool,
        use_offerstar: bool,
        offerstar_page_from: int,
        offerstar_page_to: int,
        offerstar_max_items: int,
    ) -> EmploymentReport:
        report_query = self._resolve_report_query(content, context)
        request = EmploymentRequest(
            query=report_query,
            mode=mode,
            profile=context.profile,
            save=save_report,
            use_offerstar=use_offerstar,
            offerstar_page_from=offerstar_page_from,
            offerstar_page_to=offerstar_page_to,
            offerstar_max_items=offerstar_max_items,
            session_id=context.session_id,
            conversation_summary=context.conversation_summary,
            recent_messages=[{"role": item.role, "content": item.content} for item in context.recent_messages],
            active_goals=context.active_goals,
            open_questions=context.open_questions,
        )
        return self.advisor.analyze_with_context(request, context)

    def _build_report_brief(self, report: EmploymentReport) -> str:
        lines = [line.strip() for line in report.markdown.splitlines() if line.strip()]
        return " ".join(lines[:3])[:240]

    def _compose_chat_message(self, decision: ConversationDecision) -> str:
        if decision.follow_up_question:
            return f"{decision.reply}\n\n{decision.follow_up_question}"
        return decision.reply

    def _generate_chat_reply(
        self,
        *,
        context: RuntimeContext,
        decision: ConversationDecision,
        search_results: list[EmploymentSearchResult],
    ) -> tuple[str, bool]:
        request = EmploymentRequest(
            query=context.latest_user_message,
            mode="guidance",
            profile=context.profile,
            save=False,
            session_id=context.session_id,
            conversation_summary=context.conversation_summary,
            recent_messages=[{"role": item.role, "content": item.content} for item in context.recent_messages],
            active_goals=context.active_goals,
            open_questions=context.open_questions,
        )
        try:
            reply = self.advisor.llm_client.generate_text(
                CHAT_SYSTEM_PROMPT,
                build_chat_prompt(
                    request,
                    search_results,
                    response_style=decision.response_style,
                    follow_up_question=decision.follow_up_question,
                    last_report_brief=context.last_report_brief,
                ),
                temperature=0.55,
            )
            return reply, True
        except Exception:
            return self._compose_chat_message(decision), False

    def _search_for_chat(
        self,
        context: RuntimeContext,
        decision: ConversationDecision,
        *,
        mode: str,
    ) -> list[EmploymentSearchResult]:
        if not decision.should_search:
            return []
        request = EmploymentRequest(
            query=self._build_contextual_query(context.latest_user_message, context),
            mode=mode,
            profile=context.profile,
            save=False,
            session_id=context.session_id,
            conversation_summary=context.conversation_summary,
            recent_messages=[{"role": item.role, "content": item.content} for item in context.recent_messages],
            active_goals=context.active_goals,
            open_questions=context.open_questions,
        )
        try:
            results = self.advisor.search_agency.search(request, mode=mode)
        except Exception:
            return []
        return results[:4]

    def _resolve_report_query(self, content: str, context: RuntimeContext) -> str:
        trigger_like = {"生成报告", "输出报告", "总结成报告", "完整报告", "帮我生成报告"}
        if not any(token in content for token in trigger_like):
            return self._build_contextual_query(content, context)
        user_messages = [message.content.strip() for message in context.recent_messages if message.role == "user"]
        for candidate in reversed(user_messages[:-1] or user_messages):
            if candidate and not any(token in candidate for token in trigger_like):
                return self._build_contextual_query(candidate, context)
        if context.active_topic:
            return context.active_topic
        return "当前会话求职分析"

    def _build_contextual_query(self, base_query: str, context: RuntimeContext) -> str:
        normalized = " ".join(base_query.strip().split())
        if not normalized:
            return "当前会话求职分析"

        profile = context.profile or {}
        education = str(profile.get("education") or "").strip()
        major = str(profile.get("major") or "").strip()
        cities = profile.get("target_cities") if isinstance(profile.get("target_cities"), list) else []
        roles = profile.get("target_roles") if isinstance(profile.get("target_roles"), list) else []
        skills = profile.get("skills") if isinstance(profile.get("skills"), list) else []

        short_followup_markers = ("那", "这个", "这个方向", "这个岗位", "这里", "呢", "怎么样", "如何")
        needs_enrichment = len(normalized) <= 12 or any(marker in normalized for marker in short_followup_markers)
        if not needs_enrichment:
            return normalized

        identity = " ".join(part for part in [education, major] if part).strip()
        city_part = "、".join(str(city) for city in cities[:2]).strip()
        role_part = "、".join(str(role) for role in roles[:2]).strip()
        skill_part = "、".join(str(skill) for skill in skills[:3]).strip()

        if city_part and role_part:
            topic = f"{city_part}{role_part}"
        elif role_part:
            topic = role_part
        elif city_part:
            topic = city_part
        else:
            topic = context.active_topic or "求职方向"

        if normalized in {"那广州呢？", "那广州呢", "那深圳呢？", "那深圳呢", "怎么样", "如何", "那呢？", "那呢"}:
            prefix = f"{identity}背景下的" if identity else ""
            return f"{prefix}{topic}机会分析"

        details = [f"{identity}背景" if identity else "", topic]
        if skill_part:
            details.append(f"技能包括{skill_part}")
        detail_text = "，".join(part for part in details if part)
        return f"{detail_text}，问题：{normalized}".strip("，")
