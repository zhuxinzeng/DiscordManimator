"""Tests for the configuration system."""

import pytest
from pydantic import ValidationError

from discordmanimator.config import (
    Config,
    BotConfig,
    RenderConfig,
    get_config,
    set_config,
    reset_config,
)


@pytest.fixture(autouse=True)
def reset_global_config():
    """Reset global config before and after each test."""
    reset_config()
    yield
    reset_config()


class TestBotConfig:
    """Tests for BotConfig model."""

    def test_default_values(self):
        """Test that BotConfig has correct defaults."""
        config = BotConfig()
        assert config.prefix == "!"
        assert config.description == "Manim Community Discord Bot"
        assert config.activity_name == "Animating with Manim"

    def test_custom_prefix(self):
        """Test custom prefix."""
        config = BotConfig(prefix="?")
        assert config.prefix == "?"

    def test_prefix_too_long(self):
        """Test that prefix cannot be too long."""
        with pytest.raises(ValidationError, match="at most 5"):
            BotConfig(prefix="!!!!!!")

    def test_prefix_too_short(self):
        """Test that prefix cannot be empty."""
        with pytest.raises(ValidationError, match="at least 1"):
            BotConfig(prefix="")


class TestRenderConfig:
    """Tests for RenderConfig model."""

    def test_default_values(self):
        """Test that RenderConfig has correct defaults."""
        config = RenderConfig()
        assert config.disable_docker is False
        assert config.use_onlinetex is False
        assert config.view_timeout == 120
        assert config.container_timeout == 120
        assert config.container_memory == "512m"
        assert config.render_quality == "m"
        assert config.docker_image == "manimcommunity/manim:stable"

    def test_custom_values(self):
        """Test custom values."""
        config = RenderConfig(
            disable_docker=True,
            use_onlinetex=True,
            view_timeout=60,
            container_timeout=180,
            render_quality="h",
            docker_image="custom/manim:latest",
        )
        assert config.disable_docker is True
        assert config.use_onlinetex is True
        assert config.view_timeout == 60
        assert config.container_timeout == 180
        assert config.render_quality == "h"
        assert config.docker_image == "custom/manim:latest"

    def test_view_timeout_validation(self):
        """Test view_timeout bounds validation."""
        # Too small
        with pytest.raises(ValidationError):
            RenderConfig(view_timeout=5)

        # Too large
        with pytest.raises(ValidationError):
            RenderConfig(view_timeout=1000)

        # Valid boundary values
        config = RenderConfig(view_timeout=10)
        assert config.view_timeout == 10

        config = RenderConfig(view_timeout=900)
        assert config.view_timeout == 900

    def test_container_timeout_validation(self):
        """Test container_timeout bounds validation."""
        # Too small
        with pytest.raises(ValidationError):
            RenderConfig(container_timeout=5)

        # Too large
        with pytest.raises(ValidationError):
            RenderConfig(container_timeout=700)

        # Valid boundary values
        config = RenderConfig(container_timeout=10)
        assert config.container_timeout == 10

        config = RenderConfig(container_timeout=600)
        assert config.container_timeout == 600

    def test_quality_validation(self):
        """Test render_quality pattern validation."""
        # Valid qualities
        for quality in ["l", "m", "h", "k"]:
            config = RenderConfig(render_quality=quality)
            assert config.render_quality == quality

        # Invalid qualities
        with pytest.raises(ValidationError):
            RenderConfig(render_quality="x")

        with pytest.raises(ValidationError):
            RenderConfig(render_quality="low")

        with pytest.raises(ValidationError):
            RenderConfig(render_quality="")

    def test_docker_image_validation(self):
        """Test docker_image validation."""
        # Valid images
        config = RenderConfig(docker_image="manimcommunity/manim:v0.18.0")
        assert config.docker_image == "manimcommunity/manim:v0.18.0"

        # Empty image should fail
        with pytest.raises(ValidationError):
            RenderConfig(docker_image="")

    def test_container_memory_validation(self):
        """Test container_memory validation."""
        # Valid memory strings
        for memory in ["512k", "256m", "1g", "2g", "1024k", "2048m"]:
            config = RenderConfig(container_memory=memory)
            assert config.container_memory == memory

        # Invalid memory strings
        with pytest.raises(ValidationError):
            RenderConfig(container_memory="512")  # No unit

        with pytest.raises(ValidationError):
            RenderConfig(container_memory="512mb")  # Invalid unit

        with pytest.raises(ValidationError):
            RenderConfig(container_memory="1GB")  # Uppercase

        with pytest.raises(ValidationError):
            RenderConfig(container_memory="")  # Empty

        with pytest.raises(ValidationError):
            RenderConfig(container_memory="abc")  # Not a number


