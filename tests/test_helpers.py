import pytest
from src.utils.helpers import count_words, truncate_text, sanitize_filename, extract_code_blocks, format_as_markdown


class TestHelpers:
    def test_count_words(self):
        assert count_words("Hello world") == 2
        assert count_words("") == 0
        assert count_words("   ") == 0
        assert count_words("One two three four five") == 5

    def test_truncate_text(self):
        assert truncate_text("Hello world", 20) == "Hello world"
        assert truncate_text("Hello world", 8) == "Hello..."
        assert truncate_text("Hello world", 5, ">>") == "He>>"

    def test_sanitize_filename(self):
        assert sanitize_filename("Hello World!") == "Hello World"
        assert sanitize_filename("Test@#$%^&*()") == "Test"
        assert sanitize_filename("Normal-File_Name.txt") == "Normal-File_Name.txt"

    def test_extract_code_blocks(self):
        text = "```python\nprint('hello')\n```"
        blocks = extract_code_blocks(text)
        assert len(blocks) == 1
        assert blocks[0] == ("python", "print('hello')")

        text = "```\ncode\n```\n```javascript\nconsole.log('hi')\n```"
        blocks = extract_code_blocks(text)
        assert len(blocks) == 2
        assert blocks[0] == ("", "code")
        assert blocks[1] == ("javascript", "console.log('hi')")

    def test_format_as_markdown(self):
        text = "## Heading\n\nParagraph\n\n```python\ncode\n```"
        formatted = format_as_markdown(text)
        assert "## Heading" in formatted
        assert "```python" in formatted
        assert "code" in formatted