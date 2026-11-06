"""Validate a skill-card manifest against the C-02 card rules.

Standard library only (the JSON Schema in this directory is the
normative document; this validator enforces the same rules without a
schema dependency):

- required sections: card / tools / gate
- card identity fields present, id and version well-formed
- every tool declares exactly one tier in {read, draft, send}
- gate.send_requires_human_approval is true (a card that opts out of
  human approval for sends is not a conforming card)
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

TIERS = ("read", "draft", "send")
_ID = re.compile(r"^[a-z0-9][a-z0-9-]{2,63}$")
_VER = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")


def validate(manifest: dict) -> list[str]:
    errors: list[str] = []
    if not isinstance(manifest, dict):
        return ["manifest is not a JSON object"]
    card = manifest.get("card")
    if not isinstance(card, dict):
        errors.append("missing 'card' section")
    else:
        for key in ("id", "name", "version", "author", "description", "entry"):
            if not card.get(key):
                errors.append(f"card.{key} is required")
        if card.get("id") and not _ID.match(str(card["id"])):
            errors.append("card.id must be lowercase slug, 3-64 chars")
        if card.get("version") and not _VER.match(str(card["version"])):
            errors.append("card.version must be semver (x.y.z)")
    tools = manifest.get("tools")
    if not isinstance(tools, dict) or not tools:
        errors.append("'tools' must declare at least one tool")
    else:
        for name, spec in tools.items():
            if not isinstance(spec, dict) or spec.get("tier") not in TIERS:
                errors.append(f"tool {name!r} must declare tier in {TIERS}")
    gate = manifest.get("gate")
    if not isinstance(gate, dict):
        errors.append("missing 'gate' section")
    elif gate.get("send_requires_human_approval") is not True:
        errors.append("gate.send_requires_human_approval must be true")
    return errors


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: validate_card.py <card.json>", file=sys.stderr)
        return 2
    try:
        manifest = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"invalid: cannot read manifest: {exc}")
        return 1
    errors = validate(manifest)
    if errors:
        for err in errors:
            print(f"invalid: {err}")
        return 1
    print(f"valid: {manifest['card']['id']} v{manifest['card']['version']} "
          f"({len(manifest['tools'])} tools declared)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
