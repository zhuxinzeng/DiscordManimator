"""Entry point for DiscordManimator bot."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pydantic import ValidationError, SecretStr

from .config import Config, set_config
from .DiscordManimator import create_and_run_bot
from .health import start_health_server
from .logging_config import setup_logging_with_extra_fields


def main() -> None:
    """Main entry point for the bot."""

    # Set up logging with support for structured extra fields
    setup_logging_with_extra_fields()

    parser = argparse.ArgumentParser(
        prog="DiscordManimator",
        description="Discord bot for rendering Manim animations",
    )
    parser.add_argument(
        "configfile",
        nargs="?",
        default=None,
        help="Path to the TOML configuration file (optional if DISCORDMANIMATOR_* env vars are set)",
        type=Path,
    )
    parser.add_argument(
        "--generate-example",
        help="Generate an example config file and exit",
        action="store_true",
    )
    parser.add_argument(
        "--validate-only",
        help="Validate config file and exit (don't run bot)",
        action="store_true",
    )

    args = parser.parse_args()

    # Generate example config if requested
    if args.generate_example:
        if args.configfile is None:
            print("✗ Error: config file path is required with --generate-example", file=sys.stderr)
            sys.exit(1)
        try:
            # Create config with dummy token to get defaults
            dummy_config = Config(
                token=SecretStr(
                    "irrelevant and just needs to be long enough to pass validation"
                )
            )
            dummy_config.save_example(args.configfile)
            print(f"✓ Example configuration saved to: {args.configfile}")
            print(
                "\nEdit the file and replace 'paste_your_bot_token_here' with your actual token."
            )
            print(
                "You can get a token from: https://discord.com/developers/applications"
            )
            return
        except Exception as e:
            print(f"✗ Error generating example: {e}", file=sys.stderr)
            sys.exit(1)

    # Load and validate configuration
    try:
        if args.configfile is not None:
            config = Config.from_toml(args.configfile)
        else:
            config = Config()
    except FileNotFoundError:
        print(f"✗ Error: Config file not found: {args.configfile}", file=sys.stderr)
        print("\nGenerate an example config with:", file=sys.stderr)
        print(
            f"  python -m discordmanimator --generate-example {args.configfile}",
            file=sys.stderr,
        )
        sys.exit(1)
    except ValidationError as e:
        print("✗ Error: Invalid configuration\n", file=sys.stderr)
        # Print user-friendly error messages
        for error in e.errors():
            loc = " -> ".join(str(loc) for loc in error["loc"])
            print(f"  {loc}: {error['msg']}", file=sys.stderr)
        if args.configfile is not None:
            print(
                "\nPlease fix the errors in your config file or regenerate it with:",
                file=sys.stderr,
            )
            print(
                f"  python -m discordmanimator --generate-example {args.configfile}",
                file=sys.stderr,
            )
        else:
            print(
                "\nSet DISCORDMANIMATOR_TOKEN (and optional DISCORDMANIMATOR_* vars), "
                "or pass a config.toml path.",
                file=sys.stderr,
            )
        sys.exit(1)
    except Exception as e:
        print(f"✗ Error loading config: {e}", file=sys.stderr)
        sys.exit(1)

    # Set global config
    set_config(config)

    if args.configfile is not None:
        print(f"✓ Configuration loaded from {args.configfile}")
    else:
        print("✓ Configuration loaded from environment variables")
    config.print_summary()

    if args.validate_only:
        print("\n✓ Configuration is valid!")
        return

    start_health_server()

    # Create and run the bot
    print("\nStarting bot...")
    manimator_bot = create_and_run_bot()
    manimator_bot.run(config.token.get_secret_value())


if __name__ == "__main__":
    main()
