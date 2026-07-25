"""Command-line entry point for the VEGAS always-on daemon."""

from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path

from .launchagent import MacOSLaunchAgent
from .runtime import VegasDaemon, VegasDaemonConfig, configure_logging


def _project_root(value: str | None) -> Path:
    return Path(value).expanduser().resolve() if value else Path.cwd().resolve()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="VEGAS always-on macOS daemon")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run the daemon in the foreground.")
    run_parser.add_argument("--project-root", help="Path to the VEGAS repository.")

    for command, help_text in (
        ("install", "Install the macOS LaunchAgent and start it."),
        ("uninstall", "Stop and remove the macOS LaunchAgent."),
        ("start", "Start an installed macOS LaunchAgent."),
        ("stop", "Gracefully stop an installed macOS LaunchAgent."),
        ("status", "Print macOS LaunchAgent status."),
    ):
        subparser = subparsers.add_parser(command, help=help_text)
        subparser.add_argument("--project-root", help="Path to the VEGAS repository.")
        if command == "install":
            subparser.add_argument("--no-start", action="store_true", help="Install without loading the agent.")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    project_root = _project_root(getattr(args, "project_root", None))

    if args.command == "run":
        configure_logging()
        daemon = VegasDaemon(VegasDaemonConfig.from_environment(project_root))
        try:
            asyncio.run(daemon.run_forever())
        except KeyboardInterrupt:
            logging.getLogger(__name__).info("VEGAS daemon interrupted.")
        return 0

    agent = MacOSLaunchAgent(project_root)
    if args.command == "install":
        plist_path = agent.install(start=not args.no_start)
        print(f"Installed VEGAS LaunchAgent: {plist_path}")
    elif args.command == "uninstall":
        agent.uninstall()
        print("Removed VEGAS LaunchAgent.")
    elif args.command == "start":
        agent.start()
        print("Started VEGAS LaunchAgent.")
    elif args.command == "stop":
        agent.stop()
        print("Stopped VEGAS LaunchAgent.")
    elif args.command == "status":
        print(agent.status())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
