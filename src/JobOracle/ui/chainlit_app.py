from __future__ import annotations

import asyncio
from pathlib import Path
import sys
import threading

project_src_dir = Path(__file__).resolve().parents[2]
if str(project_src_dir) not in sys.path:
    sys.path.insert(0, str(project_src_dir))

if __package__ in {None, ""}:
    from JobOracle.chat_service import ChatService
else:
    try:
        from ..chat_service import ChatService
    except ImportError:
        from JobOracle.chat_service import ChatService

try:
    import chainlit as cl
except Exception:  # pragma: no cover - optional dependency during local development
    cl = None

chat_service = ChatService()


def _runtime_overview(response) -> list[str]:
    context = response.runtime_context
    if context is None:
        return []
    profile_lines = []
    ordered_keys = [
        ("education", "学历"),
        ("school", "学校"),
        ("major", "专业"),
        ("target_cities", "目标城市"),
        ("target_roles", "目标岗位"),
        ("skills", "技能"),
        ("internship", "实习经历"),
    ]
    for key, label in ordered_keys:
        value = context.profile.get(key)
        if isinstance(value, list):
            rendered = "、".join(str(item) for item in value) if value else "未补充"
        else:
            rendered = str(value) if value else "未补充"
        profile_lines.append(f"- {label}: {rendered}")

    task_lines = [
        f"- 当前主题: {context.active_topic or '未识别'}",
        f"- 当前阶段: {context.decision_stage or '初步探索'}",
    ]
    if context.active_goals:
        task_lines.extend(f"- {goal}" for goal in context.active_goals[-3:])
    else:
        task_lines.append("- 暂无明确目标")

    open_questions = "、".join(context.open_questions) or "无"
    summary = context.conversation_summary or "当前还没有形成稳定摘要。"
    return [
        f"会话 ID: `{response.session_id}`\n\n"
        f"## 用户画像\n"
        f"{chr(10).join(profile_lines)}",
        "## 当前任务\n" + "\n".join(task_lines),
        f"## 待补充信息\n- {open_questions}\n\n## 会话摘要\n{summary}",
    ]


def _build_side_elements(response) -> list["cl.Text"]:
    overviews = _runtime_overview(response)
    if not overviews:
        return []
    names = ["profile_state", "task_state", "summary_state"]
    return [
        cl.Text(name=name, content=content, display="side")
        for name, content in zip(names, overviews, strict=False)
    ]


def _response_meta(response) -> str:
    mode = "LLM" if response.used_llm else "fallback"
    search = "已启用" if response.used_search else "未启用"
    return f"- 当前回复方式: {mode}\n- 聊天检索: {search}"


def _normalize_label(label: str) -> str:
    return label.strip().lower().replace(" ", "_")


def _action_guidance(label: str) -> str:
    if "比较城市" in label:
        return (
            "你可以继续补充你最关心的城市差异，比如：\n\n"
            "- 哪个城市更容易拿到面试\n"
            "- 哪个城市更适合先投中厂\n"
            "- 哪个城市对你当前背景更友好"
        )
    if "继续分析" in label:
        return (
            "你可以继续告诉我你的背景、目标岗位、目标城市，或者直接追问你最关心的问题。\n\n"
            "例如：\n"
            "- 我更适合先投中厂还是小厂？\n"
            "- 我现在应该先补项目还是先投简历？"
        )
    return "你可以继续补充你的背景信息，或者直接追问下一步问题。"


