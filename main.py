#!/usr/bin/env python3
"""RHOAI Amplitude Dashboard — Customer Profiles Report Generator.

Generates interactive HTML reports showing RHOAI customer adoption
stages, feature usage, serving runtimes, and 12-month usage trends
from Amplitude product analytics data.

Usage:
    python main.py report --open
    python main.py report --days 90 --output my-report.html
    python main.py list
    python main.py backfill
"""

import click

from src.commands.amplitude_cmd import amplitude_group


@click.group()
def cli():
    """RHOAI Customer Profiles Dashboard — Amplitude Analytics."""
    pass


# Register all amplitude commands at the top level
for cmd_name, cmd in amplitude_group.commands.items():
    cli.add_command(cmd, name=cmd_name)


if __name__ == "__main__":
    cli()
