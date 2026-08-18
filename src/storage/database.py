import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from src.config import config
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ArticleStatus(str, Enum):
    TOPIC_SELECTED = "TOPIC_SELECTED"
    RESEARCHED = "RESEARCHED"
    GENERATED = "GENERATED"
    REVIEWED = "REVIEWED"
    READY = "READY"
    PUBLISHED = "PUBLISHED"
    FAILED = "FAILED"


@dataclass
class Article:
    id: int | None
    topic: str
    title: str
    subtitle: str
    content: str
    tags: list[str]
    sources: list[dict[str, Any]]
    published_at: datetime | None
    medium_url: str | None
    status: ArticleStatus
    content_hash: str
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class Database:
    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or config.database_path
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS articles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    topic TEXT NOT NULL,
                    title TEXT NOT NULL,
                    subtitle TEXT,
                    content TEXT NOT NULL,
                    tags TEXT NOT NULL,
                    sources TEXT NOT NULL,
                    published_at TIMESTAMP,
                    medium_url TEXT,
                    status TEXT NOT NULL,
                    content_hash TEXT NOT NULL UNIQUE,
                    error_message TEXT,
                    created_at TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_status ON articles(status)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_published_at ON articles(published_at)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_topic ON articles(topic)
            """)
            conn.commit()

    def _hash_content(self, content: str) -> str:
        return hashlib.sha256(content.encode()).hexdigest()

    def save_article(self, article: Article) -> int:
        with self._get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO articles (topic, title, subtitle, content, tags, sources,
                                    published_at, medium_url, status, content_hash,
                                    error_message, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                article.topic,
                article.title,
                article.subtitle,
                article.content,
                json.dumps(article.tags),
                json.dumps(article.sources),
                article.published_at.isoformat() if article.published_at else None,
                article.medium_url,
                article.status.value,
                article.content_hash,
                article.error_message,
                article.created_at.isoformat(),
                article.updated_at.isoformat(),
            ))
            conn.commit()
            return cursor.lastrowid

    def update_article(self, article: Article):
        with self._get_connection() as conn:
            conn.execute("""
                UPDATE articles SET topic=?, title=?, subtitle=?, content=?, tags=?,
                                   sources=?, published_at=?, medium_url=?, status=?,
                                   content_hash=?, error_message=?, updated_at=?
                WHERE id=?
            """, (
                article.topic,
                article.title,
                article.subtitle,
                article.content,
                json.dumps(article.tags),
                json.dumps(article.sources),
                article.published_at.isoformat() if article.published_at else None,
                article.medium_url,
                article.status.value,
                article.content_hash,
                article.error_message,
                article.updated_at.isoformat(),
                article.id,
            ))
            conn.commit()

    def get_article_by_id(self, article_id: int) -> Article | None:
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM articles WHERE id=?", (article_id,)).fetchone()
            return self._row_to_article(row) if row else None

    def get_article_by_hash(self, content_hash: str) -> Article | None:
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM articles WHERE content_hash=?", (content_hash,)).fetchone()
            return self._row_to_article(row) if row else None

    def get_today_published(self) -> list[Article]:
        today = datetime.now(timezone.utc).date().isoformat()
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM articles
                WHERE status = ? AND date(published_at) = ?
            """, (ArticleStatus.PUBLISHED.value, today)).fetchall()
            return [self._row_to_article(row) for row in rows]

    def get_recent_articles(self, limit: int = 50) -> list[Article]:
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM articles
                ORDER BY created_at DESC
                LIMIT ?
            """, (limit,)).fetchall()
            return [self._row_to_article(row) for row in rows]

    def get_articles_by_status(self, status: ArticleStatus) -> list[Article]:
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM articles WHERE status = ? ORDER BY created_at DESC
            """, (status.value,)).fetchall()
            return [self._row_to_article(row) for row in rows]

    def check_similar_topic(self, topic: str, threshold: float = 0.8) -> bool:
        recent = self.get_recent_articles(100)
        topic_lower = topic.lower()
        for article in recent:
            if self._similarity(topic_lower, article.topic.lower()) > threshold:
                return True
        return False

    def check_similar_content(self, content: str, threshold: float = 0.7) -> bool:
        content_hash = self._hash_content(content)
        existing = self.get_article_by_hash(content_hash)
        if existing:
            return True
        recent = self.get_recent_articles(50)
        for article in recent:
            if self._similarity(content[:500], article.content[:500]) > threshold:
                return True
        return False

    def _similarity(self, a: str, b: str) -> float:
        words_a = set(a.split())
        words_b = set(b.split())
        if not words_a or not words_b:
            return 0.0
        intersection = words_a & words_b
        union = words_a | words_b
        return len(intersection) / len(union)

    def _row_to_article(self, row: sqlite3.Row) -> Article:
        return Article(
            id=row["id"],
            topic=row["topic"],
            title=row["title"],
            subtitle=row["subtitle"] or "",
            content=row["content"],
            tags=json.loads(row["tags"]),
            sources=json.loads(row["sources"]),
            published_at=datetime.fromisoformat(row["published_at"]) if row["published_at"] else None,
            medium_url=row["medium_url"],
            status=ArticleStatus(row["status"]),
            content_hash=row["content_hash"],
            error_message=row["error_message"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )


db = Database()