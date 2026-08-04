#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) PromptKit Contributors

"""Validate universal instruction-fidelity coverage.

This script enforces the repository-wide execution contract:

1. Every template must include `guardrails/instruction-fidelity` in its
   YAML frontmatter.
2. Every template entry in `manifest.yaml` must include the short-name
   protocol `instruction-fidelity`.
3. Critical assembly / packaging files must retain explicit markers that
   preserve instruction-fidelity semantics during bootstrap and output
   generation.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


def parse_yaml_frontmatter(text: str) -> dict[str, object] | None:
    match = re.search(r"^---\s*\n(.*?)\n---", text, re.DOTALL | re.MULTILINE)
    if not match:
        return None

    block = match.group(1)
    protocols: list[str] = []
    in_protocols = False

    for line in block.splitlines():
        stripped = line.strip()
        if stripped.startswith("protocols:"):
            in_protocols = True
            inline = re.search(r"\[(.+)]", stripped)
            if inline:
                protocols = [p.strip().strip("'\"") for p in inline.group(1).split(",")]
                in_protocols = False
            continue
        if in_protocols:
            if stripped.startswith("- "):
                protocols.append(stripped[2:].strip().strip("'\""))
            else:
                in_protocols = False

    return {"protocols": protocols}


def parse_manifest_templates(manifest_text: str) -> dict[str, list[str]]:
    templates: dict[str, list[str]] = {}
    current_name: str | None = None

    for line in manifest_text.splitlines():
        stripped = line.strip()
        name_match = re.match(r"^-\s*name:\s*(.+)", stripped)
        if name_match:
            current_name = name_match.group(1).strip().strip("'\"")
            continue
        if current_name and stripped.startswith("path:"):
            path_val = stripped.split(":", 1)[1].strip().strip("'\"")
            if not path_val.startswith("templates/"):
                current_name = None
            continue
        if current_name and stripped.startswith("protocols:"):
            inline = re.search(r"\[(.+)]", stripped)
            if inline:
                templates[current_name] = [
                    p.strip().strip("'\"") for p in inline.group(1).split(",")
                ]
            current_name = None

    return templates


def validate(repo_root: Path) -> list[str]:
    errors: list[str] = []
    manifest_path = repo_root / "manifest.yaml"
    templates_dir = repo_root / "templates"

    manifest_text = manifest_path.read_text(encoding="utf-8")
    manifest_templates = parse_manifest_templates(manifest_text)

    if "name: instruction-fidelity" not in manifest_text:
        errors.append("manifest.yaml: guardrails section is missing instruction-fidelity")

    for tmpl_file in sorted(templates_dir.glob("*.md")):
        text = tmpl_file.read_text(encoding="utf-8")
        fm = parse_yaml_frontmatter(text)
        if fm is None:
            errors.append(f"{tmpl_file.name}: no YAML frontmatter found")
            continue

        protocols = fm["protocols"]
        if "guardrails/instruction-fidelity" not in protocols:
            errors.append(
                f"{tmpl_file.name}: missing guardrails/instruction-fidelity in frontmatter"
            )

        name_match = re.search(r"^name:\s*(.+)", text.split("---")[1], re.MULTILINE)
        tmpl_name = name_match.group(1).strip().strip("'\"") if name_match else tmpl_file.stem

        manifest_protocols = manifest_templates.get(tmpl_name)
        if manifest_protocols is None:
            errors.append(f"{tmpl_name}: missing from manifest.yaml")
            continue
        if "instruction-fidelity" not in manifest_protocols:
            errors.append(
                f"{tmpl_name}: manifest protocols missing instruction-fidelity"
            )

    critical_markers = {
        "bootstrap.md": [
            "## Instruction Fidelity Contract",
            "If the ambiguity would change template selection, output mode,",
        ],
        "formats/agent-instructions.md": [
            "## Non-Condensable Execution Contract",
            "## Instruction Fidelity Contract",
        ],
        "formats/copilot-prompt-file.md": [
            "Instruction-fidelity content is part of the non-negotiable execution",
            "Preserve the `instruction-fidelity` contract verbatim when present.",
        ],
    }

    for rel_path, markers in critical_markers.items():
        content = (repo_root / rel_path).read_text(encoding="utf-8")
        for marker in markers:
            if marker not in content:
                errors.append(f"{rel_path}: missing marker: {marker}")

    return errors


def main() -> int:
    repo_root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent
    errors = validate(repo_root)

    if errors:
        print(f"FAIL: instruction-fidelity validation failed ({len(errors)} error(s)):\n")
        for err in errors:
            print(f"  - {err}")
        return 1

    print("OK: instruction-fidelity coverage is present across templates and critical formats.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
