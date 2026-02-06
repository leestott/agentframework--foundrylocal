"""
Demo: Weather Tools
───────────────────
Demonstrates **function/tool calling** with multiple tools.

The agent can:
  • Get current weather for a city
  • Get a 5-day forecast
  • Compare weather between cities
  • Recommend activities based on conditions

This showcases how MAF agents can invoke Python functions decorated
with Pydantic metadata, and how the LLM chooses which tool to call.
"""

from __future__ import annotations

import asyncio
import random
import re
from typing import Annotated
from pydantic import Field

from agent_framework import ChatAgent
from agent_framework.openai import OpenAIChatClient

from ..foundry_boot import FoundryConnection
from .registry import register_demo, DemoInfo


# ─── Mock weather data (simulates an API) ────────────────────────

WEATHER_CONDITIONS = ["sunny", "cloudy", "rainy", "partly cloudy", "stormy", "foggy", "snowy"]
CITIES_DATA = {
    "london": {"lat": 51.5, "country": "UK"},
    "new york": {"lat": 40.7, "country": "USA"},
    "tokyo": {"lat": 35.7, "country": "Japan"},
    "sydney": {"lat": -33.9, "country": "Australia"},
    "paris": {"lat": 48.9, "country": "France"},
    "seattle": {"lat": 47.6, "country": "USA"},
    "berlin": {"lat": 52.5, "country": "Germany"},
}


def _mock_temp(city: str) -> int:
    """Generate a plausible temperature based on city latitude."""
    info = CITIES_DATA.get(city.lower(), {"lat": 45})
    base = 25 - abs(info["lat"] - 25) * 0.3
    return int(base + random.randint(-5, 5))


# ─── Tool Functions ──────────────────────────────────────────────

def get_current_weather(
    city: Annotated[str, Field(description="Name of the city to get weather for")],
) -> str:
    """Get the current weather conditions for a city."""
    city_lower = city.lower()
    if city_lower not in CITIES_DATA:
        return f"Weather data not available for '{city}'. Try: London, New York, Tokyo, Sydney, Paris, Seattle, Berlin."
    
    temp = _mock_temp(city)
    condition = random.choice(WEATHER_CONDITIONS)
    humidity = random.randint(30, 90)
    wind = random.randint(5, 30)
    
    return (
        f"Current weather in {city.title()}:\n"
        f"  • Temperature: {temp}°C\n"
        f"  • Condition: {condition}\n"
        f"  • Humidity: {humidity}%\n"
        f"  • Wind: {wind} km/h"
    )


def get_forecast(
    city: Annotated[str, Field(description="Name of the city")],
    days: Annotated[int, Field(description="Number of days (1-5)", ge=1, le=5)] = 3,
) -> str:
    """Get a weather forecast for the next N days."""
    city_lower = city.lower()
    if city_lower not in CITIES_DATA:
        return f"Forecast not available for '{city}'."
    
    lines = [f"Weather forecast for {city.title()} ({days} days):"]
    for i in range(days):
        temp = _mock_temp(city) + random.randint(-3, 3)
        condition = random.choice(WEATHER_CONDITIONS)
        lines.append(f"  Day {i+1}: {temp}°C, {condition}")
    
    return "\n".join(lines)


def compare_weather(
    city1: Annotated[str, Field(description="First city to compare")],
    city2: Annotated[str, Field(description="Second city to compare")],
) -> str:
    """Compare current weather between two cities."""
    temp1 = _mock_temp(city1)
    temp2 = _mock_temp(city2)
    cond1 = random.choice(WEATHER_CONDITIONS)
    cond2 = random.choice(WEATHER_CONDITIONS)
    
    diff = abs(temp1 - temp2)
    warmer = city1 if temp1 > temp2 else city2
    
    return (
        f"Weather comparison:\n"
        f"  {city1.title()}: {temp1}°C, {cond1}\n"
        f"  {city2.title()}: {temp2}°C, {cond2}\n"
        f"  → {warmer.title()} is {diff}°C warmer"
    )


def recommend_activity(
    city: Annotated[str, Field(description="City to get activity recommendations for")],
) -> str:
    """Recommend outdoor activities based on current weather."""
    temp = _mock_temp(city)
    condition = random.choice(WEATHER_CONDITIONS)
    
    activities = []
    if "sunny" in condition or "partly" in condition:
        activities.extend(["hiking", "picnic", "cycling", "sightseeing"])
    if "cloudy" in condition:
        activities.extend(["museum visit", "walking tour", "photography"])
    if "rainy" in condition or "stormy" in condition:
        activities.extend(["visit indoor attractions", "try local cafés", "shopping"])
    if temp > 25:
        activities.extend(["swimming", "beach"])
    if temp < 10:
        activities.extend(["hot chocolate tour", "indoor sports"])
    
    return (
        f"Activity recommendations for {city.title()} ({temp}°C, {condition}):\n"
        f"  • {', '.join(activities[:4])}"
    )


# ─── Demo Class ──────────────────────────────────────────────────

class WeatherDemo:
    """Weather tools demo runner."""
    
    def __init__(self, conn: FoundryConnection):
        self.conn = conn
        self.agent = self._create_agent()
    
    def _create_agent(self) -> ChatAgent:
        client = OpenAIChatClient(
            api_key=self.conn.api_key,
            base_url=self.conn.endpoint,
            model_id=self.conn.model_id,
        )
        return ChatAgent(
            chat_client=client,
            name="WeatherAssistant",
            instructions=(
                "You are a helpful weather assistant. Use the available tools to:\n"
                "  • Get current weather for cities\n"
                "  • Provide forecasts\n"
                "  • Compare weather between locations\n"
                "  • Recommend activities\n\n"
                "Always use the tools when asked about weather. "
                "Be concise in your responses."
            ),
            tools=[get_current_weather, get_forecast, compare_weather, recommend_activity],
        )
    
    async def run(self, prompt: str) -> dict:
        """Run the demo with a user prompt."""
        import time
        t0 = time.perf_counter()
        result = await self.agent.run(prompt)
        elapsed = time.perf_counter() - t0
        
        # Strip <tool_call> XML that some models emit
        text = re.sub(r'<tool_call>.*?</tool_call>\s*', '', str(result), flags=re.DOTALL).strip()
        return {
            "prompt": prompt,
            "response": text,
            "elapsed": round(elapsed, 2),
            "tools_available": ["get_current_weather", "get_forecast", "compare_weather", "recommend_activity"],
        }


# ─── Register Demo ───────────────────────────────────────────────

async def run_weather_demo(conn: FoundryConnection, prompt: str) -> dict:
    """Entry point for the demo registry."""
    demo = WeatherDemo(conn)
    return await demo.run(prompt)


register_demo(DemoInfo(
    id="weather_tools",
    name="Weather Tools",
    description="Multi-tool agent that provides weather information, forecasts, city comparisons, and activity recommendations. Demonstrates function calling with 4 different tools.",
    icon="🌤️",
    category="Tool Calling",
    runner=run_weather_demo,
    tags=["tools", "function-calling", "single-agent"],
    suggested_prompt="What's the weather in Seattle and San Francisco? Compare them and recommend activities for the warmer city.",
))
