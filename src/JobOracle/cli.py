from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

if __package__ in {None, ""}:
    package_dir = Path(__file__).resolve().parent
    parent_dir = str(package_dir.parent)
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)
    __package__ = package_dir.name

from .models import EmploymentRequest
from .offerstar_crawler import run_cli as run_offerstar_cli
from .profile import normalize_profile
from .service import EmploymentAdvisor


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="JobOracle employment market analysis and guidance tool")
    parser.add_argument("query", nargs="?", help="Employment question to analyze")
    parser.add_argument(
        "--mode",
        choices=["auto", "market", "guidance"],
        default="auto",
        help="Analysis mode",
    )
    parser.add_argument(
        "--profile-json",
        default="",
        help="Inline JSON string for candidate profile",
    )
    parser.add_argument(
        "--profile-file",
        default="",
        help="Path to a JSON file containing candidate profile",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Do not save the markdown report to disk",
    )
    parser.add_argument(
        "--print-only",
        action="store_true",
        help="Print the report and suppress the trailing metadata output",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress stage progress output",
    )
    parser.add_argument(
        "--use-offerstar",
        action="store_true",
        help="Use OfferStar crawler results as part of retrieval",
    )
    parser.add_argument(
        "--offerstar-from-page",
        type=int,
        default=1,
        help="OfferStar start page when crawler is enabled",
    )
    parser.add_argument(
        "--offerstar-to-page",
        type=int,
        default=1,
        help="OfferStar end page when crawler is enabled",
    )
    parser.add_argument(
        "--offerstar-max-items",
        type=int,
        default=20,
        help="Maximum OfferStar rows to keep when crawler is enabled",
    )
    return parser.parse_args()


def load_profile(args: argparse.Namespace) -> dict[str, object]:
    if args.profile_json:
        return normalize_profile(json.loads(args.profile_json))
    if args.profile_file:
        return normalize_profile(json.loads(Path(args.profile_file).read_text(encoding="utf-8")))
    return {}


def _now() -> str:
    return datetime.now().strftime("%H:%M:%S")


def _print_divider(char: str = "=") -> None:
    print(char * 72)


def _render_progress_bar(progress: int, width: int = 24) -> str:
    progress = max(0, min(100, progress))
    filled = round(width * progress / 100)
    return "[" + "#" * filled + "-" * (width - filled) + f"] {progress:>3d}%"


def _print_header(query: str, mode: str, has_profile: bool, save: bool, use_offerstar: bool) -> None:
    _print_divider("=")
    print("JobOracle CLI")
    _print_divider("=")
    print(f"[{_now()}] 问题: {query}")
    print(f"[{_now()}] 模式: {mode}")
    print(f"[{_now()}] 用户画像: {'已提供' if has_profile else '未提供'}")
    print(f"[{_now()}] 报告保存: {'开启' if save else '关闭'}")
    print(f"[{_now()}] OfferStar 爬虫: {'开启' if use_offerstar else '关闭'}")
    _print_divider("-")
    print(f"[{_now()}] 已启动分析流程，请稍候...")


def _print_stage(stage: str, message: str, progress: int, meta: dict[str, object] | None) -> None:
    print(f"[{_now()}] {message}")
    print(f"[{_now()}] {_render_progress_bar(progress)}")
    if stage == "search_plan" and meta:
        queries = meta.get("queries")
        if isinstance(queries, list):
            for index, query in enumerate(queries, start=1):
                print(f"[{_now()}]   查询 {index}: {query}")
    if stage == "search_done" and meta:
        count = meta.get("results_count")
        print(f"[{_now()}]   检索证据数: {count}")
    if stage == "offerstar_done" and meta:
        count = meta.get("results_count")
        print(f"[{_now()}]   OfferStar 岗位数: {count}")
    if stage in {"researcher_done", "analyst_done", "advisor_done"} and meta:
        used_llm = meta.get("used_llm")
        mode = "LLM" if used_llm else "fallback"
        print(f"[{_now()}]   当前阶段生成方式: {mode}")


def _print_footer(report_path: str | None) -> None:
    _print_divider("-")
    if report_path:
        print(f"[{_now()}] 报告已保存到: {report_path}")
    else:
        print(f"[{_now()}] 本次未保存报告文件")
    _print_divider("=")


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "crawl-offerstar":
        raise SystemExit(run_offerstar_cli(sys.argv[2:]))

    args = parse_args()
    query = args.query or input("请输入就业分析问题: ").strip()
    if not query:
        raise SystemExit("query 不能为空")

    profile = load_profile(args)
    if not args.print_only and not args.quiet:
        _print_header(
            query=query,
            mode=args.mode,
            has_profile=bool(profile),
            save=not args.no_save,
            use_offerstar=args.use_offerstar,
        )

    advisor = EmploymentAdvisor()

    def progress_callback(stage: str, message: str, progress: int, meta: dict[str, object] | None) -> None:
        if not args.print_only and not args.quiet:
            _print_stage(stage, message, progress, meta)

    try:
        report = advisor.analyze(
            EmploymentRequest(
                query=query,
                mode=args.mode,
                profile=profile,
                save=not args.no_save,
                use_offerstar=args.use_offerstar,
                offerstar_page_from=args.offerstar_from_page,
                offerstar_page_to=args.offerstar_to_page,
                offerstar_max_items=args.offerstar_max_items,
            ),
            progress_callback=progress_callback,
        )
    except KeyboardInterrupt:
        if not args.quiet:
            _print_divider("-")
            print(f"[{_now()}] 用户中断了本次分析")
        raise SystemExit(130)
    except Exception as exc:
        if not args.quiet:
            _print_divider("-")
            print(f"[{_now()}] 分析失败: {exc}")
        raise SystemExit(1) from exc

    if not args.print_only and not args.quiet:
        _print_footer(report.output_path)

    print(report.markdown)

    if not args.print_only and not args.quiet:
        print("\n---")
        print(f"mode: {report.mode}")
        print(f"used_llm: {report.used_llm}")
        print(f"used_search: {report.used_search}")
        print(f"search_results: {len(report.search_results)}")
        print(f"agent_notes: {len(report.agent_notes)}")
        print(f"output_path: {report.output_path or 'not saved'}")


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        try:
            sys.stdout.close()
        except Exception:
            pass
