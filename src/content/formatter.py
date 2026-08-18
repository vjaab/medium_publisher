import re
from dataclasses import dataclass

from src.content.seo import SEOMetadata
from src.content.writer import ArticleDraft
from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class FormattedArticle:
    title: str
    subtitle: str
    content: str
    tags: list


class MediumFormatter:
    def format(self, draft: ArticleDraft, seo: SEOMetadata) -> FormattedArticle:
        content = draft.content

        content = self._normalize_headings(content)
        content = self._format_code_blocks(content)
        content = self._format_lists(content)
        content = self._format_emphasis(content)
        content = self._format_quotes(content)
        content = self._clean_up(content)

        title = seo.medium_title or draft.title
        subtitle = seo.subtitle or draft.subtitle
        tags = seo.tags[:5] if seo.tags else ["software engineering", "programming"]

        return FormattedArticle(
            title=title,
            subtitle=subtitle,
            content=content,
            tags=tags
        )

    def _normalize_headings(self, content: str) -> str:
        lines = content.split("\n")
        result = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("### "):
                result.append(f"### {stripped[4:]}")
            elif stripped.startswith("## "):
                result.append(f"## {stripped[3:]}")
            elif stripped.startswith("# ") and not result:
                result.append(f"## {stripped[2:]}")
            elif re.match(r"^[A-Z][A-Za-z\s]+:$", stripped) and len(stripped) < 80:
                result.append(f"## {stripped[:-1]}")
            else:
                result.append(line)
        return "\n".join(result)

    def _format_code_blocks(self, content: str) -> str:
        pattern = r"```(\w*)\n(.*?)\n```"
        def replace(match):
            lang = match.group(1) or ""
            code = match.group(2).rstrip()
            return f"```{lang}\n{code}\n```"
        return re.sub(pattern, replace, content, flags=re.DOTALL)

    def _format_lists(self, content: str) -> str:
        lines = content.split("\n")
        result = []
        for line in lines:
            stripped = line.strip()
            if re.match(r"^\d+\.\s", stripped):
                result.append(stripped)
            elif re.match(r"^[-*•]\s", stripped):
                result.append(f"- {stripped[1:].strip()}")
            else:
                result.append(line)
        return "\n".join(result)

    def _format_emphasis(self, content: str) -> str:
        content = re.sub(r"\*\*(.+?)\*\*", r"**\1**", content)
        content = re.sub(r"__(.+?)__", r"**\1**", content)
        content = re.sub(r"\*(.+?)\*", r"*\1*", content)
        content = re.sub(r"_(.+?)_", r"*\1*", content)
        return content

    def _format_quotes(self, content: str) -> str:
        lines = content.split("\n")
        result = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("> "):
                result.append(stripped)
            elif stripped.startswith('"') and stripped.endswith('"') and len(stripped) > 20:
                result.append(f"> {stripped[1:-1]}")
            else:
                result.append(line)
        return "\n".join(result)

    def _clean_up(self, content: str) -> str:
        content = re.sub(r"\n{3,}", "\n\n", content)
        content = content.strip()
        return content