class TestConfig:
    """Tests for main Config model."""

    def test_minimal_config(self):
        """Test minimal valid config with just token."""
        config = Config(
            token="test_token_123_this_is_a_valid_discord_bot_token_1234567890"
        )
        assert (
            config.token.get_secret_value()
            == "test_token_123_this_is_a_valid_discord_bot_token_1234567890"
        )
        assert config.bot.prefix == "!"
        assert config.render.disable_docker is False

    def test_missing_token(self):
        """Test that missing token raises error."""
        with pytest.raises(ValidationError, match="token"):
            Config()

    def test_invalid_token_placeholder(self):
        """Test that placeholder token is rejected."""
        with pytest.raises(ValidationError, match="Invalid token"):
            Config(token="paste_your_bot_token_here")

    def test_nested_config(self):
        """Test nested configuration."""
        config = Config(
            token="test_token_123_this_is_a_valid_discord_bot_token_1234567890",
            bot={"prefix": ">>", "description": "Test Bot"},
            render={"use_onlinetex": True},
        )
        assert config.bot.prefix == ">>"
        assert config.bot.description == "Test Bot"
        assert config.render.use_onlinetex is True

    def test_to_dict_excludes_secrets(self):
        """Test that to_dict excludes secrets by default."""
        config = Config(
            token="test_token_123_this_is_a_valid_discord_bot_token_1234567890"
        )
        data = config.to_dict(include_secrets=False)
        assert "token" not in data
        assert "bot" in data
        assert "render" in data

    def test_to_dict_includes_secrets(self):
        """Test that to_dict can include secrets."""
        config = Config(
            token="test_token_123_this_is_a_valid_discord_bot_token_1234567890"
        )
        data = config.to_dict(include_secrets=True)
        assert (
            data["token"]
            == "test_token_123_this_is_a_valid_discord_bot_token_1234567890"
        )

    def test_extra_fields_forbidden(self):
        """Test that extra/unknown fields are rejected."""
        with pytest.raises(ValidationError, match="extra"):
            Config(
                token="test_token_123_this_is_a_valid_discord_bot_token_1234567890",
                unknown_field="value",
            )


class TestConfigFromToml:
    """Tests for loading config from TOML files."""

    def test_load_minimal_toml(self, tmp_path):
        """Test loading minimal TOML config."""
        config_file = tmp_path / "config.toml"
        config_file.write_text(
            'token = "test_token_123_this_is_a_valid_discord_bot_token_1234567890"\n'
        )

        config = Config.from_toml(config_file)
        assert (
            config.token.get_secret_value()
            == "test_token_123_this_is_a_valid_discord_bot_token_1234567890"
        )
        assert config.bot.prefix == "!"

    def test_load_nested_toml(self, tmp_path):
        """Test loading TOML with nested config."""
        config_file = tmp_path / "config.toml"
        config_file.write_text("""
token = "test_token_123_this_is_a_valid_discord_bot_token_1234567890"

[bot]
prefix = "?"
description = "Custom Bot"

[render]
use_onlinetex = true
disable_docker = false
view_timeout = 90
container_timeout = 150
render_quality = "h"
docker_image = "manimcommunity/manim:v0.18.0"
""")

        config = Config.from_toml(config_file)
        assert config.bot.prefix == "?"
        assert config.bot.description == "Custom Bot"
        assert config.render.use_onlinetex is True
        assert config.render.disable_docker is False
        assert config.render.view_timeout == 90
        assert config.render.container_timeout == 150
        assert config.render.render_quality == "h"
        assert config.render.docker_image == "manimcommunity/manim:v0.18.0"

    def test_file_not_found(self, tmp_path):
        """Test that missing file raises FileNotFoundError."""
        config_file = tmp_path / "nonexistent.toml"
        with pytest.raises(FileNotFoundError, match="Config file not found"):
            Config.from_toml(config_file)

    def test_invalid_toml(self, tmp_path):
        """Test that invalid TOML raises error."""
        config_file = tmp_path / "config.toml"
        config_file.write_text('token = "paste_your_bot_token_here"')  # Placeholder

        with pytest.raises(ValidationError, match="Invalid token"):
            Config.from_toml(config_file)


