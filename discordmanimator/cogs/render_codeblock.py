from __future__ import annotations

import io
import logging
import os
import tempfile
import traceback
from pathlib import Path
from typing import Any

import aiodocker
import discord
from discord.ext import commands

from ..config import Config, get_config
from ..snippet_parser import (
    extract_non_animation_code,
    extract_snippet_from_message,
    parse_snippet,
    rename_function_to_construct,
)

logger = logging.getLogger(__name__)


class RenderCodeblock(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        super().__init__()
        self.bot = bot
        self.config = get_config()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.id == self.bot.user.id:
            return

        if extract_snippet_from_message(message.content):
            view = RenderView(timeout=self.config.render.view_timeout)
            message = await message.reply(
                "This message looks like it contains a Manim snippet, "
                "do you want me to render it?",
                view=view,
            )
            view.message = message


class RenderView(discord.ui.View):
    message: discord.Message  # Will be set after creation

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.message_deleted = False

    @discord.ui.button(
        label="Yes, render",
        style=discord.ButtonStyle.blurple,
    )
    async def render(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        # Disable buttons during render
        for child in self.children:
            child.disabled = True
        await self.message.edit(view=self)

        await interaction.response.defer()
        async with interaction.channel.typing():
            response, view = await handle_render_request(interaction)

            message = await interaction.followup.edit_message(
                message_id=interaction.message.id, view=view, **response
            )
            view.message = message

    @discord.ui.button(
        label="Change settings",
        style=discord.ButtonStyle.secondary,
    )
    async def change_settings(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await interaction.response.send_modal(SettingsModal())

    @discord.ui.button(
        label="Go away",
        style=discord.ButtonStyle.red,
    )
    async def close(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        self.message_deleted = True
        await interaction.message.delete()

    async def on_timeout(self) -> None:
        if self.message_deleted:
            return
        try:
            await self.message.edit(view=self.clear_items())
        except discord.NotFound:
            # Message was already deleted
            pass


class SettingsModal(discord.ui.Modal, title="Change render settings"):
    CLI_flags = discord.ui.TextInput(
        label="CLI flags",
        placeholder="--renderer=cairo",
        required=False,
    )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        async with interaction.channel.typing():
            response, view = await handle_render_request(
                interaction,
                cli_flags=self.CLI_flags.value.split(),
                show_cli_flags_in_response=True,
            )

            message = await interaction.followup.edit_message(
                message_id=interaction.message.id, view=view, **response
            )
            view.message = message


def prepare_snippet(raw_content: str, config: Config) -> list[str]:
    """Extract and transform snippet into script lines ready to write.

    Args:
        raw_content: Raw message content containing code snippet
        config: Bot configuration with render settings

    Returns:
        List of script lines including imports and snippet code
    """
    # Extract first snippet
    snippets = extract_snippet_from_message(raw_content)
    if not snippets:
        raise ValueError("No valid animation snippet found in message")

    raw_snippet = snippets[0]
    snippet_info = parse_snippet(raw_snippet)

    if snippet_info is None:
        raise ValueError("Failed to parse animation snippet")

    # Build script lines
    script_lines = []

    # Add default imports (from manim import *)
    script_lines.append("from manim import *")
    if config.render.use_onlinetex:
        script_lines.append("from manim_onlinetex import *")

    # Add user code
    if snippet_info.needs_wrapping:
        # User provided a bare function
        # Add all non-animation code (imports, helpers, etc.)
        non_animation_code = extract_non_animation_code(
            snippet_info.raw_code, snippet_info.function_name
        )
        script_lines.extend(non_animation_code)

        # Rename function to 'construct' and change parameter to 'self'
        renamed_function = rename_function_to_construct(
            snippet_info.animation_function, snippet_info.function_name
        )

        # Wrap the renamed function in a Scene class
        script_lines.append("class Manimation(Scene):")
        for line in renamed_function.split("\n"):
            script_lines.append("    " + line)
    else:
        # User provided a class - add entire snippet as-is
        script_lines.extend(snippet_info.animation_function.split("\n"))

    return script_lines


async def handle_render_request(
    interaction: discord.Interaction,
    cli_flags: list[str] | None = None,
    show_cli_flags_in_response: bool = False,
) -> tuple[dict[str, Any], discord.ui.View]:
    """Handle a render request from a button or modal interaction.

    Fetches the code message, renders it, and prepares the response with a fresh view.

    Args:
        interaction: Discord interaction triggering the render
        cli_flags: Optional CLI flags to pass to manim
        show_cli_flags_in_response: Whether to append CLI flags to response content

    Returns:
        Tuple of (response_dict, view) ready to use with followup.edit_message
    """
    # Fetch code message from reference
    code_message = await interaction.channel.fetch_message(
        interaction.message.reference.message_id
    )

    # Render the snippet
    response = await render_animation_snippet(
        code_message,
        cli_flags=cli_flags,
        interaction=interaction,
    )

    # Process response
    cli_flags_used = response.pop("cli_flags")
    if show_cli_flags_in_response and cli_flags_used:
        response["content"] += f"\n\nPassed CLI flags: `{cli_flags_used}`"

    # Create fresh view with updated button label
    config = get_config()
    view = RenderView(timeout=config.render.view_timeout)
    view.children[0].label = "Render again"

    return response, view


def _parse_memory_string(memory_str: str) -> int:
    """Parse memory string (e.g., '512m', '1g') to bytes for Docker API.

    Docker API expects memory limit as an integer in bytes.

    Args:
        memory_str: Memory string like '512m', '1g', '2048k'

    Returns:
        Memory limit in bytes

    Examples:
        >>> _parse_memory_string("512m")
        536870912
        >>> _parse_memory_string("1g")
        1073741824
        >>> _parse_memory_string("2048k")
        2097152
    """
    memory_str = memory_str.lower()
    if memory_str.endswith("k"):
        return int(memory_str[:-1]) * 1024
    elif memory_str.endswith("m"):
        return int(memory_str[:-1]) * 1024 * 1024
    elif memory_str.endswith("g"):
        return int(memory_str[:-1]) * 1024 * 1024 * 1024
    else:
        raise ValueError(f"Invalid memory string format: {memory_str}")


def build_container_config(
    script_dir: str, cli_flags: list[str], config: Config
) -> dict[str, Any]:
    """Build Docker container configuration for rendering.

    Args:
        script_dir: Path to directory containing script.py
        cli_flags: List of CLI flags to pass to manim
        config: Bot configuration with render settings

    Returns:
        Docker container configuration dict

    Raises:
        ValueError: If cli_flags contain forbidden characters
    """
    # Security validation: check for shell injection characters
    if cli_flags:
        forbidden_chars = [";", "&", "|", "$", ">", "<", "`"]
        cli_flags_str = " ".join(cli_flags)
        if any(ch in cli_flags_str for ch in forbidden_chars):
            raise ValueError(
                f"CLI flags contain forbidden characters: {forbidden_chars}"
            )

    return {
        "Image": config.render.docker_image,
        "Cmd": [
            "timeout",
            str(config.render.container_timeout),
            "manim",
            f"--quality={config.render.render_quality}",
            "--disable_caching",
            "--progress_bar=none",
            "--output_file=scriptoutput",
            *cli_flags,
            "/manim/script.py",
        ],
        "User": str(os.getuid()),
        "HostConfig": {
            "Binds": [f"{script_dir}:/manim/:rw"],
            "AutoRemove": True,
            "Memory": _parse_memory_string(config.render.container_memory),
        },
    }


async def execute_render(container_config: dict[str, Any]) -> None:
    """Execute Docker container and check for Manim errors.

    Args:
        container_config: Docker container configuration

    Raises:
        ManimError: If Manim reports errors on stderr
        aiodocker.DockerError: If Docker execution fails
    """
    async with aiodocker.Docker() as dockerclient:
        container = await dockerclient.containers.run(config=container_config)
        manim_stderr = [
            line.rstrip() async for line in container.log(follow=True, stderr=True)
        ]
        # `follow=True` allows keeping the stream open until the container stops

    if manim_stderr:
        raise ManimError(traceback=manim_stderr)


def find_output_file(directory: Path) -> Path:
    """Locate and validate the rendered output file.

    Args:
        directory: Directory to search for output file

    Returns:
        Path to the output file

    Raises:
        FileNotFoundError: If no output file is found
        ValueError: If multiple output files are found
    """
    output_files = list(directory.rglob("scriptoutput.*"))
    num_files = len(output_files)

    if num_files == 0:
        raise FileNotFoundError(
            "No output file was produced. :cry:\n\n"
            "This usually means the scene didn't render successfully. "
            "Check the error log above for details."
        )

    if num_files > 1:
        file_names = [f.name for f in output_files]
        raise ValueError(
            f"Multiple output files found ({num_files}). "
            f"Expected exactly one output file, but found: {', '.join(file_names)}"
        )

    return output_files[0]


def format_render_response(
    output_file: Path | None,
    error: Exception | None,
    cli_flags: list[str],
) -> dict[str, Any]:
    """Format response dict for Discord based on render result.

    Args:
        output_file: Path to rendered output file (if successful)
        error: Exception if render failed (if unsuccessful)
        cli_flags: CLI flags used for rendering

    Returns:
        Dictionary with content, cli_flags, and optional attachments
    """
    if output_file is not None:
        # Success case
        return {
            "content": "Here you go!",
            "cli_flags": cli_flags,
            "attachments": [discord.File(output_file)],
        }

    # Error cases
    if isinstance(error, ManimError):
        return {
            "content": "Something went wrong! :cry: Here is what Manim reports.",
            "cli_flags": cli_flags,
            "attachments": [
                discord.File(
                    fp=io.BytesIO(error.traceback.encode()),
                    filename="error.log",
                ),
            ],
        }

    if isinstance(error, aiodocker.DockerContainerError):
        # error.message could be bytes or str, ensure bytes
        error_bytes = (
            error.message
            if isinstance(error.message, bytes)
            else error.message.encode()
        )
        return {
            "content": "Something went wrong with the Docker container. :cry:",
            "cli_flags": cli_flags,
            "attachments": [
                discord.File(
                    fp=io.BytesIO(error_bytes),
                    filename="error.log",
                ),
            ],
        }

    if isinstance(error, aiodocker.DockerError):
        error_msg = f"Docker error: {error}"
        return {
            "content": "Could not connect to Docker. :cry:",
            "cli_flags": cli_flags,
            "attachments": [
                discord.File(
                    fp=io.BytesIO(error_msg.encode()),
                    filename="error.log",
                ),
            ],
        }

    if isinstance(error, (FileNotFoundError, ValueError)):
        # Output file validation errors
        return {
            "content": f"{str(error)} :cry:",
            "cli_flags": cli_flags,
        }

    # Unexpected error
    if error is None:
        return {
            "content": "An unexpected error occurred (error was None). :cry:",
            "cli_flags": cli_flags,
        }

    tb = traceback.format_exception(type(error), error, error.__traceback__)
    return {
        "content": "An unexpected error occurred. :cry:",
        "cli_flags": cli_flags,
        "attachments": [
            discord.File(
                fp=io.BytesIO("".join(tb).encode()),
                filename="error.log",
            ),
        ],
    }


async def render_animation_snippet(
    code_message: discord.Message,
    cli_flags: list[str] | None = None,
    interaction: discord.Interaction | None = None,
) -> dict[str, Any]:
    """Render a Manim animation snippet from a code message.

    Args:
        code_message: Discord message containing the code snippet
        cli_flags: Optional list of CLI flags to pass to manim
        interaction: Optional Discord interaction for logging context

    Returns:
        Dictionary with response content and attachments
    """
    import time

    start_time = time.time()

    if cli_flags is None:
        cli_flags = []

    config = get_config()

    # Set up logging context
    log_extra = {
        "snippet_lines": len(code_message.content.split("\n")),
        "has_cli_flags": bool(cli_flags),
        "cli_flag_count": len(cli_flags) if cli_flags else 0,
    }
    if interaction:
        log_extra.update(
            {
                "user_id": interaction.user.id,
                "guild_id": interaction.guild_id,
                "channel_id": interaction.channel_id,
            }
        )

    logger.info("Render request started", extra=log_extra)

    # Check if Docker is disabled
    if config.render.disable_docker:
        logger.info("Render blocked: Docker disabled", extra=log_extra)
        return {
            "content": "Docker rendering is disabled. Cannot render animations.",
            "cli_flags": cli_flags,
        }

    # Prepare script
    try:
        script_lines = prepare_snippet(code_message.content, config)
    except Exception as e:
        render_time = time.time() - start_time
        logger.error(
            "Render failed: Snippet preparation error",
            extra={**log_extra, "render_time_seconds": round(render_time, 2)},
            exc_info=True,
        )
        return format_render_response(None, e, cli_flags)

    # Execute render with tempdir context
    with tempfile.TemporaryDirectory() as tmpdirname:
        # Write script to file
        with open(Path(tmpdirname) / "script.py", "w", encoding="utf-8") as f:
            f.write("\n".join(script_lines))

        # Build container configuration with actual script directory
        try:
            container_config = build_container_config(
                script_dir=tmpdirname,
                cli_flags=cli_flags,
                config=config,
            )
        except ValueError as e:
            # CLI flag validation failed
            render_time = time.time() - start_time
            logger.warning(
                "Render blocked: Invalid CLI flags",
                extra={
                    **log_extra,
                    "render_time_seconds": round(render_time, 2),
                    "error": str(e),
                },
            )
            return {
                "content": "Something went wrong, please try again.",
                "cli_flags": cli_flags,
            }

        # Execute Docker render
        try:
            await execute_render(container_config)
        except ManimError as e:
            render_time = time.time() - start_time
            logger.info(
                "Render failed: Manim error",
                extra={**log_extra, "render_time_seconds": round(render_time, 2)},
            )
            return format_render_response(None, e, cli_flags)
        except aiodocker.DockerContainerError as e:
            render_time = time.time() - start_time
            logger.error(
                "Render failed: Docker container error",
                extra={**log_extra, "render_time_seconds": round(render_time, 2)},
                exc_info=True,
            )
            return format_render_response(None, e, cli_flags)
        except aiodocker.DockerError as e:
            render_time = time.time() - start_time
            logger.error(
                "Render failed: Docker daemon error",
                extra={**log_extra, "render_time_seconds": round(render_time, 2)},
                exc_info=True,
            )
            return format_render_response(None, e, cli_flags)
        except Exception as e:
            render_time = time.time() - start_time
            logger.error(
                "Render failed: Unexpected error during execution",
                extra={
                    **log_extra,
                    "render_time_seconds": round(render_time, 2),
                    "error_type": type(e).__name__,
                },
                exc_info=True,
            )
            return format_render_response(None, e, cli_flags)

        # Find and validate output file
        try:
            output_file = find_output_file(Path(tmpdirname))
        except (FileNotFoundError, ValueError) as e:
            render_time = time.time() - start_time
            log_level = logger.warning
            extra_data = {**log_extra, "render_time_seconds": round(render_time, 2)}

            if isinstance(e, FileNotFoundError):
                log_level(
                    "Render failed: No output file produced",
                    extra={**extra_data, "expected_pattern": "scriptoutput.*"},
                )
            else:
                # ValueError - multiple files
                log_level(
                    "Render failed: Multiple output files found", extra=extra_data
                )

            return format_render_response(None, e, cli_flags)

        # Success!
        render_time = time.time() - start_time
        file_size_kb = output_file.stat().st_size / 1024

        logger.info(
            "Render completed successfully",
            extra={
                **log_extra,
                "render_time_seconds": round(render_time, 2),
                "output_file": output_file.name,
                "file_size_kb": round(file_size_kb, 2),
            },
        )
        return format_render_response(output_file, None, cli_flags)


async def setup(bot: commands.Bot) -> None:
    """Entrypoint of loading the bot extension."""
    await bot.add_cog(RenderCodeblock(bot))
    logging.info("RenderCodeblock cog has been added.")


class ManimError(ChildProcessError):
    def __init__(self, traceback: list[str]) -> None:
        self.traceback = "\n".join(traceback)
