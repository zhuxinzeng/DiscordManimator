"""Tests for the main entry point."""

import sys
from unittest.mock import MagicMock, patch

import pytest

from discordmanimator.__main__ import main
from discordmanimator.config import reset_config


@pytest.fixture(autouse=True)
def reset_global_config():
    """Reset global config before and after each test."""
    reset_config()
    yield
    reset_config()


class TestMainEntryPoint:
    """Tests for the main() function."""

    def test_generate_example(self, tmp_path, monkeypatch):
        """Test generating an example config file."""
        config_file = tmp_path / "test_config.toml"

        # Mock sys.argv
        test_args = ["discordmanimator", str(config_file), "--generate-example"]
        monkeypatch.setattr(sys, "argv", test_args)

        # Run main
        main()

        # Verify file was created
        assert config_file.exists()
        content = config_file.read_text()
        assert "paste_your_bot_token_here" in content
        assert "[bot]" in content
        assert "[render]" in content

    def test_validate_only_valid_config(self, tmp_path, monkeypatch, capsys):
        """Test --validate-only with a valid config."""
        config_file = tmp_path / "config.toml"
        config_file.write_text(
            """
token = "valid_token_1234567890_abcdefghijklmnopqrstuvwxyz123456"

[bot]
prefix = "!"

[render]
use_onlinetex = false
"""
        )

        test_args = ["discordmanimator", str(config_file), "--validate-only"]
        monkeypatch.setattr(sys, "argv", test_args)

        main()

        captured = capsys.readouterr()
        assert "✓ Configuration loaded" in captured.out
        assert "✓ Configuration is valid!" in captured.out

    def test_validate_only_invalid_config(self, tmp_path, monkeypatch, capsys):
        """Test --validate-only with an invalid config."""
        config_file = tmp_path / "config.toml"
        config_file.write_text(
            """
token = "paste_your_bot_token_here"
"""
        )

        test_args = ["discordmanimator", str(config_file), "--validate-only"]
        monkeypatch.setattr(sys, "argv", test_args)

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 1

        captured = capsys.readouterr()
        assert "✗ Error: Invalid configuration" in captured.err
        assert "Invalid token" in captured.err

    def test_missing_config_file(self, tmp_path, monkeypatch, capsys):
        """Test with a missing config file."""
        config_file = tmp_path / "nonexistent.toml"

        test_args = ["discordmanimator", str(config_file)]
        monkeypatch.setattr(sys, "argv", test_args)

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 1

        captured = capsys.readouterr()
        assert "✗ Error: Config file not found" in captured.err
        assert "--generate-example" in captured.err

    def test_config_with_extra_fields(self, tmp_path, monkeypatch, capsys):
        """Test config with unknown fields."""
        config_file = tmp_path / "config.toml"
        config_file.write_text(
            """
token = "valid_token_1234567890_abcdefghijklmnopqrstuvwxyz123456"
unknown_field = "value"
"""
        )

        test_args = ["discordmanimator", str(config_file), "--validate-only"]
        monkeypatch.setattr(sys, "argv", test_args)

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 1

        captured = capsys.readouterr()
        assert "✗ Error: Invalid configuration" in captured.err
        assert "extra" in captured.err.lower()

    @patch("discordmanimator.__main__.create_and_run_bot")
    def test_run_bot(self, mock_create_bot, tmp_path, monkeypatch, capsys):
        """Test running the bot with valid config."""
        config_file = tmp_path / "config.toml"
        config_file.write_text(
            """
token = "valid_token_1234567890_abcdefghijklmnopqrstuvwxyz123456"

[bot]
prefix = "?"
description = "Test Bot"

[render]
use_onlinetex = true
disable_docker = false
"""
        )

        # Mock the bot
        mock_bot = MagicMock()
        mock_create_bot.return_value = mock_bot

        test_args = ["discordmanimator", str(config_file)]
        monkeypatch.setattr(sys, "argv", test_args)

        main()

        # Verify bot was created and run
        mock_create_bot.assert_called_once()
        mock_bot.run.assert_called_once()

        # Verify the token was passed correctly
        call_args = mock_bot.run.call_args
        token = call_args[0][0]
        assert token == "valid_token_1234567890_abcdefghijklmnopqrstuvwxyz123456"

        # Verify output
        captured = capsys.readouterr()
        assert "✓ Configuration loaded" in captured.out
        assert "Command prefix: ?" in captured.out
        assert "Description: Test Bot" in captured.out
        assert "Docker: enabled" in captured.out
        assert "OnlineTeX: enabled" in captured.out
        assert "Starting bot..." in captured.out

    def test_config_display_docker_disabled(self, tmp_path, monkeypatch, capsys):
        """Test that Docker disabled shows warning."""
        config_file = tmp_path / "config.toml"
        config_file.write_text(
            """
token = "valid_token_1234567890_abcdefghijklmnopqrstuvwxyz123456"

[render]
disable_docker = true
"""
        )

        test_args = ["discordmanimator", str(config_file), "--validate-only"]
        monkeypatch.setattr(sys, "argv", test_args)

        main()

        captured = capsys.readouterr()
        assert "Docker: DISABLED (not recommended)" in captured.out
