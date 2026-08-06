"""__main__.py — allow ``python3 -m dag_inspector ...``."""

from .cli import main


if __name__ == "__main__":
    raise SystemExit(main())