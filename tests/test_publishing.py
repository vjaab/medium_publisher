import pytest
import time
from unittest.mock import Mock, patch
from src.utils.helpers import retry_with_backoff
from src.publishing.medium import MediumPublisher, MediumPublisherAdapter, PublishResult


class TestRetryLogic:
    def test_retry_success_first_attempt(self):
        call_count = 0

        @retry_with_backoff(max_attempts=3, base_delay=0.01)
        def succeed():
            nonlocal call_count
            call_count += 1
            return "success"

        result = succeed()
        assert result == "success"
        assert call_count == 1

    def test_retry_success_after_failures(self):
        call_count = 0

        @retry_with_backoff(max_attempts=3, base_delay=0.01, exceptions=(ValueError,))
        def fail_twice():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Temporary error")
            return "success"

        result = fail_twice()
        assert result == "success"
        assert call_count == 3

    def test_retry_exhausted(self):
        call_count = 0

        @retry_with_backoff(max_attempts=3, base_delay=0.01, exceptions=(ValueError,))
        def always_fail():
            nonlocal call_count
            call_count += 1
            raise ValueError("Permanent error")

        with pytest.raises(ValueError, match="Permanent error"):
            always_fail()
        assert call_count == 3

    def test_retry_wrong_exception(self):
        call_count = 0

        @retry_with_backoff(max_attempts=3, base_delay=0.01, exceptions=(ValueError,))
        def wrong_exception():
            nonlocal call_count
            call_count += 1
            raise TypeError("Wrong exception type")

        with pytest.raises(TypeError):
            wrong_exception()
        assert call_count == 1


class TestMediumPublisher:
    @pytest.fixture
    def publisher(self):
        with patch('src.publishing.medium.config') as mock_config:
            mock_config.medium_token = "test-token"
            mock_config.medium_publication_id = None
            yield MediumPublisher(token="test-token")

    def test_init_without_token(self):
        with pytest.raises(ValueError, match="Medium token is required"):
            MediumPublisher(token=None)

    def test_get_headers(self, publisher):
        headers = publisher._get_headers()
        assert headers["Authorization"] == "Bearer test-token"
        assert headers["Content-Type"] == "application/json"

    def test_convert_to_medium_format(self, publisher):
        article = FormattedArticle(
            title="Test Title",
            subtitle="Test Subtitle",
            content="# Heading\n\nContent with **bold**",
            tags=["tag1", "tag2"]
        )
        payload = publisher._convert_to_medium_format(article)
        assert payload["title"] == "Test Title"
        assert payload["contentFormat"] == "markdown"
        assert payload["tags"] == ["tag1", "tag2"]
        assert payload["publishStatus"] == "draft"


class TestMediumPublisherAdapter:
    @pytest.fixture
    def adapter(self):
        with patch('src.publishing.medium.MediumPublisher') as mock_publisher_class:
            mock_publisher = Mock()
            mock_publisher_class.return_value = mock_publisher
            adapter = MediumPublisherAdapter()
            adapter.publisher = mock_publisher
            yield adapter

    def test_get_limitations(self, adapter):
        limitations = adapter.get_limitations()
        assert len(limitations) == 5
        assert "drafts" in limitations[0].lower()
        assert "public" in limitations[1].lower()

    def test_publish_creates_draft(self, adapter):
        mock_result = PublishResult(success=True, url="https://medium.com/@user/draft", article_id="123")
        adapter.publisher.publish.return_value = mock_result

        article = FormattedArticle(
            title="Test", subtitle="Sub", content="Content", tags=["tag"]
        )
        result = adapter.publish(article)

        assert result.success is True
        assert result.url == "https://medium.com/@user/draft"
        adapter.publisher.publish.assert_called_once_with(article)