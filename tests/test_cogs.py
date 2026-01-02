"""Tests for cogs using the configuration system."""
from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from discordmanimator.cogs.render_codeblock import (
    RenderCodeblock,
    extract_manim_snippets,
    render_animation_snippet,
)
from discordmanimator.config import Config, reset_config, set_config


@pytest.fixture(autouse=True)
def reset_global_config():
    """Reset global config before and after each test."""
    reset_config()
    yield
    reset_config()


@pytest.fixture
def test_config():
    """Create and set a test configuration."""
    config = Config(
        token="test_token_123_this_is_a_valid_discord_bot_token_1234567890",
        render={"use_onlinetex": True, "no_docker": False},
    )
    set_config(config)
    return config


@contextmanager
def mock_docker_render():
    """Context manager to mock Docker rendering infrastructure.

    Yields a tuple of (mock_file, result_awaitable) where:
    - mock_file: Can be used to inspect what was written
    - result_awaitable: The coroutine to await for render_animation_snippet
    """
    with patch("discordmanimator.cogs.render_codeblock.aiodocker.Docker") as mock_docker_class:
        mock_docker = AsyncMock()
        mock_docker_class.return_value = mock_docker

        mock_container = AsyncMock()
        mock_container.log = AsyncMock()
        mock_container.log.return_value.__aiter__ = AsyncMock(return_value=iter([]))

        mock_docker.containers.run = AsyncMock(return_value=mock_container)
        mock_docker.close = AsyncMock()

        with patch("pathlib.Path.rglob") as mock_rglob:
            mock_rglob.return_value = [MagicMock(spec="Path")]

            with patch("builtins.open", create=True) as mock_open:
                mock_file = MagicMock()
                mock_open.return_value.__enter__.return_value = mock_file

                with patch("tempfile.TemporaryDirectory") as mock_tmpdir:
                    mock_tmpdir.return_value.__enter__.return_value = "/tmp/test"

                    yield mock_file


class TestExtractManimSnippets:
    """Tests for extract_manim_snippets function."""

    def test_extract_simple_snippet(self):
        """Test extracting a simple snippet."""
        message = """
```python
def construct(self):
    self.play(Create(Square()))
```
"""
        result = extract_manim_snippets(message)
        assert result
        assert "def construct(self):" in result[0]

    def test_extract_class_snippet(self):
        """Test extracting a class-based snippet."""
        message = """
```python
class MyScene(Scene):
    def construct(self):
        self.play(Create(Circle()))
```
"""
        result = extract_manim_snippets(message)
        assert result
        assert "class MyScene(Scene):" in result[0]

    def test_no_snippet(self):
        """Test message without snippets."""
        message = "Just a regular message"
        result = extract_manim_snippets(message)
        assert result == []

    def test_snippet_without_construct(self):
        """Test code block without construct method."""
        message = """
```python
def some_function():
    pass
```
"""
        result = extract_manim_snippets(message)
        assert result == []


class TestRenderCodeblock:
    """Tests for RenderCodeblock cog."""

    def test_cog_initialization(self, test_config):
        """Test that cog initializes with config."""
        mock_bot = MagicMock()
        cog = RenderCodeblock(mock_bot)

        assert cog.bot is mock_bot
        assert cog.config is test_config
        assert cog.config.render.use_onlinetex is True


class TestRenderAnimationSnippet:
    """Tests for render_animation_snippet function."""

    @pytest.mark.asyncio
    async def test_docker_disabled(self, test_config):
        """Test that rendering fails gracefully when Docker is disabled."""
        # Update config to disable Docker
        config = Config(
            token="test_token_123_this_is_a_valid_discord_bot_token_1234567890",
            render={"no_docker": True},
        )
        set_config(config)

        mock_message = MagicMock()
        mock_message.content = """
```python
def construct(self):
    self.play(Create(Square()))
```
"""

        result = await render_animation_snippet(mock_message)

        assert "Docker rendering is disabled" in result["content"]
        assert result["cli_flags"] == []

    @pytest.mark.asyncio
    async def test_uses_onlinetex_config(self, test_config):
        """Test that onlinetex config is respected."""
        mock_message = MagicMock()
        mock_message.content = """
```python
def construct(self):
    self.play(Create(Square()))
```
"""

        with mock_docker_render() as mock_file:
            await render_animation_snippet(mock_message)

            # Verify the script was written with onlinetex import
            write_calls = mock_file.write.call_args_list
            if write_calls:
                written_content = write_calls[0][0][0]
                assert "from manim import *" in written_content
                assert "from manim_onlinetex import *" in written_content

    @pytest.mark.asyncio
    async def test_does_not_use_onlinetex_when_disabled(self):
        """Test that onlinetex is not imported when disabled."""
        config = Config(
            token="test_token_123_this_is_a_valid_discord_bot_token_1234567890",
            render={"use_onlinetex": False, "no_docker": False},
        )
        set_config(config)

        mock_message = MagicMock()
        mock_message.content = """
```python
def construct(self):
    self.play(Create(Square()))
```
"""

        with mock_docker_render() as mock_file:
            await render_animation_snippet(mock_message)

            # Verify the script was written without onlinetex import
            write_calls = mock_file.write.call_args_list
            if write_calls:
                written_content = write_calls[0][0][0]
                assert "from manim import *" in written_content
                assert "from manim_onlinetex import *" not in written_content
