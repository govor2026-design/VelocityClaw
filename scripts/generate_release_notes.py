from __future__ import annotations

from velocity_claw.release_notes import (
    extract_changelog_section,
    generate_release_notes,
    write_release_notes,
)


def main() -> int:
    path = write_release_notes()
    print(f"release notes written: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
