from __future__ import annotations

import io
import logging
import os
import re
import tempfile
import traceback
from pathlib import Path
from typing import Any

import aiodocker
import discord
from discord.ext import commands

from ..config import get_config

logger = logging.getLogger(__name__)


class RenderCodeblock(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        super().__init__()
        self.bot = bot
        self.config = get_config()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.id == self.bot.user.id:
            return

        if extract_manim_snippets(message.content):
            view = RenderView(timeout=self.config.render.view_timeout)
            message = await message.reply(
                "This message looks like it contains a Manim snippet, "
                "do you want me to render it?",
                view=view,
            )
            view.message = message


class RenderView(discord.ui.View):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.message_deleted = False

    @discord.ui.button(
        label="Yes, render",
        style=discord.ButtonStyle.blurple,
    )
    async def render(self, interaction: discord.Interaction, button: discord.ui.Button):
        for child in self.children:
            child.disabled = True
        await self.message.edit(view=self)
        await interaction.response.defer()
        async with interaction.channel.typing():
            code_message = await interaction.channel.fetch_message(
                interaction.message.reference.message_id
            )
            response = await render_animation_snippet(
                code_message, interaction=interaction
            )
            response.pop("cli_flags")

            button.label = "Render again"
            for child in self.children:
                child.disabled = False
            await interaction.followup.edit_message(
                message_id=interaction.message.id, view=self, **response
            )

    @discord.ui.button(
        label="Change settings",
        style=discord.ButtonStyle.secondary,
    )
    async def change_settings(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.send_modal(SettingsModal())

    @discord.ui.button(
        label="Go away",
        style=discord.ButtonStyle.red,
    )
    async def close(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        self.message_deleted = True
        await interaction.message.delete()

    async def on_timeout(self):
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

    async def on_submit(self, interaction: discord.Interaction):
        if any(
            ch in self.CLI_flags.value for ch in [";", "&", "|", "$", ">", "<", "`"]
        ):
            logger.warning(
                "Invalid CLI flags rejected",
                extra={
                    "user_id": interaction.user.id,
                    "reason": "contains_forbidden_characters",
                },
            )
            await interaction.response.send_message(
                "Something went wrong, please try again.",
                ephemeral=True,
            )
            return

        await interaction.response.defer()
        async with interaction.channel.typing():
            code_message = await interaction.channel.fetch_message(
                interaction.message.reference.message_id
            )
            response = await render_animation_snippet(
                code_message,
                cli_flags=self.CLI_flags.value.split(),
                interaction=interaction,
            )
            cli_flags = response.pop("cli_flags")
            if cli_flags:
                response["content"] += f"\n\nPassed CLI flags: `{cli_flags}`"
            config = get_config()
            view = RenderView(timeout=config.render.view_timeout)
            view.children[0].label = "Render again"
            message = await interaction.followup.edit_message(
                message_id=interaction.message.id, view=view, **response
            )
            view.message = message


def extract_manim_snippets(msg) -> None | str:
    pattern = re.compile(r"```(?:python|py)?([^`]*def construct[^`]*)```")
    return pattern.findall(msg)


async def render_animation_snippet(
    code_message, cli_flags=None, interaction=None
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

    # Log render request with minimal metadata
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

    # theoretically, multiple snippets could be rendered
    # at once. for now, we'll just choose and render the
    # first one.
    [snippet, *rest] = extract_manim_snippets(code_message.content)
    snippet = snippet.strip()

    if snippet.startswith("def construct(self):"):
        snippet = ["class Manimation(Scene):"] + [
            "    " + line for line in snippet.split("\n")
        ]
    else:
        snippet = snippet.split("\n")

    prescript = ["from manim import *"]
    if config.render.use_onlinetex:
        prescript.append("from manim_onlinetex import *")
    script = prescript + snippet

    with tempfile.TemporaryDirectory() as tmpdirname:
        with open(Path(tmpdirname) / "script.py", "w", encoding="utf-8") as f:
            f.write("\n".join(script))

        try:
            async with aiodocker.Docker() as dockerclient:
                container = await dockerclient.containers.run(
                    config={
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
                            "Binds": [f"{tmpdirname}:/manim/:rw"],
                            "AutoRemove": True,
                        },
                    }
                )
                manim_stderr = [
                    line.rstrip()
                    async for line in container.log(follow=True, stderr=True)
                ]
                # `follow=True` allow to keep the stream open until the container stops

            if manim_stderr:
                raise ManimError(traceback=manim_stderr)

        except ManimError as e:
            # Manim itself threw an error (expected error case)
            render_time = time.time() - start_time
            logger.info(
                "Render failed: Manim error",
                extra={**log_extra, "render_time_seconds": round(render_time, 2)},
            )
            return {
                "content": "Something went wrong! :cry: Here is what Manim reports.",
                "cli_flags": cli_flags,
                "attachments": [
                    discord.File(
                        fp=io.StringIO(e.traceback),
                        filename="error.log",
                    ),
                ],
            }

        except aiodocker.DockerContainerError as e:
            # Docker container execution failed
            render_time = time.time() - start_time
            logger.error(
                "Render failed: Docker container error",
                extra={**log_extra, "render_time_seconds": round(render_time, 2)},
                exc_info=True,
            )
            return {
                "content": "Something went wrong with the Docker container. :cry:",
                "cli_flags": cli_flags,
                "attachments": [
                    discord.File(
                        fp=io.BytesIO(e.message),
                        filename="error.log",
                    ),
                ],
            }

        except aiodocker.DockerError as e:
            # Docker communication error (daemon not running, etc.)
            render_time = time.time() - start_time
            logger.error(
                "Render failed: Docker daemon error",
                extra={**log_extra, "render_time_seconds": round(render_time, 2)},
                exc_info=True,
            )
            error_msg = f"Docker error: {e}"
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

        except Exception as e:
            # Unexpected error
            render_time = time.time() - start_time
            logger.error(
                "Render failed: Unexpected error",
                extra={
                    **log_extra,
                    "render_time_seconds": round(render_time, 2),
                    "error_type": type(e).__name__,
                },
                exc_info=True,
            )
            tb = traceback.format_exc()
            return {
                "content": "An unexpected error occurred. :cry:",
                "cli_flags": cli_flags,
                "attachments": [
                    discord.File(
                        fp=io.BytesIO(tb.encode()),
                        filename="error.log",
                    ),
                ],
            }

        # Find output file
        output_files = list(Path(tmpdirname).rglob("scriptoutput.*"))
        if len(output_files) == 0:
            render_time = time.time() - start_time
            logger.warning(
                "Render failed: No output file produced",
                extra={**log_extra, "render_time_seconds": round(render_time, 2)},
            )
            return {
                "content": "No output file was produced. :cry:",
                "cli_flags": cli_flags,
            }
        elif len(output_files) > 1:
            render_time = time.time() - start_time
            logger.warning(
                "Render failed: Multiple output files",
                extra={
                    **log_extra,
                    "render_time_seconds": round(render_time, 2),
                    "file_count": len(output_files),
                },
            )
            return {
                "content": f"Multiple output files found ({len(output_files)}). :cry:",
                "cli_flags": cli_flags,
            }

        # Success case
        outfilepath = output_files[0]
        render_time = time.time() - start_time
        file_size_kb = outfilepath.stat().st_size / 1024

        logger.info(
            "Render completed successfully",
            extra={
                **log_extra,
                "render_time_seconds": round(render_time, 2),
                "output_file": outfilepath.name,
                "file_size_kb": round(file_size_kb, 2),
            },
        )
        return {
            "content": "Here you go!",
            "cli_flags": cli_flags,
            "attachments": [
                discord.File(outfilepath),
            ],
        }


async def setup(bot: commands.Bot):
    """Entrypoint of loading the bot extension."""
    await bot.add_cog(RenderCodeblock(bot))
    logging.info("RenderCodeblock cog has been added.")


class ManimError(ChildProcessError):
    def __init__(self, traceback: list[str]):
        self.traceback = "\n".join(traceback)
