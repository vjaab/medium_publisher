import json
import os
from dataclasses import dataclass

from src.config import config
from src.research.web_researcher import ResearchResult
from src.utils.helpers import count_words, retry_with_backoff
from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ArticleDraft:
    title: str
    subtitle: str
    content: str
    word_count: int
    outline: str


class ArticleWriter:
    def __init__(self):
        self.min_words = config.min_article_words
        self.max_words = config.max_article_words

    def write(self, topic: str, research: ResearchResult) -> ArticleDraft:
        prompt = self._load_prompt("article_writer.txt")
        prompt = prompt.format(
            topic=topic,
            research_summary=research.summary,
            key_points="\n".join(f"- {p}" for p in research.key_points),
            facts="\n".join(f"- {f.get('statement', '')}" for f in research.facts),
            sources="\n".join(f"- {s.get('title', '')}: {s.get('url', '')}" for s in research.sources),
            min_words=self.min_words,
            max_words=self.max_words
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
                {"role": "system", "content": "You are an expert software engineering writer who creates practical, technically accurate articles for developers."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=4000,
        )
        return response.choices[0].message.content

    def _call_anthropic(self, prompt: str) -> str:
        import anthropic
        client = anthropic.Anthropic(api_key=config.llm_api_key)
        response = client.messages.create(
            model=config.llm_model,
            max_tokens=4000,
            temperature=0.7,
            system="You are an expert software engineering writer who creates practical, technically accurate articles for developers.",
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
                max_output_tokens=8192,
            )
        )
        return response.text

    def _parse_response(self, response: str) -> ArticleDraft:
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
            content = data.get("content", "")
            return ArticleDraft(
                title=data.get("title", ""),
                subtitle=data.get("subtitle", ""),
                content=content,
                word_count=count_words(content),
                outline=data.get("outline", "")
            )

        lines = response.split("\n")
        title = ""
        subtitle = ""
        content_lines = []
        in_content = False

        for line in lines:
            if line.startswith("TITLE:") and not title:
                title = line[6:].strip()
            elif line.startswith("SUBTITLE:") and not subtitle:
                subtitle = line[9:].strip()
            elif line.startswith(("CONTENT:", "---")):
                in_content = True
            elif in_content:
                content_lines.append(line)

        content = "\n".join(content_lines).strip()
        return ArticleDraft(
            title=title or "Untitled Article",
            subtitle=subtitle or "",
            content=content,
            word_count=count_words(content),
            outline=""
        )