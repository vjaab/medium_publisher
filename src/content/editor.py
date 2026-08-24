import json
import os
from dataclasses import dataclass
from typing import Any

from src.config import config
from src.content.writer import ArticleDraft
from src.research.web_researcher import ResearchResult
from src.utils.helpers import retry_with_backoff
from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ReviewResult:
    passed: bool
    issues: list[dict[str, Any]]
    suggestions: list[str]
    score: float


class ArticleEditor:
    def __init__(self):
        self.enable_fact_check = config.enable_fact_check

    def review(self, draft: ArticleDraft, research: ResearchResult) -> ReviewResult:
        if not self.enable_fact_check:
            return ReviewResult(passed=True, issues=[], suggestions=[], score=1.0)

        prompt = self._load_prompt("editor.txt")
        prompt = prompt.format(
            title=draft.title,
            subtitle=draft.subtitle,
            content=draft.content,
            research_summary=research.summary,
            key_points="\n".join(f"- {p}" for p in research.key_points),
            facts="\n".join(f"- {f.get('statement', '')}" for f in research.facts),
            sources="\n".join(f"- {s.get('title', '')}: {s.get('url', '')}" for s in research.sources)
        )

        response = self._call_llm(prompt)
        return self._parse_response(response)

    def _load_prompt(self, filename: str) -> str:
        path = os.path.join("prompts", filename)
        with open(path, "r") as f:
            return f.read()

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
                {"role": "system", "content": "You are a senior technical editor who reviews software engineering articles for accuracy, clarity, and quality."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=3000,
        )
        return response.choices[0].message.content

    def _call_anthropic(self, prompt: str) -> str:
        import anthropic
        client = anthropic.Anthropic(api_key=config.llm_api_key)
        response = client.messages.create(
            model=config.llm_model,
            max_tokens=3000,
            temperature=0.2,
            system="You are a senior technical editor who reviews software engineering articles for accuracy, clarity, and quality.",
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
                temperature=0.2,
                max_output_tokens=8192,
            )
        )
        return response.text

    def _parse_response(self, response: str) -> ReviewResult:
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
            return ReviewResult(
                passed=data.get("passed", False),
                issues=data.get("issues", []),
                suggestions=data.get("suggestions", []),
                score=data.get("score", 0.0)
            )

        passed = "PASSED" in response.upper() or "PASS" in response.upper()
        issues = []
        suggestions = []

        for line in response.split("\n"):
            line = line.strip()
            if line.startswith(("- ", "* ")):
                if "issue" in line.lower() or "error" in line.lower() or "incorrect" in line.lower():
                    issues.append({"type": "issue", "description": line[2:]})
                else:
                    suggestions.append(line[2:])

        return ReviewResult(
            passed=passed and len(issues) == 0,
            issues=issues,
            suggestions=suggestions,
            score=0.8 if passed else 0.4
        )