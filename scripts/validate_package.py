from __future__ import annotations

import sys

from velocity_claw.package_validation import validate_package


def main() -> int:
    try:
        result = validate_package()
    except Exception as exc:
        print(f"package validation failed: {exc}", file=sys.stderr)
        return 1
    print(f"package validation ok: {result['name']} {result['version']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
