import pytest
from unittest.mock import Mock, patch
from src.content.writer import ArticleWriter, ArticleDraft
from src.content.editor import ArticleEditor, ReviewResult
from src.content.seo import SEOOptimizer, SEOMetadata
from src.content.formatter import MediumFormatter, FormattedArticle


class TestArticleWriter:
    @pytest.fixture
    def writer(self):
        with patch('src.content.writer.config') as mock_config:
            mock_config.min_article_words = 1200
            mock_config.max_article_words = 2000
            mock_config.llm_provider = "openai"
            mock_config.llm_api_key = "test-key"
            mock_config.llm_model = "gpt-4o"
            yield ArticleWriter()

    def test_parse_json_response(self, writer):
        response = '{"title": "Test", "subtitle": "Sub", "content": "Content", "outline": "Outline"}'
        draft = writer._parse_response(response)
        assert draft.title == "Test"
        assert draft.subtitle == "Sub"
        assert draft.content == "Content"

    def test_parse_fallback_response(self, writer):
        response = "TITLE: Test Title\nSUBTITLE: Test Subtitle\nCONTENT:\nTest content here"
        draft = writer._parse_response(response)
        assert draft.title == "Test Title"
        assert draft.subtitle == "Test Subtitle"
        assert "Test content" in draft.content


class TestArticleEditor:
    @pytest.fixture
    def editor(self):
        with patch('src.content.editor.config') as mock_config:
            mock_config.enable_fact_check = True
            mock_config.llm_provider = "openai"
            mock_config.llm_api_key = "test-key"
            mock_config.llm_model = "gpt-4o"
            yield ArticleEditor()

    def test_parse_review_passed(self, editor):
        response = '{"passed": true, "score": 0.9, "issues": [], "suggestions": ["Add more examples"]}'
        result = editor._parse_response(response)
        assert result.passed is True
        assert result.score == 0.9
        assert len(result.issues) == 0

    def test_parse_review_failed(self, editor):
        response = '{"passed": false, "score": 0.4, "issues": [{"type": "critical", "description": "Wrong API"}], "suggestions": []}'
        result = editor._parse_response(response)
        assert result.passed is False
        assert len(result.issues) == 1
        assert result.issues[0]["type"] == "critical"


class TestSEOOptimizer:
    @pytest.fixture
    def seo(self):
        with patch('src.content.seo.config') as mock_config:
            mock_config.llm_provider = "openai"
            mock_config.llm_api_key = "test-key"
            mock_config.llm_model = "gpt-4o"
            yield SEOOptimizer()

    def test_parse_seo_response(self, seo):
        response = '''{
            "seo_title": "SEO Title",
            "medium_title": "Medium Title",
            "subtitle": "Subtitle",
            "tags": ["tag1", "tag2", "tag3", "tag4", "tag5"],
            "canonical_topic": "Technology",
            "meta_description": "Description"
        }'''
        result = seo._parse_response(response)
        assert result.seo_title == "SEO Title"
        assert result.medium_title == "Medium Title"
        assert len(result.tags) == 5
        assert result.canonical_topic == "Technology"


class TestMediumFormatter:
    @pytest.fixture
    def formatter(self):
        yield MediumFormatter()

    def test_normalize_headings(self, formatter):
        content = "# H1\n## H2\n### H3\nNormal text"
        result = formatter._normalize_headings(content)
        assert "## H1" in result
        assert "## H2" in result
        assert "### H3" in result

    def test_format_code_blocks(self, formatter):
        content = "```python\nprint('hello')\n```"
        result = formatter._format_code_blocks(content)
        assert "```python" in result
        assert "print('hello')" in result

    def test_format_lists(self, formatter):
        content = "- Item 1\n* Item 2\n1. Numbered"
        result = formatter._format_lists(content)
        assert "- Item 1" in result
        assert "- Item 2" in result
        assert "1. Numbered" in result

    def test_clean_up(self, formatter):
        content = "Line 1\n\n\n\nLine 2\n\n\nLine 3"
        result = formatter._clean_up(content)
        assert result.count("\n\n") <= 2

    def test_full_format(self, formatter):
        draft = ArticleDraft(
            title="Test Title",
            subtitle="Test Subtitle",
            content="# Introduction\n\n## Section\n\n```python\ncode\n```\n\n- Item 1\n- Item 2",
            word_count=100,
            outline=""
        )
        seo = SEOMetadata(
            seo_title="SEO Title",
            medium_title="Medium Title",
            subtitle="SEO Subtitle",
            tags=["tag1", "tag2", "tag3"],
            canonical_topic="Technology",
            meta_description="Description"
        )
        formatted = formatter.format(draft, seo)
        assert formatted.title == "Medium Title"
        assert formatted.subtitle == "SEO Subtitle"
        assert "## Introduction" in formatted.content
        assert "```python" in formatted.content
        assert len(formatted.tags) == 3