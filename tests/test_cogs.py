"""Tests for cogs using the configuration system."""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import SecretStr

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
        token=SecretStr("test_token_123_this_is_a_valid_discord_bot_token_1234567890"),
        render={"use_onlinetex": True, "disable_docker": False},
    )
    set_config(config)
    return config


@contextmanager
def mock_docker_render():
    """Context manager to mock Docker rendering infrastructure.

    Yields a tuple of (mock_file, mock_docker) where:
    - mock_file: Can be used to inspect what was written
    - mock_docker: The mocked Docker client (to inspect container.run calls)
    """
    with patch(
        "discordmanimator.cogs.render_codeblock.aiodocker.Docker"
    ) as mock_docker_class:
        mock_docker = AsyncMock()
        # Support async context manager protocol
        mock_docker.__aenter__ = AsyncMock(return_value=mock_docker)
        mock_docker.__aexit__ = AsyncMock(return_value=None)
        mock_docker_class.return_value = mock_docker

        # Create an async iterator for container.log()
        async def mock_log_iterator():
            return
            yield  # Make this a generator but yield nothing

        mock_container = AsyncMock()
        mock_container.log = MagicMock(return_value=mock_log_iterator())

        mock_docker.containers.run = AsyncMock(return_value=mock_container)
        mock_docker.close = AsyncMock()

        with patch("pathlib.Path.rglob") as mock_rglob:
            mock_path = MagicMock()
            mock_path.name = "scriptoutput.mp4"
            mock_rglob.return_value = [mock_path]

            with patch("builtins.open", create=True) as mock_open:
                mock_file = MagicMock()
                mock_open.return_value.__enter__.return_value = mock_file

                with patch("tempfile.TemporaryDirectory") as mock_tmpdir:
                    mock_tmpdir.return_value.__enter__.return_value = "/tmp/test"

                    yield mock_file, mock_docker


def create_simple_message():
    """Create a mock message with a simple Manim snippet."""
    mock_message = MagicMock()
    mock_message.content = """
```python
def construct(self):
    self.play(Create(Square()))
```
"""
    return mock_message


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
    async def test_docker_disabled(self):
        """Test that rendering fails gracefully when Docker is disabled."""
        # Create config with Docker disabled
        config = Config(
            token="test_token_123_this_is_a_valid_discord_bot_token_1234567890",
            render={"disable_docker": True},
        )
        set_config(config)

        mock_message = create_simple_message()

        result = await render_animation_snippet(mock_message)

        assert "Docker rendering is disabled" in result["content"]
        assert result["cli_flags"] == []

    @pytest.mark.asyncio
    async def test_uses_onlinetex_config(self, test_config):
        """Test that onlinetex config is respected."""
        mock_message = create_simple_message()

        with mock_docker_render() as (mock_file, _):
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
            render={"use_onlinetex": False, "disable_docker": False},
        )
        set_config(config)

        mock_message = create_simple_message()

        with mock_docker_render() as (mock_file, _):
            await render_animation_snippet(mock_message)

            # Verify the script was written without onlinetex import
            write_calls = mock_file.write.call_args_list
            if write_calls:
                written_content = write_calls[0][0][0]
                assert "from manim import *" in written_content
                assert "from manim_onlinetex import *" not in written_content

    @pytest.mark.asyncio
    async def test_uses_custom_docker_image(self):
        """Test that custom docker image config is used."""
        config = Config(
            token="test_token_123_this_is_a_valid_discord_bot_token_1234567890",
            render={"disable_docker": False, "docker_image": "custom/manim:test"},
        )
        set_config(config)

        mock_message = create_simple_message()

        with mock_docker_render() as (_, mock_docker):
            await render_animation_snippet(mock_message)

            # Check that the custom image was used
            call_args = mock_docker.containers.run.call_args
            assert call_args[1]["config"]["Image"] == "custom/manim:test"

    @pytest.mark.asyncio
    async def test_uses_custom_quality(self):
        """Test that custom quality config is used."""
        config = Config(
            token="test_token_123_this_is_a_valid_discord_bot_token_1234567890",
            render={"disable_docker": False, "render_quality": "h"},
        )
        set_config(config)

        mock_message = create_simple_message()

        with mock_docker_render() as (_, mock_docker):
            await render_animation_snippet(mock_message)

            # Check that the custom quality was used
            call_args = mock_docker.containers.run.call_args
            cmd = call_args[1]["config"]["Cmd"]
            assert "--quality=h" in cmd

    @pytest.mark.asyncio
    async def test_uses_custom_container_timeout(self):
        """Test that custom container timeout config is used."""
        config = Config(
            token="test_token_123_this_is_a_valid_discord_bot_token_1234567890",
            render={"disable_docker": False, "container_timeout": 180},
        )
        set_config(config)

        mock_message = create_simple_message()

        with mock_docker_render() as (_, mock_docker):
            await render_animation_snippet(mock_message)

            # Check that the custom timeout was used
            call_args = mock_docker.containers.run.call_args
            cmd = call_args[1]["config"]["Cmd"]
            # The timeout command should have "180" as its argument
            timeout_idx = cmd.index("timeout")
            assert cmd[timeout_idx + 1] == "180"

    @pytest.mark.asyncio
    async def test_no_output_file_error(self):
        """Test error handling when no output file is produced."""
        config = Config(
            token="test_token_123_this_is_a_valid_discord_bot_token_1234567890",
            render={"disable_docker": False},
        )
        set_config(config)

        mock_message = create_simple_message()

        # Mock Docker but return no output files
        with patch(
            "discordmanimator.cogs.render_codeblock.aiodocker.Docker"
        ) as mock_docker_class:
            mock_docker = AsyncMock()
            mock_docker.__aenter__ = AsyncMock(return_value=mock_docker)
            mock_docker.__aexit__ = AsyncMock(return_value=None)
            mock_docker_class.return_value = mock_docker

            async def mock_log_iterator():
                return
                yield

            mock_container = AsyncMock()
            mock_container.log = MagicMock(return_value=mock_log_iterator())
            mock_docker.containers.run = AsyncMock(return_value=mock_container)
            mock_docker.close = AsyncMock()

            # Mock rglob to return empty list (no output files)
            with patch("pathlib.Path.rglob") as mock_rglob:
                mock_rglob.return_value = []

                with patch("builtins.open", create=True):
                    with patch("tempfile.TemporaryDirectory") as mock_tmpdir:
                        mock_tmpdir.return_value.__enter__.return_value = "/tmp/test"

                        result = await render_animation_snippet(mock_message)

                        assert "No output file was produced" in result["content"]
                        assert "Check the error log" in result["content"]
                        assert result["cli_flags"] == []
                        assert "attachments" not in result

    @pytest.mark.asyncio
    async def test_multiple_output_files_error(self):
        """Test error handling when multiple output files are found."""
        config = Config(
            token="test_token_123_this_is_a_valid_discord_bot_token_1234567890",
            render={"disable_docker": False},
        )
        set_config(config)

        mock_message = create_simple_message()

        # Mock Docker but return multiple output files
        with patch(
            "discordmanimator.cogs.render_codeblock.aiodocker.Docker"
        ) as mock_docker_class:
            mock_docker = AsyncMock()
            mock_docker.__aenter__ = AsyncMock(return_value=mock_docker)
            mock_docker.__aexit__ = AsyncMock(return_value=None)
            mock_docker_class.return_value = mock_docker

            async def mock_log_iterator():
                return
                yield

            mock_container = AsyncMock()
            mock_container.log = MagicMock(return_value=mock_log_iterator())
            mock_docker.containers.run = AsyncMock(return_value=mock_container)
            mock_docker.close = AsyncMock()

            # Mock rglob to return multiple files
            with patch("pathlib.Path.rglob") as mock_rglob:
                mock_path1 = MagicMock()
                mock_path1.name = "scriptoutput.mp4"
                mock_path2 = MagicMock()
                mock_path2.name = "scriptoutput.gif"
                mock_path3 = MagicMock()
                mock_path3.name = "scriptoutput.png"
                mock_rglob.return_value = [mock_path1, mock_path2, mock_path3]

                with patch("builtins.open", create=True):
                    with patch("tempfile.TemporaryDirectory") as mock_tmpdir:
                        mock_tmpdir.return_value.__enter__.return_value = "/tmp/test"

                        result = await render_animation_snippet(mock_message)

                        assert "Multiple output files found (3)" in result["content"]
                        assert "scriptoutput.mp4" in result["content"]
                        assert "scriptoutput.gif" in result["content"]
                        assert "scriptoutput.png" in result["content"]
                        assert "Expected exactly one" in result["content"]
                        assert result["cli_flags"] == []
                        assert "attachments" not in result


