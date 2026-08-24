import json
import os
from dataclasses import dataclass
from typing import Any

from src.config import config
from src.utils.helpers import retry_with_backoff
from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ResearchResult:
    topic: str
    summary: str
    key_points: list[str]
    facts: list[dict[str, Any]]
    sources: list[dict[str, str]]


class WebResearcher:
    def __init__(self):
        self.provider = config.search_provider.lower()

    def research(self, topic: str) -> ResearchResult:
        if not config.enable_research:
            return ResearchResult(
                topic=topic,
                summary="Research disabled",
                key_points=[],
                facts=[],
                sources=[]
            )

        prompt = self._load_prompt("research.txt")
        prompt = prompt.format(topic=topic)

        search_results = self._search_web(topic)
        prompt += f"\n\nSearch Results:\n{json.dumps(search_results, indent=2)}"

        response = self._call_llm(prompt)
        return self._parse_response(topic, response, search_results)

    def _load_prompt(self, filename: str) -> str:
        path = os.path.join("prompts", filename)
        with open(path, "r") as f:
            return f.read()

    @retry_with_backoff(max_attempts=3, base_delay=2.0)
    def _search_web(self, query: str) -> list[dict[str, str]]:
        if self.provider == "serpapi":
            return self._search_serpapi(query)
        elif self.provider == "duckduckgo":
            return self._search_duckduckgo(query)
        elif self.provider == "tavily":
            return self._search_tavily(query)
        else:
            logger.warning(f"Unknown search provider: {self.provider}, returning empty results")
            return []

    def _search_serpapi(self, query: str) -> list[dict[str, str]]:
        import requests
        params = {
            "engine": "google",
            "q": query,
            "api_key": config.search_api_key,
            "num": 10,
            "hl": "en",
        }
        response = requests.get("https://serpapi.com/search", params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        results = []
        for item in data.get("organic_results", [])[:8]:
            results.append({
                "title": item.get("title", ""),
                "url": item.get("link", ""),
                "snippet": item.get("snippet", ""),
                "source": "google"
            })
        return results

    def _search_duckduckgo(self, query: str) -> list[dict[str, str]]:
        import urllib.parse

        import requests
        from bs4 import BeautifulSoup

        url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
        headers = {"User-Agent": "Mozilla/5.0 (compatible; MediumBot/1.0)"}
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        results = []
        for result in soup.select(".result__snippet")[:8]:
            text = result.get_text(strip=True)
            link = result.find_previous("a", class_="result__url")
            title_elem = result.find_previous("a", class_="result__snippet")
            results.append({
                "title": title_elem.get_text(strip=True) if title_elem else "Result",
                "url": link.get("href", "") if link else "",
                "snippet": text,
                "source": "duckduckgo"
            })
        return results

    def _search_tavily(self, query: str) -> list[dict[str, str]]:
        import requests
        response = requests.post(
            "https://api.tavily.com/search",
            json={
                "api_key": config.search_api_key,
                "query": query,
                "search_depth": "advanced",
                "max_results": 8,
                "include_domains": ["github.com", "aws.amazon.com", "spring.io", "docs.oracle.com", "docs.python.org", "rust-lang.org"]
            },
            timeout=30
        )
        response.raise_for_status()
        data = response.json()

        results = []
        for item in data.get("results", []):
            results.append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "snippet": item.get("content", ""),
                "source": "tavily"
            })
        return results

    @retry_with_backoff(max_attempts=3, base_delay=2.0)
    def _call_llm(self, prompt: str) -> str:
        provider = config.llm_provider.lower()
        if provider == "openai":
            return self._call_openai(prompt)
        elif provider == "anthropic":
            return self._call_anthropic(prompt)
        elif provider == "gemini":
            return self._call_gemini(prompt)
        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")

    def _call_openai(self, prompt: str) -> str:
        import openai
        client = openai.OpenAI(api_key=config.llm_api_key)
        response = client.chat.completions.create(
            model=config.llm_model,
            messages=[
                {"role": "system", "content": "You are a technical researcher who extracts accurate, well-sourced information for software engineering articles."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=3000,
        )
        return response.choices[0].message.content

    def _call_anthropic(self, prompt: str) -> str:
        import anthropic
        client = anthropic.Anthropic(api_key=config.llm_api_key)
        response = client.messages.create(
            model=config.llm_model,
            max_tokens=3000,
            temperature=0.3,
            system="You are a technical researcher who extracts accurate, well-sourced information for software engineering articles.",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text

    def _call_gemini(self, prompt: str) -> str:
        import google.generativeai as genai
        genai.configure(api_key=config.llm_api_key)
        model = genai.GenerativeModel(config.llm_model)
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.3,
                max_output_tokens=8192,
            )
        )
        return response.text

    def _parse_response(self, topic: str, response: str, search_results: list[dict]) -> ResearchResult:
        import re

        def try_parse_json(text: str):
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(text[start:end])
            return None

        data = try_parse_json(response)
        if data is None:
            cleaned = re.sub(r",\s*([}\]])", r"\1", response)
            data = try_parse_json(cleaned)
        if data is None:
            cleaned = re.sub(r'([{,])\s*(\w+)\s*:', r'\1"\2":', response)
            data = try_parse_json(cleaned)

        if data is not None:
            return ResearchResult(
                topic=topic,
                summary=data.get("summary", ""),
                key_points=data.get("key_points", []),
                facts=data.get("facts", []),
                sources=data.get("sources", search_results)
            )

        return ResearchResult(
            topic=topic,
            summary=self._extract_section(response, "summary"),
            key_points=self._extract_list(response, "key_points"),
            facts=self._extract_facts(response),
            sources=search_results
        )

    def _extract_section(self, text: str, section: str) -> str:
        import re
        pattern = rf"{section}[:]\s*(.*?)(?:\n\n|\n[A-Z]|$)"
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        return match.group(1).strip() if match else ""

    def _extract_list(self, text: str, section: str) -> list[str]:
        import re
        content = self._extract_section(text, section)
        items = re.findall(r"[-*•]\s*(.+)", content)
        return [item.strip() for item in items if item.strip()]

    def _extract_facts(self, text: str) -> list[dict[str, Any]]:
        facts = []
        fact_section = self._extract_section(text, "facts")
        for line in fact_section.split("\n"):
            line = line.strip()
            if line and line.startswith(("-", "*")) or (line and line[0].isdigit()):
                clean = line.lstrip("-*0123456789. ").strip()
                if clean:
                    facts.append({"statement": clean, "verified": False})
        return facts