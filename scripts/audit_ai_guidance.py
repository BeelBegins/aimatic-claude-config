#!/usr/bin/env python3
"""Audit progressive-disclosure guidance without loading project runtimes."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

SECRET_ASSIGNMENT = re.compile(
    r"(?i)(password|passwd|secret|token|api[_-]?key)\s*[:=]\s*['\"][^'\"\n]{4,}['\"]"
)
FRONTMATTER = re.compile(r"\A---\n(?P<meta>.*?)\n---\n", re.DOTALL)
REQUIRED_REFERENCES = (
    "current-state.md",
    "priorities.md",
    "known-issues.md",
    "module-catalog.md",
    "project-knowledge-archive-2026-07-28.md",
)
REQUIRED_SKILLS = (
    "ai-assistant-console",
    "bench-ops",
    "erpnext-feature",
    "fbr-integration",
    "ipos-migration",
    "offline-pos",
    "oauth-client-surfaces",
    "posapplication-release",
    "purchase-cycle",
    "shelf-pricing",
    "sql-reconciliation",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--aimatic-root", type=Path)
    parser.add_argument("--pos-root", type=Path)
    parser.add_argument("--max-root-lines", type=int, default=200)
    return parser.parse_args()


def tracked_text_files(root: Path):
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z"],
        check=True,
        capture_output=True,
    )
    for relative in result.stdout.decode().split("\0"):
        if relative and Path(relative).suffix in {".md", ".py", ".json", ".yml", ".yaml"}:
            yield root / relative


def audit_skills(config: Path, errors: list[str]) -> tuple[int, int]:
    skills_root = config / ".claude" / "skills"
    total_lines = 0
    total_words = 0
    for skill_dir in sorted(path for path in skills_root.iterdir() if path.is_dir()):
        body = skill_dir / "SKILL.md"
        if not body.is_file():
            errors.append(f"missing SKILL.md: {skill_dir}")
            continue
        text = body.read_text(encoding="utf-8")
        total_lines += len(text.splitlines())
        total_words += len(text.split())
        match = FRONTMATTER.match(text)
        if not match:
            errors.append(f"invalid frontmatter: {body}")
            continue
        metadata = {}
        for line in match.group("meta").splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                metadata[key.strip()] = value.strip()
        if set(metadata) != {"name", "description"}:
            errors.append(f"frontmatter must contain only name/description: {body}")
        if metadata.get("name") != skill_dir.name:
            errors.append(f"skill name/folder mismatch: {body}")
        if not metadata.get("description"):
            errors.append(f"empty skill description: {body}")
    for name in REQUIRED_SKILLS:
        if not (skills_root / name / "SKILL.md").is_file():
            errors.append(f"required skill missing: {name}")
    return total_lines, total_words


def audit_config(config: Path, errors: list[str], warnings: list[str], max_lines: int) -> None:
    root_guide = config / "CLAUDE.md"
    if not root_guide.is_file():
        errors.append("CLAUDE.md missing")
        return
    root_text = root_guide.read_text(encoding="utf-8")
    root_lines = len(root_text.splitlines())
    if root_lines > max_lines:
        errors.append(f"CLAUDE.md has {root_lines} lines; limit is {max_lines}")
    if not (config / "AGENTS.md").is_symlink():
        errors.append("AGENTS.md must symlink to CLAUDE.md")
    codex_skills = config / ".agents" / "skills"
    if not codex_skills.is_symlink():
        errors.append(".agents/skills must symlink to .claude/skills")
    reference_root = config / ".claude" / "reference"
    for name in REQUIRED_REFERENCES:
        if not (reference_root / name).is_file():
            errors.append(f"required reference missing: {name}")
    normalized_root = " ".join(root_text.split())
    for required_phrase in (
        "local code, configuration, and uncommitted diff",
        "explicit approval",
        "2,000 transactions",
        "purchase-cycle",
        "every push to `main`",
    ):
        if required_phrase not in normalized_root:
            errors.append(f"root invariant missing: {required_phrase}")
    current = (reference_root / "current-state.md").read_text(encoding="utf-8")
    if "not yet live" not in current or "Last human-confirmed:" not in current:
        errors.append("current-state lacks dated SZL not-live designation")
    skill_lines, skill_words = audit_skills(config, errors)
    cases_path = config / "scripts" / "ai_guidance_cases.json"
    if not cases_path.is_file():
        errors.append("routing evaluation cases missing")
    else:
        cases = json.loads(cases_path.read_text(encoding="utf-8"))
        if len(cases) < 40:
            errors.append(f"routing cases: expected >=40, found {len(cases)}")
        for index, case in enumerate(cases, 1):
            if not {"prompt", "skills", "safety"} <= set(case):
                errors.append(f"routing case {index} missing required keys")
            for skill in case.get("skills", []):
                if not (config / ".claude" / "skills" / skill / "SKILL.md").is_file():
                    errors.append(f"routing case {index} references missing skill {skill}")
    print(f"root: {root_lines} lines, {len(root_text.split())} words")
    print(f"skill routers: {skill_lines} lines, {skill_words} words")


def audit_migrations(aimatic: Path, config: Path, errors: list[str], warnings: list[str]) -> None:
    migration_root = aimatic / "ipos_data_migration"
    if not migration_root.is_dir():
        errors.append(f"migration directory missing: {migration_root}")
        return
    files = sorted(path for path in migration_root.iterdir() if path.suffix in {".py", ".md"} and path.name not in {"AGENTS.md", "CLAUDE.md"})
    if not files:
        errors.append("migration inventory is empty")
    if "ipos_data_migration/" not in (config / ".claude/reference/module-catalog.md").read_text():
        errors.append("module catalog does not own ipos_data_migration")
    print(f"migration inventory: {len(files)} tracked source/runbook files")


def audit_secrets(roots: list[Path], errors: list[str]) -> None:
    excluded = {"project-knowledge-archive-2026-07-28.md"}
    for root in roots:
        if not root or not root.exists():
            continue
        for path in tracked_text_files(root):
            if (
                path.name in excluded
                or path.name.startswith("test_")
                or path.name == "README.md"
                or any(part in {"node_modules", ".git", "dist", "build", "tests"} for part in path.parts)
            ):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            if SECRET_ASSIGNMENT.search(text):
                errors.append(f"possible literal secret: {path}")


def main() -> int:
    args = parse_args()
    config = args.config_root.resolve()
    errors: list[str] = []
    warnings: list[str] = []
    audit_config(config, errors, warnings, args.max_root_lines)
    roots = [config]
    if args.aimatic_root:
        aimatic = args.aimatic_root.resolve()
        roots.append(aimatic)
        audit_migrations(aimatic, config, errors, warnings)
    if args.pos_root:
        roots.append(args.pos_root.resolve())
    audit_secrets(roots, errors)
    for warning in warnings:
        print(f"WARNING: {warning}")
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    if errors:
        print(f"guidance audit failed: {len(errors)} error(s)", file=sys.stderr)
        return 1
    print("guidance audit passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
