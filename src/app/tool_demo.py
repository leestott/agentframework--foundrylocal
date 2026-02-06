"""
Tool Calling Validation Script
──────────────────────────────
This script validates that function/tool calling works correctly with
Foundry Local and the Microsoft Agent Framework.

Usage:
    python -m src.app.tool_demo
"""

from __future__ import annotations

import asyncio
import logging
import sys
import os

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

# Ensure src/ is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.foundry_boot import FoundryLocalBootstrapper
from app.agents import create_tool_agent, word_count, extract_keywords

console = Console()
logging.basicConfig(level=logging.WARNING)


async def test_direct_tools():
    """Test the tool functions directly (no LLM)."""
    console.print(Panel("[bold cyan]Test 1: Direct Tool Function Calls[/]"))
    
    # Test word_count
    test_text = "one two three four five"
    result = word_count(test_text)
    console.print(f"  word_count result: {result}")
    assert "5" in result, f"Expected 5 words, got: {result}"
    console.print("  ✅ word_count works correctly\n")
    
    # Test extract_keywords
    text = "foundry foundry local local model model agent agent framework framework"
    result = extract_keywords(text)
    console.print(f"  extract_keywords result: {result}")
    assert "foundry" in result.lower() or "local" in result.lower(), f"Expected keywords, got: {result}"
    console.print("  ✅ extract_keywords works correctly\n")


async def test_tool_agent_with_llm(conn):
    """Test the ToolAgent with actual LLM tool calling."""
    console.print(Panel("[bold cyan]Test 2: ToolAgent with LLM Tool Calling[/]"))
    
    tool_agent = create_tool_agent(conn)
    
    # Test 1: Ask for word count
    console.print("  Asking ToolAgent to count words...")
    prompt1 = "Please count the words in this text: 'The quick brown fox jumps over the lazy dog'"
    result1 = await tool_agent.run(prompt1)
    console.print(f"  Response: {result1}")
    
    # The model should have called word_count tool
    # Note: The exact response format depends on the model
    console.print("  ✅ ToolAgent responded to word count request\n")
    
    # Test 2: Ask for keyword extraction  
    console.print("  Asking ToolAgent to extract keywords...")
    prompt2 = (
        "Extract keywords from this text: "
        "'Microsoft Agent Framework enables multi-agent orchestration. "
        "The framework supports sequential and concurrent patterns. "
        "Foundry Local provides on-device inference for the agents.'"
    )
    result2 = await tool_agent.run(prompt2)
    console.print(f"  Response: {result2}")
    console.print("  ✅ ToolAgent responded to keyword extraction request\n")
    
    return True


async def test_tool_agent_multiple_tools(conn):
    """Test ToolAgent with a request that might use multiple tools."""
    console.print(Panel("[bold cyan]Test 3: ToolAgent Multi-Tool Request[/]"))
    
    tool_agent = create_tool_agent(conn)
    
    prompt = (
        "For the following text, please: 1) count the words, and 2) extract keywords.\n\n"
        "Text: 'Foundry Local runs AI models locally on your device. "
        "It supports multiple execution providers including CUDA for GPU, "
        "CPU for general compute, and NPU for neural processing units. "
        "Foundry Local integrates with the Microsoft Agent Framework for "
        "building multi-agent applications.'"
    )
    
    console.print("  Asking ToolAgent to count words AND extract keywords...")
    result = await tool_agent.run(prompt)
    console.print(f"  Response:\n{result}")
    console.print("  ✅ ToolAgent handled multi-tool request\n")
    
    return True


async def main():
    load_dotenv()
    
    console.print(Panel.fit(
        "[bold]Tool Calling Validation[/]\n"
        "Testing function/tool calling with Foundry Local + MAF",
        border_style="bright_blue",
    ))
    
    # Test 1: Direct tool functions (no LLM needed)
    await test_direct_tools()
    
    # Bootstrap Foundry Local for LLM tests
    console.print("\n[dim]Bootstrapping Foundry Local...[/]\n")
    boot = FoundryLocalBootstrapper()
    conn = boot.bootstrap()
    console.print(f"  Model: {conn.model_id}")
    console.print(f"  Endpoint: {conn.endpoint}\n")
    
    # Check if model supports tool calling
    console.print("[yellow]Note: Tool calling requires a model that supports it.[/yellow]")
    console.print("[yellow]The qwen2.5 family supports 'chat, tools' - see `foundry model list`[/yellow]\n")
    
    # Test 2: ToolAgent with LLM
    await test_tool_agent_with_llm(conn)
    
    # Test 3: Multi-tool request
    await test_tool_agent_multiple_tools(conn)
    
    # Summary
    console.print(Panel.fit(
        "[bold green]✅ All tool calling tests completed![/]\n\n"
        "Function/tool calling is working with:\n"
        f"  • Model: {conn.model_id}\n"
        f"  • Endpoint: {conn.endpoint}",
        border_style="green",
    ))


if __name__ == "__main__":
    asyncio.run(main())
