import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


GEMINI_MODELS = [
    "gemini-2.5-pro",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-1.5-pro",
    "gemini-1.5-flash",
    "gemini-1.5-flash-8b",
]


@dataclass
class Config:
    llm_api_key: str
    llm_provider: str
    llm_model: str
    search_api_key: str
    search_provider: str
    medium_token: str
    medium_publication_id: str | None
    articles_per_day: int
    min_article_words: int
    max_article_words: int
    content_categories: list[str]
    enable_research: bool
    enable_fact_check: bool
    enable_duplicate_check: bool
    dry_run: bool
    database_path: str
    log_level: str
    retry_attempts: int
    retry_base_delay: float

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            llm_api_key=os.getenv("LLM_API_KEY", ""),
            llm_provider=os.getenv("LLM_PROVIDER", "openai"),
            llm_model=os.getenv("LLM_MODEL", "gpt-4o"),
            search_api_key=os.getenv("SEARCH_API_KEY", ""),
            search_provider=os.getenv("SEARCH_PROVIDER", "serpapi"),
            medium_token=os.getenv("MEDIUM_TOKEN", ""),
            medium_publication_id=os.getenv("MEDIUM_PUBLICATION_ID"),
            articles_per_day=int(os.getenv("ARTICLES_PER_DAY", "1")),
            min_article_words=int(os.getenv("MIN_ARTICLE_WORDS", "1200")),
            max_article_words=int(os.getenv("MAX_ARTICLE_WORDS", "2000")),
            content_categories=[
                c.strip() for c in os.getenv("CONTENT_CATEGORIES", "AI,Software Engineering,Java,Spring Boot,AWS,Cloud,Developer Productivity,Programming,Open Source,Developer Tools,Technology Trends,Career Growth for Developers").split(",")
            ],
            enable_research=os.getenv("ENABLE_RESEARCH", "true").lower() == "true",
            enable_fact_check=os.getenv("ENABLE_FACT_CHECK", "true").lower() == "true",
            enable_duplicate_check=os.getenv("ENABLE_DUPLICATE_CHECK", "true").lower() == "true",
            dry_run=os.getenv("DRY_RUN", "false").lower() == "true",
            database_path=os.getenv("DATABASE_PATH", "data/articles.db"),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            retry_attempts=int(os.getenv("RETRY_ATTEMPTS", "3")),
            retry_base_delay=float(os.getenv("RETRY_BASE_DELAY", "2.0")),
        )

    def validate(self) -> list[str]:
        errors = []
        if not self.llm_api_key:
            errors.append("LLM_API_KEY is required")
        if not self.search_api_key:
            errors.append("SEARCH_API_KEY is required")
        if not self.medium_token and not self.dry_run:
            errors.append("MEDIUM_TOKEN is required for publishing")
        if self.articles_per_day < 1:
            errors.append("ARTICLES_PER_DAY must be at least 1")
        if self.min_article_words > self.max_article_words:
            errors.append("MIN_ARTICLE_WORDS cannot exceed MAX_ARTICLE_WORDS")
        return errors


config = Config.from_env()