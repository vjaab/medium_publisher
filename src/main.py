"""Medium Auto Publisher - Automated daily publishing pipeline for Medium articles."""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from src.config import config
from src.content.editor import ArticleEditor
from src.content.formatter import MediumFormatter
from src.content.seo import SEOOptimizer
from src.content.writer import ArticleWriter
from src.publishing.medium import MediumPublisherAdapter
from src.research.topic_finder import TopicFinder
from src.research.web_researcher import WebResearcher
from src.storage.database import Article, ArticleStatus, db
from src.utils.helpers import count_words
from src.utils.logger import get_logger

logger = get_logger(__name__)

NOW = datetime.now(timezone.utc)


class Pipeline:
    def __init__(self, dry_run: bool = False, manual_topic: str | None = None):
        self.dry_run = dry_run or config.dry_run
        self.manual_topic = manual_topic
        self.topic_finder = TopicFinder()
        self.researcher = WebResearcher()
        self.writer = ArticleWriter()
        self.editor = ArticleEditor()
        self.seo = SEOOptimizer()
        self.formatter = MediumFormatter()
        self.publisher = MediumPublisherAdapter() if not self.dry_run else None
        self.article: Article | None = None

    def run(self) -> bool:
        logger.info("=" * 60)
        logger.info("Pipeline started")
        logger.info(f"Mode: {'DRY RUN' if self.dry_run else 'LIVE'}")
        logger.info("=" * 60)

        try:
            if not self._check_idempotency():
                return True

            self._select_topic()
            self._research()
            self._write_article()
            self._review()
            self._optimize_seo()
            self._format()
            self._check_duplicates()
            self._publish()
            self._save_metadata()
            self._generate_report()

            logger.info("Pipeline completed successfully")
            return True

        except Exception as e:  # noqa: BLE001
            logger.error(f"Pipeline failed: {e}")
            if self.article:
                self.article.status = ArticleStatus.FAILED
                self.article.error_message = str(e)
                self.article.updated_at = datetime.now(timezone.utc)
                db.update_article(self.article)
            return False

    def _check_idempotency(self) -> bool:
        today_published = db.get_today_published()
        if today_published and not self.manual_topic:
            logger.info(f"Today's article already published: {today_published[0].title}")
            logger.info("Exiting successfully (idempotency check)")
            return False
        return True

    def _select_topic(self):
        logger.info("Finding topics...")
        candidates = self.topic_finder.generate_topics(
            count=10,
            manual_topic=self.manual_topic
        )

        if not candidates:
            raise ValueError("No suitable topics found")

        selected = candidates[0]
        logger.info(f"Selected topic: {selected.topic} (score: {selected.score:.2f})")
        logger.info(f"Reasoning: {selected.reasoning}")

        self.article = Article(
            id=None,
            topic=selected.topic,
            title="",
            subtitle="",
            content="",
            tags=[],
            sources=[],
            published_at=None,
            medium_url=None,
            status=ArticleStatus.TOPIC_SELECTED,
            content_hash="",
            error_message=None,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        db.save_article(self.article)

    def _research(self):
        logger.info(f"Researching topic: {self.article.topic}")
        self.research_result = self.researcher.research(self.article.topic)

        self.article.sources = self.research_result.sources
        self.article.status = ArticleStatus.RESEARCHED
        self.article.updated_at = datetime.now(timezone.utc)
        db.update_article(self.article)
        logger.info(f"Research completed: {len(self.research_result.key_points)} key points, {len(self.research_result.sources)} sources")

    def _write_article(self):
        logger.info("Generating article...")
        draft = self.writer.write(self.article.topic, self.research_result)

        if draft.word_count < config.min_article_words * 0.5:
            raise ValueError(f"Article too short: {draft.word_count} words (min: {config.min_article_words})")

        self.article.title = draft.title
        self.article.subtitle = draft.subtitle
        self.article.content = draft.content
        self.article.status = ArticleStatus.GENERATED
        self.article.updated_at = datetime.now(timezone.utc)
        db.update_article(self.article)
        logger.info(f"Article generated: {draft.word_count} words")

    def _review(self):
        logger.info("Running editorial review...")
        review = self.editor.review(
            self.writer.write(self.article.topic, self.research_result),
            self.research_result
        )

        if not review.passed:
            critical_issues = [i for i in review.issues if i.get("type") == "critical"]
            if critical_issues:
                raise ValueError(f"Critical issues found: {critical_issues}")

            logger.warning(f"Review issues (non-blocking): {review.issues}")
            logger.info(f"Suggestions: {review.suggestions}")

        self.article.status = ArticleStatus.REVIEWED
        self.article.updated_at = datetime.now(timezone.utc)
        db.update_article(self.article)
        logger.info(f"Review passed (score: {review.score:.2f})")

    def _optimize_seo(self):
        logger.info("Optimizing SEO...")
        draft = self.writer.write(self.article.topic, self.research_result)
        self.seo_result = self.seo.optimize(draft)
        logger.info(f"SEO title: {self.seo_result.medium_title}")
        logger.info(f"Tags: {self.seo_result.tags}")

    def _format(self):
        logger.info("Formatting for Medium...")
        draft = self.writer.write(self.article.topic, self.research_result)
        self.formatted = self.formatter.format(draft, self.seo_result)

        self.article.title = self.formatted.title
        self.article.subtitle = self.formatted.subtitle
        self.article.content = self.formatted.content
        self.article.tags = self.formatted.tags
        self.article.content_hash = db._hash_content(self.formatted.content)
        self.article.status = ArticleStatus.READY
        self.article.updated_at = datetime.now(timezone.utc)
        db.update_article(self.article)
        logger.info("Formatting completed")

    def _check_duplicates(self):
        logger.info("Checking for duplicates...")
        if config.enable_duplicate_check:
            if db.check_similar_topic(self.article.topic):
                raise ValueError(f"Similar topic already published: {self.article.topic}")

            if db.check_similar_content(self.article.content):
                raise ValueError("Similar content already published")

        logger.info("Duplicate check passed")

    def _publish(self):
        if self.dry_run:
            logger.info("DRY RUN: Skipping actual publication")
            self._save_dry_run_output()
            return

        logger.info("Publishing to Medium...")
        result = self.publisher.publish(self.formatted)

        if not result.success:
            raise RuntimeError(f"Publishing failed: {result.error}")

        self.article.medium_url = result.url
        self.article.published_at = datetime.now(timezone.utc)
        self.article.status = ArticleStatus.PUBLISHED
        self.article.updated_at = datetime.now(timezone.utc)
        logger.info(f"Published successfully: {result.url}")

    def _save_dry_run_output(self):
        output_dir = Path("output")
        output_dir.mkdir(exist_ok=True)

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"article_{timestamp}_{sanitize_filename(self.article.topic)}.md"
        filepath = output_dir / filename

        content = f"""# {self.formatted.title}

*{self.formatted.subtitle}*

**Tags:** {", ".join(self.formatted.tags)}

---

{self.formatted.content}

---

**Sources:**
"""
        for source in self.article.sources:
            content += f"- [{source.get('title', 'Source')}]({source.get('url', '')})\n"

        filepath.write_text(content)
        logger.info(f"Dry run output saved to: {filepath}")

    def _save_metadata(self):
        db.update_article(self.article)

    def _generate_report(self):
        report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "topic": self.article.topic,
            "title": self.article.title,
            "subtitle": self.article.subtitle,
            "word_count": count_words(self.article.content),
            "tags": self.article.tags,
            "status": self.article.status.value,
            "medium_url": self.article.medium_url,
            "sources_count": len(self.article.sources),
            "dry_run": self.dry_run
        }

        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        report_file = log_dir / f"report_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
        report_file.write_text(json.dumps(report, indent=2))
        logger.info(f"Execution report saved: {report_file}")


def sanitize_filename(text: str) -> str:
    return "".join(c for c in text if c.isalnum() or c in (" ", "-", "_")).rstrip()[:50]


def main():
    parser = argparse.ArgumentParser(description="Medium Auto Publisher")
    parser.add_argument("--dry-run", action="store_true", help="Run pipeline without publishing")
    parser.add_argument("--publish", action="store_true", help="Force publish mode (override dry-run)")
    parser.add_argument("--topic", type=str, help="Manual topic to write about")
    parser.add_argument("--config-check", action="store_true", help="Validate configuration and exit")

    args = parser.parse_args()

    if args.config_check:
        errors = config.validate()
        if errors:
            print("Configuration errors:")
            for e in errors:
                print(f"  - {e}")
            sys.exit(1)
        print("Configuration valid")
        sys.exit(0)

    dry_run = args.dry_run or (not args.publish and config.dry_run)
    manual_topic = args.topic

    pipeline = Pipeline(dry_run=dry_run, manual_topic=manual_topic)
    success = pipeline.run()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()