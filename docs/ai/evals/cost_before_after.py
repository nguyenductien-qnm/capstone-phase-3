#!/usr/bin/env python3
"""Compatibility entry point for the MANDATE-14 evidence history report.

The canonical implementation is aggregate_cost_history.py; this filename is
kept so older repro commands continue to work.
"""

from aggregate_cost_history import main


if __name__ == "__main__":
    main()
