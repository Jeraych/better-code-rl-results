"""Create a unique research run directory and provenance manifest."""

from __future__ import annotations

import argparse

from common import initialize_run


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_id")
    args = parser.parse_args()
    print(initialize_run(args.run_id))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
