#!/usr/bin/env python3
"""
SoccerSolver - Main Entrypoint
"""

import sys
from soccersolver.cli import cli

if __name__ == "__main__":
    if len(sys.argv) == 1:
        # Default with no args: run solve demo and instructions
        from click.testing import CliRunner
        print("SoccerSolver Decision Engine")
        print("Usage: python main.py [COMMAND]")
        print("Commands: solve, backtest, trigger, queue, logs, web")
        print("\nRunning default solver demo...\n")
        cli.main(args=["solve"])
    else:
        cli()
