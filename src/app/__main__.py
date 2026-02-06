"""
CLI entry-point for the Local Research & Synthesis Desk.
────────────────────────────────────────────────────────
Usage:
    python -m app "your research question" --docs ./data
    python -m app "summarise the key themes" --docs ./data --mode sequential

Modes:
    full       — Sequential + Concurrent patterns (default)
    sequential — Pure sequential pipeline only
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import os
import time

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

# ── Ensure the src/ directory is on the module path ─────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.foundry_boot import FoundryLocalBootstrapper       # noqa: E402
from app.documents import load_documents                     # noqa: E402
from app.orchestrator import run_full_workflow, run_sequential  # noqa: E402

console = Console()


def _configure_logging(level_name: str) -> None:
    level = getattr(logging, level_name.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s  %(name)-28s  %(levelname)-7s  %(message)s",
        datefmt="%H:%M:%S",
    )
    # Quieten noisy HTTP libraries
    for noisy in ("httpx", "httpcore", "openai", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(
        prog="app",
        description="Local Research & Synthesis Desk — multi-agent demo",
    )
    parser.add_argument(
        "question",
        help="Your research question (wrap in quotes).",
    )
    parser.add_argument(
        "--docs",
        default=os.getenv("DOCS_PATH", "./data"),
        help="Path to a folder of local documents (default: ./data).",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Foundry Local model alias (default from .env or qwen2.5).",
    )
    parser.add_argument(
        "--mode",
        choices=["full", "sequential"],
        default="full",
        help="Orchestration mode: 'full' (sequential+concurrent) or 'sequential'.",
    )
    parser.add_argument(
        "--log-level",
        default=os.getenv("LOG_LEVEL", "INFO"),
        help="Log level (DEBUG, INFO, WARNING, ERROR).",
    )
    args = parser.parse_args()

    _configure_logging(args.log_level)

    # ── Banner ───────────────────────────────────────────────────
    console.print(
        Panel.fit(
            "[bold]Local Research & Synthesis Desk[/]\n"
            "Multi-Agent Orchestration  •  MAF + Foundry Local\n"
            f"Mode: [cyan]{args.mode}[/]",
            border_style="bright_blue",
        )
    )

    # ── 1. Bootstrap Foundry Local ───────────────────────────────
    console.print("\n[dim]Bootstrapping Foundry Local …[/]\n")
    boot = FoundryLocalBootstrapper(alias=args.model)
    conn = boot.bootstrap()
    console.print(
        f"  Model : [bold]{conn.model_id}[/]  (alias: {conn.model_alias})\n"
        f"  Endpoint: {conn.endpoint}\n"
    )

    # ── 2. Load local documents ──────────────────────────────────
    docs = load_documents(args.docs)
    console.print(
        f"  Documents: [bold]{docs.file_count}[/] file(s), "
        f"{len(docs.chunks)} chunk(s) from [cyan]{args.docs}[/]\n"
    )

    if not docs.chunks:
        console.print(
            "[yellow]⚠  No documents found. The Retriever will have nothing to cite.\n"
            "   Add .txt or .md files to the --docs folder and re-run.[/]\n"
        )

    # ── 3. Run the multi-agent workflow ──────────────────────────
    console.print(Panel("Starting multi-agent workflow …", style="bold green"))
    t0 = time.perf_counter()

    if args.mode == "sequential":
        wf = asyncio.run(run_sequential(args.question, docs, conn))
    else:
        wf = asyncio.run(run_full_workflow(args.question, docs, conn))

    total = time.perf_counter() - t0

    # ── 4. Summary ───────────────────────────────────────────────
    console.print(Panel.fit("[bold green]✅  Workflow complete[/]", border_style="green"))
    console.print(f"  Total time : {total:.1f}s")
    console.print(f"  Steps      : {len(wf.steps)}")
    for s in wf.steps:
        console.print(f"    • {s.agent_name:12s}  {s.elapsed_sec:.1f}s")

    console.print("\n[bold]═══ Final Report ═══[/]\n")
    console.print(Markdown(wf.final_report))


if __name__ == "__main__":
    main()
