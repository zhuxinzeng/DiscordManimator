"""Configuration system for DiscordManimator.

This module provides a validated configuration system using Pydantic.
Configuration is loaded from TOML files and can be overridden with environment variables.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import tomllib
from pydantic import BaseModel, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class BotConfig(BaseModel):
    """Discord bot specific configuration.

    Attributes:
        prefix: Command prefix for the bot
        description: Bot description shown in Discord
        activity_name: Activity name shown in bot status
    """

    prefix: str = Field(
        default="!",
        description="Command prefix for the bot",
        min_length=1,
        max_length=5,
    )

    description: str = Field(
        default="Manim Community Discord Bot",
        description="Bot description shown in Discord",
    )

    activity_name: str = Field(
        default="Animating with Manim",
        description="Activity name shown in bot status",
    )


class RenderConfig(BaseModel):
    """Configuration for Manim rendering.

    Attributes:
        disable_docker: Whether to disable Docker for rendering (not recommended)
        use_onlinetex: Whether to use manim-onlinetex for LaTeX rendering
        view_timeout: Timeout in seconds for button view before it's removed
        container_timeout: Timeout in seconds for Docker container execution
        render_quality: Default render quality (l=low, m=medium, h=high, k=4k)
        docker_image: Docker image to use for rendering
    """

    disable_docker: bool = Field(
        default=False,
        description="Disable Docker for rendering (not recommended for security)",
    )

    use_onlinetex: bool = Field(
        default=False,
        description="Whether to use manim-onlinetex for LaTeX rendering",
    )

    view_timeout: int = Field(
        default=120,
        description="Timeout in seconds for button view before it's removed",
        ge=10,
        le=900,  # Discord's max interaction timeout is 15 minutes
    )

    container_timeout: int = Field(
        default=120,
        description="Timeout in seconds for Docker container execution",
        ge=10,
        le=600,  # Max 10 minutes to prevent abuse
    )

    render_quality: str = Field(
        default="m",
        description="Default render quality (l=low, m=medium, h=high, k=4k)",
        pattern="^[lmhk]$",
    )

    docker_image: str = Field(
        default="manimcommunity/manim:stable",
        description="Docker image to use for rendering",
        min_length=1,
    )


class Config(BaseSettings):
    """Root configuration for DiscordManimator.

    Configuration is loaded from:
    1. TOML file (specified at runtime)
    2. Environment variables (prefixed with DISCORDMANIMATOR_)

    Environment variables override TOML settings.

    Example environment variables:
        DISCORDMANIMATOR_TOKEN=your_token_here
        DISCORDMANIMATOR_BOT__PREFIX=!!
        DISCORDMANIMATOR_RENDER__USE_ONLINETEX=true

    Attributes:
        token: Discord bot token (required, kept secret)
        bot: Discord bot configuration
        render: Rendering configuration
    """

    model_config = SettingsConfigDict(
        env_prefix="DISCORDMANIMATOR_",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="forbid",  # Reject unknown config keys
        validate_default=True,
    )

    # Required field
    token: SecretStr = Field(
        ...,  # Required
        description="Discord bot token (keep this secret!)",
    )

    # Nested configuration
    bot: BotConfig = Field(
        default_factory=BotConfig,
        description="Discord bot configuration",
    )

    render: RenderConfig = Field(
        default_factory=RenderConfig,
        description="Rendering configuration",
    )

    @field_validator("token")
    @classmethod
    def validate_token(cls, v: SecretStr) -> SecretStr:
        """Ensure token is not a placeholder."""
        token_str = v.get_secret_value()
        if not token_str or token_str in (
            "paste_token_here",
            "paste_your_bot_token_here",
        ):
            raise ValueError(
                "Invalid token. Please set a valid Discord bot token. "
                "You can get one from https://discord.com/developers/applications"
            )
        if len(token_str) < 50:  # Discord tokens are typically 59+ chars
            logging.warning(
                "Token seems unusually short. Make sure it's a valid Discord bot token."
            )
        return v

    def model_post_init(self, __context: Any) -> None:
        """Post-initialization validation."""
        # Warn if Docker is disabled
        if self.render.disable_docker:
            logging.warning(
                "Docker is disabled! This is NOT RECOMMENDED for security. "
                "User code will run directly on your system."
            )

    @classmethod
    def from_toml(cls, path: Path) -> Config:
        """Load configuration from a TOML file.

        Args:
            path: Path to the TOML configuration file

        Returns:
            Validated Config instance

        Raises:
            ValidationError: If configuration is invalid
            FileNotFoundError: If config file doesn't exist

        Example:
            >>> config = Config.from_toml(Path("config.toml"))
            >>> print(config.bot.prefix)
            !
        """
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")

        with open(path, "rb") as f:
            data = tomllib.load(f)

        return cls(**data)

    def to_dict(self, include_secrets: bool = False) -> dict[str, Any]:
        """Export configuration as dictionary.

        Args:
            include_secrets: Whether to include secret values (default: False)

        Returns:
            Dictionary representation of config
        """
        data = self.model_dump(
            mode="json", exclude=set() if include_secrets else {"token"}
        )

        # If we're including secrets, we need to manually get the secret value
        if include_secrets:
            data["token"] = self.token.get_secret_value()

        return data

    def save_example(self, path: Path) -> None:
        """Save an example configuration file with all defaults.

        Args:
            path: Where to save the example config

        Example:
            >>> config = Config(token="dummy")
            >>> config.save_example(Path("example.config.toml"))
        """
        import tomli_w

        # Create example with placeholder token
        example_data = self.to_dict(include_secrets=False)
        example_data["token"] = "paste_your_bot_token_here"

        with open(path, "wb") as f:
            tomli_w.dump(example_data, f)

        logging.info(f"Example configuration saved to: {path}")

    def print_summary(self) -> None:
        """Print a human-readable summary of the configuration.

        This is useful for showing the user what settings are active at startup.
        """
        print(f"  Command prefix: {self.bot.prefix}")
        print(f"  Description: {self.bot.description}")
        print(
            f"  Docker: {'enabled' if not self.render.disable_docker else 'DISABLED (not recommended)'}"
        )
        if not self.render.disable_docker:
            print(f"  Docker image: {self.render.docker_image}")
            print(f"  Container timeout: {self.render.container_timeout}s")
        print(f"  OnlineTeX: {'enabled' if self.render.use_onlinetex else 'disabled'}")
        print(f"  Default quality: {self.render.render_quality}")
        print(f"  View timeout: {self.render.view_timeout}s")


# Global config instance (initialized in __main__.py)
_config: Config | None = None


def get_config() -> Config:
    """Get the global configuration instance.

    Returns:
        The initialized Config instance

    Raises:
        RuntimeError: If config hasn't been initialized

    Example:
        >>> from discordmanimator.config import get_config
        >>> config = get_config()
        >>> print(config.bot.prefix)
    """
    if _config is None:
        raise RuntimeError(
            "Configuration not initialized. "
            "Call set_config() first in your entry point."
        )
    return _config


def set_config(config: Config) -> None:
    """Set the global configuration instance.

    This should be called once at application startup.

    Args:
        config: The Config instance to use globally

    Example:
        >>> config = Config.from_toml(Path("config.toml"))
        >>> set_config(config)
    """
    global _config
    _config = config
    logging.debug("Configuration initialized successfully")


def reset_config() -> None:
    """Reset the global configuration (mainly for testing).

    Example:
        >>> reset_config()  # Clear global config
    """
    global _config
    _config = None
