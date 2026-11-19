"""Phase 0 entry point for the Python bulletin board client."""

from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).parent))


def main() -> None:
    print("Bulletin client skeleton (Phase 0).")
    print("Client commands will be implemented in Phase 1.")


if __name__ == "__main__":
    main()
