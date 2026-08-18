import pytest
import tempfile
import os
from datetime import datetime
from src.storage.database import Database, Article, ArticleStatus


@pytest.fixture
def temp_db():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    db = Database(db_path)
    yield db
    os.unlink(db_path)


def test_database_initialization(temp_db):
    assert temp_db is not None
    articles = temp_db.get_recent_articles()
    assert articles == []


def test_save_and_get_article(temp_db):
    article = Article(
        id=None,
        topic="Test Topic",
        title="Test Title",
        subtitle="Test Subtitle",
        content="Test content with enough words to pass validation",
        tags=["tag1", "tag2"],
        sources=[{"title": "Source", "url": "http://example.com"}],
        published_at=None,
        medium_url=None,
        status=ArticleStatus.TOPIC_SELECTED,
        content_hash="abc123",
        error_message=None,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )

    article_id = temp_db.save_article(article)
    assert article_id > 0

    retrieved = temp_db.get_article_by_id(article_id)
    assert retrieved is not None
    assert retrieved.topic == "Test Topic"
    assert retrieved.title == "Test Title"
    assert retrieved.tags == ["tag1", "tag2"]
    assert retrieved.status == ArticleStatus.TOPIC_SELECTED


def test_update_article(temp_db):
    article = Article(
        id=None,
        topic="Test Topic",
        title="Test Title",
        subtitle="Test Subtitle",
        content="Test content",
        tags=["tag1"],
        sources=[],
        published_at=None,
        medium_url=None,
        status=ArticleStatus.TOPIC_SELECTED,
        content_hash="abc123",
        error_message=None,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )

    article_id = temp_db.save_article(article)
    article.id = article_id
    article.status = ArticleStatus.PUBLISHED
    article.medium_url = "https://medium.com/@user/article"
    article.updated_at = datetime.now()

    temp_db.update_article(article)

    retrieved = temp_db.get_article_by_id(article_id)
    assert retrieved.status == ArticleStatus.PUBLISHED
    assert retrieved.medium_url == "https://medium.com/@user/article"


def test_content_hash_uniqueness(temp_db):
    article1 = Article(
        id=None, topic="Topic", title="Title", subtitle="", content="Same content",
        tags=[], sources=[], published_at=None, medium_url=None,
        status=ArticleStatus.TOPIC_SELECTED, content_hash="samehash",
        error_message=None, created_at=datetime.now(), updated_at=datetime.now()
    )
    article2 = Article(
        id=None, topic="Topic2", title="Title2", subtitle="", content="Same content",
        tags=[], sources=[], published_at=None, medium_url=None,
        status=ArticleStatus.TOPIC_SELECTED, content_hash="samehash",
        error_message=None, created_at=datetime.now(), updated_at=datetime.now()
    )

    temp_db.save_article(article1)
    with pytest.raises(Exception):
        temp_db.save_article(article2)


def test_get_today_published(temp_db):
    article = Article(
        id=None, topic="Topic", title="Title", subtitle="", content="Content",
        tags=[], sources=[], published_at=datetime.now(), medium_url="http://medium.com",
        status=ArticleStatus.PUBLISHED, content_hash="hash1",
        error_message=None, created_at=datetime.now(), updated_at=datetime.now()
    )
    temp_db.save_article(article)

    today = temp_db.get_today_published()
    assert len(today) == 1
    assert today[0].status == ArticleStatus.PUBLISHED


def test_check_similar_topic(temp_db):
    article = Article(
        id=None, topic="Spring Boot Virtual Threads", title="Title", subtitle="",
        content="Content", tags=[], sources=[], published_at=None, medium_url=None,
        status=ArticleStatus.PUBLISHED, content_hash="hash1",
        error_message=None, created_at=datetime.now(), updated_at=datetime.now()
    )
    temp_db.save_article(article)

    assert temp_db.check_similar_topic("Spring Boot Virtual Threads Guide") is True
    assert temp_db.check_similar_topic("Completely Different Topic") is False


def test_check_similar_content(temp_db):
    article = Article(
        id=None, topic="Topic", title="Title", subtitle="",
        content="This is a unique article about virtual threads in Java",
        tags=[], sources=[], published_at=None, medium_url=None,
        status=ArticleStatus.PUBLISHED, content_hash="hash1",
        error_message=None, created_at=datetime.now(), updated_at=datetime.now()
    )
    temp_db.save_article(article)

    assert temp_db.check_similar_content("This is a unique article about virtual threads in Java") is True
    assert temp_db.check_similar_content("Completely different content about something else") is False