class TestConfigSaveExample:
    """Tests for saving example config files."""

    def test_save_example(self, tmp_path):
        """Test saving example configuration."""
        config = Config(
            token="test_token_123_this_is_a_valid_discord_bot_token_1234567890"
        )
        example_path = tmp_path / "example.toml"

        config.save_example(example_path)

        # Verify file was created
        assert example_path.exists()

        # Verify it contains placeholder token
        content = example_path.read_text()
        assert "paste_your_bot_token_here" in content
        assert "test_token" not in content  # Should not leak actual token

        # Verify it's valid TOML
        import tomllib

        with open(example_path, "rb") as f:
            data = tomllib.load(f)
        assert "token" in data
        assert "bot" in data
        assert "render" in data


class TestGlobalConfig:
    """Tests for global config management."""

    def test_get_config_before_init(self):
        """Test that get_config raises error before initialization."""
        with pytest.raises(RuntimeError, match="not initialized"):
            get_config()

    def test_set_and_get_config(self):
        """Test setting and getting global config."""
        config = Config(
            token="test_token_123_this_is_a_valid_discord_bot_token_1234567890"
        )
        set_config(config)

        retrieved = get_config()
        assert retrieved is config
        assert (
            retrieved.token.get_secret_value()
            == "test_token_123_this_is_a_valid_discord_bot_token_1234567890"
        )

    def test_reset_config(self):
        """Test resetting global config."""
        config = Config(
            token="test_token_123_this_is_a_valid_discord_bot_token_1234567890"
        )
        set_config(config)
        assert get_config() is config

        reset_config()
        with pytest.raises(RuntimeError, match="not initialized"):
            get_config()


class TestConfigSummary:
    """Tests for config summary printing."""

    def test_print_summary_default(self, capsys):
        """Test printing summary with default values."""
        config = Config(
            token="test_token_123_this_is_a_valid_discord_bot_token_1234567890"
        )
        config.print_summary()

        captured = capsys.readouterr()
        assert "Command prefix: !" in captured.out
        assert "Description: Manim Community Discord Bot" in captured.out
        assert "Docker: enabled" in captured.out
        assert "Docker image: manimcommunity/manim:stable" in captured.out
        assert "Container timeout: 120s" in captured.out
        assert "OnlineTeX: disabled" in captured.out
        assert "Default quality: m" in captured.out
        assert "View timeout: 120s" in captured.out

    def test_print_summary_custom(self, capsys):
        """Test printing summary with custom values."""
        config = Config(
            token="test_token_123_this_is_a_valid_discord_bot_token_1234567890",
            bot={"prefix": "?", "description": "Custom Bot"},
            render={
                "use_onlinetex": True,
                "disable_docker": True,
                "render_quality": "h",
                "view_timeout": 60,
            },
        )
        config.print_summary()

        captured = capsys.readouterr()
        assert "Command prefix: ?" in captured.out
        assert "Description: Custom Bot" in captured.out
        assert "Docker: DISABLED (not recommended)" in captured.out
        assert "OnlineTeX: enabled" in captured.out
        assert "Default quality: h" in captured.out
        assert "View timeout: 60s" in captured.out
        # Docker image and container timeout should not appear when docker is disabled
        assert "Docker image:" not in captured.out
        assert "Container timeout:" not in captured.out


class TestEnvironmentVariables:
    """Tests for environment variable overrides."""

    def test_env_override_token(self, monkeypatch):
        """Test environment variable override for token."""
        monkeypatch.setenv(
            "DISCORDMANIMATOR_TOKEN",
            "env_token_123_this_is_a_valid_discord_bot_token_1234567890",
        )
        config = Config()
        assert (
            config.token.get_secret_value()
            == "env_token_123_this_is_a_valid_discord_bot_token_1234567890"
        )

    def test_env_override_nested(self, monkeypatch):
        """Test environment variable override for nested fields."""
        monkeypatch.setenv(
            "DISCORDMANIMATOR_TOKEN",
            "env_token_123_this_is_a_valid_discord_bot_token_1234567890",
        )
        monkeypatch.setenv("DISCORDMANIMATOR_BOT__PREFIX", ">>")
        monkeypatch.setenv("DISCORDMANIMATOR_RENDER__USE_ONLINETEX", "true")

        config = Config()
        assert config.bot.prefix == ">>"
        assert config.render.use_onlinetex is True

    def test_env_vars_with_config(self, monkeypatch):
        """Test that environment variables work when creating Config."""
        monkeypatch.setenv(
            "DISCORDMANIMATOR_TOKEN",
            "env_token_123_this_is_a_valid_discord_bot_token_1234567890",
        )
        monkeypatch.setenv("DISCORDMANIMATOR_BOT__PREFIX", "?")

        # When using Config() directly, env vars are used
        config = Config()
        assert config.bot.prefix == "?"
        assert (
            config.token.get_secret_value()
            == "env_token_123_this_is_a_valid_discord_bot_token_1234567890"
        )