if cl is not None:
    async_handle_message = cl.make_async(chat_service.handle_message)
    async_prepare_message = cl.make_async(chat_service.prepare_message)
    async_finalize_chat_reply = cl.make_async(chat_service.finalize_chat_reply)

    def _base_actions(suggested_actions: list[str] | None = None, include_export: bool = False) -> list["cl.Action"]:
        actions = []
        labels = suggested_actions or ["继续分析", "生成报告"]
        for label in labels:
            normalized = _normalize_label(label)
            if "报告" in label:
                actions.append(cl.Action(name="generate_report", payload={"action": normalized}, label=label))
                continue
            if "继续" in label or "比较" in label:
                actions.append(cl.Action(name="continue_analysis", payload={"action": normalized, "label": label}, label=label))
        if include_export:
            actions.append(cl.Action(name="export_markdown", payload={"action": "export"}, label="导出 Markdown"))
        actions.append(cl.Action(name="reset_session", payload={"action": "reset"}, label="重置会话"))
        return actions

    def _store_report_state(response) -> None:
        cl.user_session.set("last_report_markdown", response.report_markdown)
        cl.user_session.set("last_report_output_path", response.report_output_path)

    async def _send_response(response) -> None:
        await _update_sidebar(response)
        if response.mode == "report" and response.report_markdown:
            _store_report_state(response)
            await cl.Message(
                content=response.message,
                actions=_base_actions(response.suggested_actions, include_export=True),
            ).send()
            await cl.Message(content=response.report_markdown).send()
            return
        content = response.message
        if response.follow_up_question:
            content += f"\n\n{response.follow_up_question}"
        await cl.Message(content=content, actions=_base_actions(response.suggested_actions)).send()

    async def _update_sidebar(response) -> None:
        elements = _build_side_elements(response)
        elements.append(cl.Text(name="response_meta", content=_response_meta(response), display="side"))
        await cl.ElementSidebar.set_title("JobOracle 状态")
        await cl.ElementSidebar.set_elements(elements, key=f"sidebar-{response.session_id}")

    async def _stream_sync_generator(generator_factory, *args):
        queue: asyncio.Queue[tuple[str, object]] = asyncio.Queue()
        loop = asyncio.get_running_loop()

        def worker() -> None:
            try:
                generator = generator_factory(*args)
                try:
                    while True:
                        token = next(generator)
                        asyncio.run_coroutine_threadsafe(queue.put(("token", token)), loop)
                except StopIteration as stop:
                    asyncio.run_coroutine_threadsafe(queue.put(("done", stop.value)), loop)
            except Exception as exc:  # pragma: no cover - defensive streaming guard
                asyncio.run_coroutine_threadsafe(queue.put(("error", exc)), loop)

        threading.Thread(target=worker, daemon=True).start()

        while True:
            event, payload = await queue.get()
            if event == "token":
                yield ("token", payload)
                continue
            if event == "done":
                yield ("done", payload)
                return
            yield ("error", payload)
            return

    @cl.on_chat_start
    async def on_chat_start() -> None:
        session_id = cl.user_session.get("session_id")
        if not session_id:
            session_id = chat_service.start_session()
            cl.user_session.set("session_id", session_id)
            cl.user_session.set("last_report_markdown", "")
            cl.user_session.set("last_report_output_path", None)
        await cl.Message(
            content=(
                "# JobOracle\n\n"
                "多轮求职分析与就业决策助手。\n\n"
                "你可以先告诉我你的背景、目标岗位或目标城市；当你准备好时，再让我生成完整报告。\n\n"
                "示例：`我是统计学本科，会 SQL 和 Python，想在深圳找数据分析工作。`"
            ),
            actions=_base_actions(["继续分析", "生成报告"]),
        ).send()

    @cl.on_message
    async def on_message(message: "cl.Message") -> None:
        session_id = cl.user_session.get("session_id")
        prepared = await async_prepare_message(message.content, session_id=session_id)
        if isinstance(prepared, tuple):
            resolved_session_id, context, decision, search_results = prepared
            status_parts = ["正在整理记忆"]
            if search_results:
                status_parts.append("已完成轻量检索")
            status_parts.append("正在流式生成回复")
            await cl.Message(content="，".join(status_parts) + "…").send()

            stream_msg = cl.Message(content="", actions=_base_actions(decision.suggested_actions))

            used_llm = False
            final_text = ""
            async for event, payload in _stream_sync_generator(
                chat_service.stream_chat_reply,
                context,
                decision,
                search_results,
            ):
                if event == "token":
                    used_llm = True
                    await stream_msg.stream_token(str(payload))
                    continue
                if event == "done":
                    if isinstance(payload, tuple):
                        used_llm = bool(payload[0])
                        final_text = str(payload[1])
                    break
                used_llm = False
                final_text = chat_service._compose_chat_message(decision)
                break

            if not final_text:
                final_text = stream_msg.content or chat_service._compose_chat_message(decision)

            if not used_llm:
                stream_msg.content = final_text
                await stream_msg.send()
            else:
                stream_msg.content = final_text
                await stream_msg.send()

            response = await async_finalize_chat_reply(
                resolved_session_id,
                final_text,
                decision,
                used_llm=used_llm,
                search_results=search_results,
            )
            await _update_sidebar(response)
            return

        response = prepared
        await cl.Message(content="正在根据当前会话内容生成报告，请稍候...").send()
        await _send_response(response)

    @cl.action_callback("generate_report")
    async def on_generate_report(action: "cl.Action") -> None:
        session_id = cl.user_session.get("session_id")
        await cl.Message(content="正在根据当前会话内容生成报告，请稍候...").send()
        response = await async_handle_message("帮我生成报告", session_id=session_id)
        await _send_response(response)

    @cl.action_callback("continue_analysis")
    async def on_continue_analysis(action: "cl.Action") -> None:
        label = "继续分析"
        payload = getattr(action, "payload", None)
        if isinstance(payload, dict):
            label = str(payload.get("label") or label)
        await cl.Message(
            content=f"当前动作：{label}。\n\n{_action_guidance(label)}",
            actions=_base_actions(
                ["继续分析", "生成报告"],
                include_export=bool(cl.user_session.get("last_report_markdown")),
            ),
        ).send()

    @cl.action_callback("export_markdown")
    async def on_export_markdown(action: "cl.Action") -> None:
        markdown = cl.user_session.get("last_report_markdown") or ""
        output_path = cl.user_session.get("last_report_output_path")
        if not markdown:
            await cl.Message(content="当前还没有可导出的报告，先生成一份完整报告吧。", actions=_base_actions(["生成报告"])).send()
            return
        message = "下面是最近一次生成的 Markdown 报告。"
        if output_path:
            message += f"\n\n已保存到：`{output_path}`"
        await cl.Message(content=message, actions=_base_actions(["继续分析", "生成报告"], include_export=True)).send()
        await cl.Message(content=markdown).send()

    @cl.action_callback("reset_session")
    async def on_reset_session(action: "cl.Action") -> None:
        session_id = chat_service.start_session()
        cl.user_session.set("session_id", session_id)
        cl.user_session.set("last_report_markdown", "")
        cl.user_session.set("last_report_output_path", None)
        await cl.Message(
            content="已为你开启一个新会话。你可以重新介绍自己的背景、目标岗位或目标城市。",
            actions=_base_actions(["继续分析", "生成报告"]),
        ).send()
