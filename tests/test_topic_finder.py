import pytest
from unittest.mock import Mock, patch
from src.research.topic_finder import TopicFinder, TopicCandidate


class TestTopicFinder:
    @pytest.fixture
    def finder(self):
        with patch('src.research.topic_finder.config') as mock_config:
            mock_config.content_categories = ["AI", "Java", "AWS"]
            mock_config.llm_provider = "openai"
            mock_config.llm_api_key = "test-key"
            mock_config.llm_model = "gpt-4o"
            yield TopicFinder()

    def test_score_relevance(self, finder):
        assert finder._score_relevance("Spring Boot Guide", "Java") == 0.9
        assert finder._score_relevance("Random Topic", "Unknown") == 0.5

    def test_score_current_interest(self, finder):
        assert finder._score_current_interest("Building AI Applications with RAG") > 0.8
        assert finder._score_current_interest("Spring Boot 3 Virtual Threads") > 0.8
        assert finder._score_current_interest("Microservices Architecture") > 0.6
        assert finder._score_current_interest("Old Technology") == 0.5

    def test_score_developer_usefulness(self, finder):
        assert finder._score_developer_usefulness("How to Implement Caching") > 0.8
        assert finder._score_developer_usefulness("Best Practices for Testing") > 0.8
        assert finder._score_developer_usefulness("General Overview") == 0.6

    def test_score_longevity(self, finder):
        assert finder._score_longevity("Design Patterns for Microservices") > 0.8
        assert finder._score_longevity("Just Released New Framework") < 0.5
        assert finder._score_longevity("Regular Topic") == 0.6

    @patch('src.research.topic_finder.db')
    def test_check_similar_topic_skip(self, mock_db, finder):
        mock_db.check_similar_topic.return_value = True
        candidates = [{"topic": "Test Topic", "category": "AI", "reasoning": "test"}]
        scored = finder._score_candidates(candidates)
        assert len(scored) == 0


class TestTopicCandidate:
    def test_creation(self):
        candidate = TopicCandidate(
            topic="Test Topic",
            category="AI",
            score=0.85,
            reasoning="Good topic",
            search_potential=0.8,
            originality=0.9
        )
        assert candidate.topic == "Test Topic"
        assert candidate.score == 0.85