class TestMemoryParsing:
    """Tests for memory string parsing helper."""

    def test_parse_memory_kilobytes(self):
        """Test parsing kilobyte memory strings."""
        from discordmanimator.cogs.render_codeblock import _parse_memory_string

        assert _parse_memory_string("512k") == 512 * 1024
        assert _parse_memory_string("1024k") == 1024 * 1024
        assert _parse_memory_string("1k") == 1024

    def test_parse_memory_megabytes(self):
        """Test parsing megabyte memory strings."""
        from discordmanimator.cogs.render_codeblock import _parse_memory_string

        assert _parse_memory_string("512m") == 512 * 1024 * 1024
        assert _parse_memory_string("1m") == 1024 * 1024
        assert _parse_memory_string("256m") == 256 * 1024 * 1024

    def test_parse_memory_gigabytes(self):
        """Test parsing gigabyte memory strings."""
        from discordmanimator.cogs.render_codeblock import _parse_memory_string

        assert _parse_memory_string("1g") == 1024 * 1024 * 1024
        assert _parse_memory_string("2g") == 2 * 1024 * 1024 * 1024

    def test_parse_memory_case_insensitive(self):
        """Test that parsing is case insensitive."""
        from discordmanimator.cogs.render_codeblock import _parse_memory_string

        assert _parse_memory_string("512K") == 512 * 1024
        assert _parse_memory_string("512M") == 512 * 1024 * 1024
        assert _parse_memory_string("1G") == 1024 * 1024 * 1024

    def test_parse_memory_invalid_format(self):
        """Test that invalid formats raise errors."""
        from discordmanimator.cogs.render_codeblock import _parse_memory_string

        with pytest.raises(ValueError):
            _parse_memory_string("512")  # No unit

        with pytest.raises(ValueError):
            _parse_memory_string("abc")  # Not a number

        with pytest.raises(ValueError):
            _parse_memory_string("512x")  # Invalid unit
