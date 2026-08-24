import json
import os
from dataclasses import dataclass

from src.config import config
from src.storage.database import db
from src.utils.helpers import retry_with_backoff
from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class TopicCandidate:
    topic: str
    category: str
    score: float
    reasoning: str
    search_potential: float
    originality: float


class TopicFinder:
    def __init__(self):
        self.categories = config.content_categories

    def generate_topics(self, count: int = 10, manual_topic: str | None = None) -> list[TopicCandidate]:
        if manual_topic:
            return [TopicCandidate(
                topic=manual_topic,
                category="Manual",
                score=1.0,
                reasoning="Manually specified topic",
                search_potential=0.8,
                originality=0.9
            )]

        prompt = self._load_prompt("topic_selection.txt")
        prompt = prompt.format(
            categories=", ".join(self.categories),
            count=count,
            recent_topics=self._get_recent_topics()
        )

        response = self._call_llm(prompt)
        candidates = self._parse_response(response)

        scored = self._score_candidates(candidates)
        scored.sort(key=lambda x: x.score, reverse=True)
        return scored[:count]

    def _get_recent_topics(self) -> str:
        recent = db.get_recent_articles(20)
        if not recent:
            return "No recent topics."
        return "\n".join([f"- {a.topic} ({a.title})" for a in recent])

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
                {"role": "system", "content": "You are an expert technical content strategist for software developers."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=2000,
        )
        return response.choices[0].message.content

    def _call_anthropic(self, prompt: str) -> str:
        import anthropic
        client = anthropic.Anthropic(api_key=config.llm_api_key)
        response = client.messages.create(
            model=config.llm_model,
            max_tokens=2000,
            temperature=0.7,
            system="You are an expert technical content strategist for software developers.",
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
                temperature=0.7,
                max_output_tokens=2000,
            )
        )
        return response.text

    def _parse_response(self, response: str) -> list[dict]:
        import re

        def try_parse_json(text: str):
            start = text.find("[")
            end = text.rfind("]") + 1
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
            return data

        lines = response.strip().split("\n")
        candidates = []
        for line in lines:
            if line.strip() and not line.startswith("#"):
                parts = line.split("|")
                if len(parts) >= 2:
                    candidates.append({
                        "topic": parts[0].strip(),
                        "category": parts[1].strip() if len(parts) > 1 else "General",
                        "reasoning": parts[2].strip() if len(parts) > 2 else ""
                    })
        return candidates

    def _score_candidates(self, candidates: list[dict]) -> list[TopicCandidate]:
        scored = []
        for c in candidates:
            topic = c.get("topic", "")
            category = c.get("category", "General")
            reasoning = c.get("reasoning", "")

            if db.check_similar_topic(topic):
                logger.info(f"Skipping similar topic: {topic}")
                continue

            relevance = self._score_relevance(topic, category)
            interest = self._score_current_interest(topic)
            search = self._score_search_potential(topic)
            usefulness = self._score_developer_usefulness(topic)
            originality = self._score_originality(topic)
            sources = self._score_source_availability(topic)
            longevity = self._score_longevity(topic)

            total_score = (
                relevance * 0.20 +
                interest * 0.15 +
                search * 0.15 +
                usefulness * 0.20 +
                originality * 0.15 +
                sources * 0.10 +
                longevity * 0.05
            )

            scored.append(TopicCandidate(
                topic=topic,
                category=category,
                score=total_score,
                reasoning=reasoning,
                search_potential=search,
                originality=originality
            ))

        return scored

    def _score_relevance(self, topic: str, category: str) -> float:
        if category in self.categories:
            return 0.9
        return 0.5

    def _score_current_interest(self, topic: str) -> float:
        keywords_high = ["ai", "llm", "rag", "virtual threads", "spring boot 3", "aws", "kubernetes", "rust", "wasm"]
        keywords_med = ["microservices", "docker", "ci/cd", "testing", "architecture", "performance"]
        topic_lower = topic.lower()
        if any(k in topic_lower for k in keywords_high):
            return 0.9
        if any(k in topic_lower for k in keywords_med):
            return 0.7
        return 0.5

    def _score_search_potential(self, topic: str) -> float:
        return 0.7

    def _score_developer_usefulness(self, topic: str) -> float:
        practical_keywords = ["how to", "tutorial", "guide", "implementation", "example", "best practices", "patterns", "mistakes"]
        topic_lower = topic.lower()
        if any(k in topic_lower for k in practical_keywords):
            return 0.9
        return 0.6

    def _score_originality(self, topic: str) -> float:
        return 0.7

    def _score_source_availability(self, topic: str) -> float:
        official_keywords = ["official", "documentation", "github", "aws", "spring", "java", "python", "rust", "kubernetes"]
        topic_lower = topic.lower()
        if any(k in topic_lower for k in official_keywords):
            return 0.9
        return 0.6

    def _score_longevity(self, topic: str) -> float:
        evergreen = ["patterns", "architecture", "best practices", "fundamentals", "principles", "design"]
        trendy = ["new release", "just launched", "announced", "preview", "beta"]
        topic_lower = topic.lower()
        if any(k in topic_lower for k in evergreen):
            return 0.9
        if any(k in topic_lower for k in trendy):
            return 0.4
        return 0.6