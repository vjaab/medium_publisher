import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from src.main import Pipeline
from src.storage.database import Article, ArticleStatus
from src.content.writer import ArticleDraft
from src.research.web_researcher import ResearchResult
from src.content.seo import SEOMetadata
from src.content.formatter import FormattedArticle
from src.publishing.medium import PublishResult


class TestPipeline:
    @pytest.fixture
    def mock_config(self):
        with patch('src.main.config') as mock:
            mock.dry_run = True
            mock.min_article_words = 100
            mock.max_article_words = 5000
            mock.enable_research = True
            mock.enable_fact_check = True
            mock.enable_duplicate_check = True
            yield mock

    @pytest.fixture
    def mock_db(self):
        with patch('src.main.db') as mock:
            mock.get_today_published.return_value = []
            mock.check_similar_topic.return_value = False
            mock.check_similar_content.return_value = False
            mock._hash_content.return_value = "testhash"
            yield mock

    @pytest.fixture
    def mock_components(self):
        with patch('src.main.TopicFinder') as mock_finder, \
             patch('src.main.WebResearcher') as mock_researcher, \
             patch('src.main.ArticleWriter') as mock_writer, \
             patch('src.main.ArticleEditor') as mock_editor, \
             patch('src.main.SEOOptimizer') as mock_seo, \
             patch('src.main.MediumFormatter') as mock_formatter:

            # TopicFinder
            mock_finder_instance = Mock()
            mock_finder_instance.generate_topics.return_value = [
                Mock(topic="Test Topic", category="AI", score=0.9, reasoning="Good", search_potential=0.8, originality=0.9)
            ]
            mock_finder.return_value = mock_finder_instance

            # WebResearcher
            mock_researcher_instance = Mock()
            mock_researcher_instance.research.return_value = ResearchResult(
                topic="Test Topic",
                summary="Summary",
                key_points=["Point 1", "Point 2"],
                facts=[{"statement": "Fact 1"}],
                sources=[{"title": "Source", "url": "http://example.com"}]
            )
            mock_researcher.return_value = mock_researcher_instance

            # ArticleWriter
            mock_writer_instance = Mock()
            mock_writer_instance.write.return_value = ArticleDraft(
                title="Test Title",
                subtitle="Test Subtitle",
                content="Test content " * 50,
                word_count=200,
                outline="Outline"
            )
            mock_writer.return_value = mock_writer_instance

            # ArticleEditor
            mock_editor_instance = Mock()
            mock_editor_instance.review.return_value = Mock(
                passed=True,
                issues=[],
                suggestions=[],
                score=0.9
            )
            mock_editor.return_value = mock_editor_instance

            # SEOOptimizer
            mock_seo_instance = Mock()
            mock_seo_instance.optimize.return_value = SEOMetadata(
                seo_title="SEO Title",
                medium_title="Medium Title",
                subtitle="SEO Subtitle",
                tags=["tag1", "tag2", "tag3", "tag4", "tag5"],
                canonical_topic="Technology",
                meta_description="Description"
            )
            mock_seo.return_value = mock_seo_instance

            # MediumFormatter
            mock_formatter_instance = Mock()
            mock_formatter_instance.format.return_value = FormattedArticle(
                title="Medium Title",
                subtitle="SEO Subtitle",
                content="Formatted content",
                tags=["tag1", "tag2"]
            )
            mock_formatter.return_value = mock_formatter_instance

            yield {
                'finder': mock_finder_instance,
                'researcher': mock_researcher_instance,
                'writer': mock_writer_instance,
                'editor': mock_editor_instance,
                'seo': mock_seo_instance,
                'formatter': mock_formatter_instance
            }

    def test_pipeline_dry_run(self, mock_config, mock_db, mock_components):
        pipeline = Pipeline(dry_run=True)
        result = pipeline.run()

        assert result is True
        assert pipeline.article is not None
        assert pipeline.article.status == ArticleStatus.READY
        mock_db.save_article.assert_called()
        mock_db.update_article.assert_called()

    def test_pipeline_idempotency(self, mock_config, mock_db, mock_components):
        mock_db.get_today_published.return_value = [
            Article(
                id=1, topic="Existing", title="Existing", subtitle="", content="",
                tags=[], sources=[], published_at=datetime.now(), medium_url="",
                status=ArticleStatus.PUBLISHED, content_hash="", error_message=None,
                created_at=datetime.now(), updated_at=datetime.now()
            )
        ]

        pipeline = Pipeline(dry_run=True)
        result = pipeline.run()

        assert result is True
        mock_components['finder'].generate_topics.assert_not_called()

    def test_pipeline_duplicate_topic_rejected(self, mock_config, mock_db, mock_components):
        mock_db.check_similar_topic.return_value = True

        pipeline = Pipeline(dry_run=True)
        result = pipeline.run()

        assert result is False
        assert pipeline.article.status == ArticleStatus.FAILED

    def test_pipeline_editor_rejects_critical(self, mock_config, mock_db, mock_components):
        mock_components['editor'].review.return_value = Mock(
            passed=False,
            issues=[{"type": "critical", "description": "Wrong API"}],
            suggestions=[],
            score=0.3
        )

        pipeline = Pipeline(dry_run=True)
        result = pipeline.run()

        assert result is False
        assert pipeline.article.status == ArticleStatus.FAILED

    def test_pipeline_short_article_rejected(self, mock_config, mock_db, mock_components):
        mock_components['writer'].write.return_value = ArticleDraft(
            title="Test", subtitle="Sub", content="Short", word_count=10, outline=""
        )

        pipeline = Pipeline(dry_run=True)
        result = pipeline.run()

        assert result is False
        assert pipeline.article.status == ArticleStatus.FAILED