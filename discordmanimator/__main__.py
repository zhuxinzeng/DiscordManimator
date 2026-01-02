"""Entry point for DiscordManimator bot."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pydantic import ValidationError

from .config import Config, set_config
from .DiscordManimator import create_and_run_bot


def main() -> None:
    """Main entry point for the bot."""
    parser = argparse.ArgumentParser(
        prog="DiscordManimator",
        description="Discord bot for rendering Manim animations",
    )
    parser.add_argument(
        "configfile",
        help="Path to the TOML configuration file",
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
        try:
            # Create config with dummy token to get defaults
            dummy_config = Config(
                token="irrelevant and just needs to be long enough to pass validation"
            )
            dummy_config.save_example(args.configfile)
            print(f"✓ Example configuration saved to: {args.configfile}")
            print(
                "\nEdit the file and replace 'paste_your_bot_token_here' with your actual token."
            )
            print("You can get a token from: https://discord.com/developers/applications")
            return
        except Exception as e:
            print(f"✗ Error generating example: {e}", file=sys.stderr)
            sys.exit(1)

    # Load and validate configuration
    try:
        config = Config.from_toml(args.configfile)
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
        print(
            "\nPlease fix the errors in your config file or regenerate it with:",
            file=sys.stderr,
        )
        print(
            f"  python -m discordmanimator --generate-example {args.configfile}",
            file=sys.stderr,
        )
        sys.exit(1)
    except Exception as e:
        print(f"✗ Error loading config: {e}", file=sys.stderr)
        sys.exit(1)

    # Set global config
    set_config(config)

    print(f"✓ Configuration loaded from {args.configfile}")
    config.print_summary()

    if args.validate_only:
        print("\n✓ Configuration is valid!")
        return

    # Create and run the bot
    print("\nStarting bot...")
    manimator_bot = create_and_run_bot()
    manimator_bot.run(config.token.get_secret_value())


if __name__ == "__main__":
    main()
