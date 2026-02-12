"""
Agent definitions for the Local Research & Synthesis Desk.
──────────────────────────────────────────────────────────
Each agent is a *ChatAgent* from Microsoft Agent Framework backed by an
OpenAI-compatible chat client that points at *Foundry Local*.

Agents
  • PlannerAgent  – breaks the user's question into tasks
  • RetrieverAgent – reads local files and extracts relevant snippets
  • CriticAgent   – reviews for gaps / contradictions
  • WriterAgent   – produces the final report with citations
  • ToolAgent     – utility helper (word count, keyword extraction)

Reference:
  agent-framework-core  – https://pypi.org/project/agent-framework-core/
  MAF orchestration     – https://learn.microsoft.com/en-us/agent-framework/user-guide/workflows/orchestrations/overview
"""

from __future__ import annotations

import logging
from typing import Annotated

from pydantic import Field

from agent_framework import ChatAgent
from agent_framework.openai import OpenAIChatClient

from .foundry_boot import FoundryConnection

log = logging.getLogger(__name__)

# ────────────────────────────────────────────────────────────────────
# Helper: build a ChatAgent wired to Foundry Local
# ────────────────────────────────────────────────────────────────────

def _make_client(conn: FoundryConnection) -> OpenAIChatClient:
    """Create an MAF OpenAIChatClient pointing at Foundry Local."""
    return OpenAIChatClient(
        api_key=conn.api_key,
        base_url=conn.endpoint,
        model_id=conn.model_id,
    )


# ────────────────────────────────────────────────────────────────────
# Tool functions (used by ToolAgent)
# ────────────────────────────────────────────────────────────────────

def word_count(
    text: Annotated[str, Field(description="Text to count words in.")],
) -> str:
    """Return the word count of the given text."""
    count = len(text.split())
    return f"Word count: {count}"


def extract_keywords(
    text: Annotated[str, Field(description="Text to extract keywords from.")],
) -> str:
    """Extract simple keywords (words appearing more than once, len>4)."""
    words = text.lower().split()
    freq: dict[str, int] = {}
    for w in words:
        cleaned = "".join(c for c in w if c.isalnum())
        if len(cleaned) > 4:
            freq[cleaned] = freq.get(cleaned, 0) + 1
    keywords = sorted(
        (w for w, c in freq.items() if c > 1),
        key=lambda w: freq[w],
        reverse=True,
    )[:10]
    return f"Keywords: {', '.join(keywords) if keywords else '(none detected)'}"


# ────────────────────────────────────────────────────────────────────
# Agent factory functions
# ────────────────────────────────────────────────────────────────────

def create_planner(conn: FoundryConnection) -> ChatAgent:
    return ChatAgent(
        chat_client=_make_client(conn),
        name="Planner",
        instructions=(
            "You are a planning agent. Given a user research question and a set of "
            "document snippets (if any), break the question into 2-4 concrete sub-tasks. "
            "Output ONLY a numbered list of tasks. Each task should state:\n"
            "  • What information is needed\n"
            "  • Which source documents might help (if known)\n"
            "Keep it concise — no more than 6 lines total."
        ),
    )


def create_retriever(conn: FoundryConnection) -> ChatAgent:
    return ChatAgent(
        chat_client=_make_client(conn),
        name="Retriever",
        instructions=(
            "You are a retrieval agent. You receive a research plan AND raw document "
            "text from local files. Your job:\n"
            "  1. Identify the most relevant passages for each task in the plan.\n"
            "  2. Output extracted snippets with citations in the format:\n"
            "     [filename.ext, lines X-Y]: \"quoted text…\"\n"
            "  3. If no relevant content exists, say so explicitly.\n"
            "Be precise — quote only what is relevant, keep each snippet under 100 words."
        ),
    )


def create_critic(conn: FoundryConnection) -> ChatAgent:
    return ChatAgent(
        chat_client=_make_client(conn),
        name="Critic",
        instructions=(
            "You are a critical review agent. You receive a plan and extracted snippets. "
            "Your job:\n"
            "  1. Check for gaps — are any plan tasks unanswered?\n"
            "  2. Check for contradictions between snippets.\n"
            "  3. Suggest 1-2 specific improvements or missing details.\n\n"
            "OUTPUT FORMAT (you MUST follow this exactly):\n"
            "  • If there are gaps or issues, start your response with the line:\n"
            "      GAPS FOUND\n"
            "    then list the specific gaps or issues as a numbered list.\n"
            "  • If everything looks complete, start your response with the line:\n"
            "      NO GAPS\n"
            "    then briefly confirm the snippets are sufficient."
        ),
    )


def create_writer(conn: FoundryConnection) -> ChatAgent:
    return ChatAgent(
        chat_client=_make_client(conn),
        name="Writer",
        instructions=(
            "You are the final report writer. You receive:\n"
            "  • The original question\n"
            "  • A plan, extracted snippets with citations, and a critic review\n\n"
            "Produce a clear, well-structured answer (3-5 paragraphs). "
            "Requirements:\n"
            "  • Cite sources using [filename.ext, lines X-Y] notation\n"
            "  • Address any gaps the critic raised (note if unresolvable)\n"
            "  • End with a one-sentence summary\n"
            "Do NOT fabricate citations — only use citations provided by the Retriever."
        ),
    )


def create_tool_agent(conn: FoundryConnection) -> ChatAgent:
    return ChatAgent(
        chat_client=_make_client(conn),
        name="ToolHelper",
        instructions=(
            "You are a utility agent. Use the provided tools to compute "
            "word counts or extract keywords when asked. Return the tool "
            "output directly — do not embellish."
        ),
        tools=[word_count, extract_keywords],
    )
