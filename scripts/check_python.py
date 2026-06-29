"""Helper for Windows .bat: exit 0 when Python is 3.10+."""
import sys

raise SystemExit(0 if sys.version_info >= (3, 10) else 1)
