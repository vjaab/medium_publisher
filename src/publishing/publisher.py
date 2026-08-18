from abc import ABC, abstractmethod
from dataclasses import dataclass

from src.content.formatter import FormattedArticle


@dataclass
class PublishResult:
    success: bool
    url: str | None = None
    error: str | None = None
    article_id: str | None = None


class Publisher(ABC):
    @abstractmethod
    def publish(self, article: FormattedArticle) -> PublishResult:
        pass

    @abstractmethod
    def get_user_id(self) -> str:
        pass