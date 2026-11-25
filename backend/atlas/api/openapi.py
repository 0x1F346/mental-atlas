"""Write the API's OpenAPI schema to a file. The web client's types are generated from it."""

import json
import sys
from pathlib import Path

from atlas.api.app import create_app


def main() -> int:
    target = Path(sys.argv[1])
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(create_app().openapi(), indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
