from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from velocity_claw.package_validation import validate_package


def main() -> int:
    try:
        result = validate_package(ROOT)
    except Exception as exc:
        print(f"package validation failed: {exc}", file=sys.stderr)
        return 1
    print(f"package validation ok: {result['name']} {result['version']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
