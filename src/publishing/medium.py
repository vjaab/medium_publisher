
import requests

from src.config import config
from src.content.formatter import FormattedArticle
from src.publishing.publisher import Publisher, PublishResult
from src.utils.helpers import retry_with_backoff
from src.utils.logger import get_logger

logger = get_logger(__name__)


class MediumPublisher(Publisher):
    BASE_URL = "https://api.medium.com/v1"

    def __init__(self, token: str | None = None, publication_id: str | None = None):
        self.token = token or config.medium_token
        self.publication_id = publication_id or config.medium_publication_id
        self._user_id = None

        if not self.token:
            raise ValueError("Medium token is required. Set MEDIUM_TOKEN environment variable.")

    def get_user_id(self) -> str:
        if self._user_id:
            return self._user_id

        headers = self._get_headers()
        response = requests.get(f"{self.BASE_URL}/me", headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        self._user_id = data["data"]["id"]
        return self._user_id

    def _get_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _convert_to_medium_format(self, article: FormattedArticle) -> dict:
        content = article.content

        content = content.replace("\n## ", "\n\n## ")
        content = content.replace("\n### ", "\n\n### ")

        return {
            "title": article.title,
            "contentFormat": "markdown",
            "content": content,
            "tags": article.tags[:5],
            "publishStatus": "draft",
        }

    @retry_with_backoff(max_attempts=3, base_delay=2.0, exceptions=(requests.RequestException,))
    def publish(self, article: FormattedArticle) -> PublishResult:
        try:
            user_id = self.get_user_id()
            payload = self._convert_to_medium_format(article)

            if self.publication_id:
                url = f"{self.BASE_URL}/publications/{self.publication_id}/posts"
            else:
                url = f"{self.BASE_URL}/users/{user_id}/posts"

            logger.info(f"Publishing to Medium: {article.title}")
            response = requests.post(url, headers=self._get_headers(), json=payload, timeout=60)

            if response.status_code == 401:
                return PublishResult(
                    success=False,
                    error="Authentication failed. Check MEDIUM_TOKEN."
                )
            elif response.status_code == 403:
                return PublishResult(
                    success=False,
                    error="Permission denied. Check token scopes and publication access."
                )
            elif response.status_code == 429:
                return PublishResult(
                    success=False,
                    error="Rate limited. Please wait before retrying."
                )

            response.raise_for_status()
            data = response.json()

            post_data = data.get("data", {})
            post_url = post_data.get("url")
            post_id = post_data.get("id")

            logger.info(f"Article published successfully: {post_url}")
            return PublishResult(
                success=True,
                url=post_url,
                article_id=post_id
            )

        except requests.RequestException as e:
            logger.error(f"Medium API request failed: {e}")
            return PublishResult(success=False, error=f"Network error: {e!s}")
        except (ValueError, KeyError, TypeError) as e:
            logger.error(f"Publishing failed: {e}")
            return PublishResult(success=False, error=str(e))

    def update_post(self, post_id: str, article: FormattedArticle) -> PublishResult:
        try:
            user_id = self.get_user_id()
            payload = self._convert_to_medium_format(article)
            payload["publishStatus"] = "public"

            url = f"{self.BASE_URL}/users/{user_id}/posts/{post_id}"
            response = requests.put(url, headers=self._get_headers(), json=payload, timeout=60)
            response.raise_for_status()

            data = response.json()
            post_data = data.get("data", {})
            return PublishResult(
                success=True,
                url=post_data.get("url"),
                article_id=post_data.get("id")
            )
        except (requests.RequestException, ValueError, KeyError, TypeError) as e:
            logger.error(f"Failed to update post: {e}")
            return PublishResult(success=False, error=str(e))

    def get_publications(self) -> list:
        try:
            user_id = self.get_user_id()
            response = requests.get(
                f"{self.BASE_URL}/users/{user_id}/publications",
                headers=self._get_headers(),
                timeout=30
            )
            response.raise_for_status()
            return response.json().get("data", [])
        except (requests.RequestException, ValueError, KeyError, TypeError) as e:
            logger.error(f"Failed to get publications: {e}")
            return []


class MediumPublisherAdapter:
    """
    Adapter for Medium publishing with fallback strategies.
    Note: Medium's official API has limitations:
    - Only supports drafting posts (publishStatus: draft)
    - Cannot directly publish to 'public' via API
    - No image upload support
    - No canonical URL setting
    
    Workarounds:
    1. Publish as draft, then manually publish via Medium UI
    2. Use unofficial selenium/playwright automation (not implemented here)
    3. Use Medium's RSS/import features
    
    This adapter implements the official API approach with clear documentation
    of limitations. Replace with alternative implementation if needed.
    """

    def __init__(self, token: str | None = None, publication_id: str | None = None):
        self.publisher = MediumPublisher(token, publication_id)
        self.limitations = [
            "Medium API only supports creating drafts (publishStatus: draft)",
            "Cannot programmatically publish to 'public' status",
            "No image upload via API",
            "No canonical URL support",
            "Publication posting requires publication ID and permissions"
        ]

    def publish(self, article: FormattedArticle) -> PublishResult:
        result = self.publisher.publish(article)
        if result.success:
            logger.warning(
                "Article created as DRAFT on Medium. "
                "Manual action required: Go to Medium.com, open draft, click Publish."
            )
        return result

    def get_limitations(self) -> list:
        return self.limitations