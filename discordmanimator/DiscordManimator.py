"""Discord bot creation and setup."""

from __future__ import annotations

import asyncio
import logging
import traceback
from pathlib import Path

import discord
from discord.ext import commands

from .config import get_config


def create_and_run_bot() -> commands.Bot:
    """Create and configure the Discord bot.

    Returns:
        Configured Bot instance ready to run
    """
    config = get_config()

    intents = discord.Intents.default()
    intents.message_content = True

    bot = commands.Bot(
        description=config.bot.description,
        activity=discord.Game(config.bot.activity_name),
        help_command=None,
        command_prefix=config.bot.prefix,
        case_insensitive=True,
        strip_after_prefix=True,
        intents=intents,
    )

    @bot.event
    async def on_ready():
        logging.info(f"Logged in as {bot.user.name}")
        logging.info(f"Bot is in {len(bot.guilds)} guilds")
        await bot.tree.sync()

    async def load_cogs():
        cogs_dir = Path(__file__).parent / "cogs"
        loaded = []
        failed = []

        for extension in cogs_dir.glob("*.py"):
            if extension.name.startswith("_"):
                continue

            cog_name = f"discordmanimator.cogs.{extension.stem}"
            try:
                await bot.load_extension(cog_name)
                loaded.append(extension.stem)
            except Exception:
                failed.append(extension.stem)
                logging.error(f"Failed to load cog: {extension.stem}")
                traceback.print_exc()

        logging.info(f"Loaded {len(loaded)} cogs: {', '.join(loaded)}")
        if failed:
            logging.warning(f"Failed to load {len(failed)} cogs: {', '.join(failed)}")

    asyncio.run(load_cogs())

    return bot
