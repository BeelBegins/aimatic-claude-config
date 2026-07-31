#!/usr/bin/env python3
"""Audit compact progressive-disclosure guidance without loading runtimes."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

SECRET_ASSIGNMENT = re.compile(
    r"(?i)(password|passwd|secret|token|api[_-]?key)\s*[:=]\s*['\"]([^'\"\n]{4,})['\"]"
)
SAFE_SECRET_VALUES = re.compile(
    r"(?i)^(?:<[^>]+>|\.{3}|x+|example|placeholder|redacted|dummy|changeme|none|null)(?:[-_ ].*)?$"
)
FRONTMATTER = re.compile(r"\A---\n(?P<meta>.*?)\n---\n", re.DOTALL)
MARKDOWN_LINK = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
DATED_OR_NARRATIVE_HEADING = re.compile(
    r"(?im)^#{1,6}\s+.*(?:\b(?:incident|history|historical|archive)\b|20\d{2}-\d{2}-\d{2})"
)

MAX_ROOT_WORDS = 600
MAX_SKILL_BODY_WORDS = 600
MAX_TOTAL_SKILL_BODY_WORDS = 7000

REQUIRED_REFERENCES = {
    "current-state.md",
    "priorities.md",
    "goals.md",
    "known-issues.md",
    "module-catalog.md",
}
REQUIRED_SKILLS = {
    "ai-assistant-console",
    "bench-ops",
    "desk-navigation",
    "erpnext-feature",
    "fbr-integration",
    "foodpanda-integration",
    "ipos-migration",
    "loyalty-gift-voucher",
    "oauth-client-surfaces",
    "offline-pos",
    "posapplication-release",
    "print-format-packaging",
    "purchase-cycle",
    "shelf-pricing",
    "sql-reconciliation",
}
FORBIDDEN_GUIDANCE_NAMES = {
    "project-knowledge-archive-2026-07-28.md",
    "historical-szl-test-fragility.md",
    "historical-site-operations.md",
    "architecture-and-incidents.md",
}
FORBIDDEN_SKILL_NAMES = {
    "release-pos-apk",
    "release-restaurant-apk",
    "release-sales-apk",
    "release-shopping-apk",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--aimatic-root", type=Path)
    parser.add_argument("--pos-root", type=Path)
    return parser.parse_args()


def git_files(root: Path) -> list[Path]:
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z"],
        check=True,
        capture_output=True,
    )
    return [root / name for name in result.stdout.decode().split("\0") if name]


def guidance_files(root: Path) -> list[Path]:
    files = []
    for path in git_files(root):
        if not path.exists() or not path.is_file():
            continue
        relative = path.relative_to(root)
        if (
            relative.parts[:1] in {(".claude",), (".agents",)}
            or path.name in {"CLAUDE.md", "AGENTS.md"}
            or relative.as_posix()
            in {"scripts/audit_ai_guidance.py", "scripts/ai_guidance_cases.json"}
        ):
            files.append(path)
    return files


def parse_frontmatter(path: Path, text: str, errors: list[str]) -> tuple[dict[str, str], str]:
    match = FRONTMATTER.match(text)
    if not match:
        errors.append(f"invalid frontmatter: {path}")
        return {}, text
    metadata = {}
    for line in match.group("meta").splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            metadata[key.strip()] = value.strip()
    return metadata, text[match.end():]


def audit_skills(config: Path, errors: list[str]) -> tuple[set[str], int]:
    skills_root = config / ".claude" / "skills"
    actual: set[str] = set()
    total_body_words = 0

    for skill_dir in sorted(path for path in skills_root.iterdir() if path.is_dir()):
        body_path = skill_dir / "SKILL.md"
        if not body_path.is_file():
            errors.append(f"skill directory missing SKILL.md: {skill_dir}")
            continue
        actual.add(skill_dir.name)
        text = body_path.read_text(encoding="utf-8")
        metadata, body = parse_frontmatter(body_path, text, errors)
        if set(metadata) != {"name", "description"}:
            errors.append(f"frontmatter must contain only name/description: {body_path}")
        if metadata.get("name") != skill_dir.name:
            errors.append(f"skill name/folder mismatch: {body_path}")
        if not metadata.get("description"):
            errors.append(f"empty skill description: {body_path}")

        body_words = len(body.split())
        total_body_words += body_words
        if body_words > MAX_SKILL_BODY_WORDS:
            errors.append(
                f"skill body has {body_words} words; limit is {MAX_SKILL_BODY_WORDS}: {body_path}"
            )
        heading = DATED_OR_NARRATIVE_HEADING.search(body)
        if heading:
            errors.append(f"dated/history heading in skill: {body_path}: {heading.group(0)}")

    if actual != REQUIRED_SKILLS:
        missing = sorted(REQUIRED_SKILLS - actual)
        extra = sorted(actual - REQUIRED_SKILLS)
        errors.append(f"skill catalog mismatch; missing={missing}, extra={extra}")
    if total_body_words > MAX_TOTAL_SKILL_BODY_WORDS:
        errors.append(
            f"skill bodies have {total_body_words} words; limit is {MAX_TOTAL_SKILL_BODY_WORDS}"
        )
    return actual, total_body_words


def audit_routing(config: Path, actual_skills: set[str], errors: list[str]) -> None:
    cases_path = config / "scripts" / "ai_guidance_cases.json"
    if not cases_path.is_file():
        errors.append("routing evaluation cases missing")
        return
    try:
        cases = json.loads(cases_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"routing cases invalid JSON: {exc}")
        return
    if not isinstance(cases, list) or len(cases) < 40:
        errors.append(f"routing cases: expected >=40, found {len(cases) if isinstance(cases, list) else 0}")
        return

    covered: set[str] = set()
    for index, case in enumerate(cases, 1):
        if not isinstance(case, dict) or not {"prompt", "skills", "safety"} <= set(case):
            errors.append(f"routing case {index} missing required keys")
            continue
        skills = case.get("skills")
        if not isinstance(skills, list) or not 1 <= len(skills) <= 2:
            errors.append(f"routing case {index} must name one or two skills")
            continue
        if len(skills) != len(set(skills)):
            errors.append(f"routing case {index} repeats a skill")
        if len(skills) == 2 and case.get("cross_boundary") is not True:
            errors.append(f"routing case {index} needs cross_boundary=true for two skills")
        if len(skills) == 1 and "cross_boundary" in case:
            errors.append(f"routing case {index} marks a single-skill task cross-boundary")
        for skill in skills:
            covered.add(skill)
            if skill not in actual_skills:
                errors.append(f"routing case {index} references missing skill {skill}")

    if covered != actual_skills:
        errors.append(
            f"routing coverage/catalog mismatch; uncovered={sorted(actual_skills - covered)}, "
            f"unknown={sorted(covered - actual_skills)}"
        )


def audit_links_and_retired_files(config: Path, errors: list[str]) -> None:
    guidance_root = config / ".claude"
    for path in guidance_root.rglob("*"):
        if not path.is_file():
            continue
        lowered = path.name.lower()
        if lowered in FORBIDDEN_GUIDANCE_NAMES or re.search(r"(?:historical|archive|incidents?)", lowered):
            errors.append(f"retired narrative guidance file exists: {path}")

    retired_tokens = FORBIDDEN_GUIDANCE_NAMES | FORBIDDEN_SKILL_NAMES
    markdown = [config / "CLAUDE.md", *guidance_root.rglob("*.md")]
    for path in markdown:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for token in retired_tokens:
            if token in text:
                errors.append(f"retired guidance reference {token}: {path}")
        for raw_target in MARKDOWN_LINK.findall(text):
            target = raw_target.strip().strip("<>").split("#", 1)[0]
            target = target.split(" ", 1)[0]
            if not target or re.match(r"^[a-z][a-z0-9+.-]*:", target, re.I) or target.startswith("/"):
                continue
            resolved = (path.parent / target).resolve()
            if not resolved.exists():
                errors.append(f"broken local link in {path}: {raw_target}")


def audit_config(config: Path, errors: list[str]) -> None:
    root_guide = config / "CLAUDE.md"
    if not root_guide.is_file():
        errors.append("CLAUDE.md missing")
        return
    root_text = root_guide.read_text(encoding="utf-8")
    root_words = len(root_text.split())
    if root_words > MAX_ROOT_WORDS:
        errors.append(f"CLAUDE.md has {root_words} words; limit is {MAX_ROOT_WORDS}")
    if not (config / "AGENTS.md").is_symlink():
        errors.append("AGENTS.md must symlink to CLAUDE.md")
    if not (config / ".agents" / "skills").is_symlink():
        errors.append(".agents/skills must symlink to .claude/skills")

    reference_root = config / ".claude" / "reference"
    existing_references = {path.name for path in reference_root.glob("*.md")}
    if existing_references != REQUIRED_REFERENCES:
        errors.append(
            f"reference catalog mismatch; missing={sorted(REQUIRED_REFERENCES - existing_references)}, "
            f"extra={sorted(existing_references - REQUIRED_REFERENCES)}"
        )
    normalized_root = " ".join(root_text.split())
    for phrase in (
        "current local code, configuration, and uncommitted diff",
        "explicit approval",
        "2,000 transactions",
        "purchase-cycle",
        "Every push to Posapplication `main`",
        "PKCE",
        "rollback path",
    ):
        if phrase not in normalized_root:
            errors.append(f"root invariant missing: {phrase}")

    current_path = reference_root / "current-state.md"
    if current_path.is_file():
        current = current_path.read_text(encoding="utf-8")
        if "not yet live" not in current or "Last human-confirmed:" not in current:
            errors.append("current-state lacks dated SZL not-live designation")

    actual_skills, total_body_words = audit_skills(config, errors)
    audit_routing(config, actual_skills, errors)
    audit_links_and_retired_files(config, errors)
    print(f"root: {root_words} words")
    print(f"skill bodies: {len(actual_skills)} skills, {total_body_words} words")


def audit_migrations(aimatic: Path, config: Path, errors: list[str]) -> None:
    migration_root = aimatic / "ipos_data_migration"
    if not migration_root.is_dir():
        errors.append(f"migration directory missing: {migration_root}")
        return
    files = [
        path for path in migration_root.iterdir()
        if path.suffix in {".py", ".md"} and path.name not in {"AGENTS.md", "CLAUDE.md"}
    ]
    if not files:
        errors.append("migration inventory is empty")
    if "ipos_data_migration/" not in (config / ".claude/reference/module-catalog.md").read_text():
        errors.append("module catalog does not own ipos_data_migration")
    print(f"migration inventory: {len(files)} tracked source/runbook files")


def audit_secrets(roots: list[Path], errors: list[str]) -> None:
    seen: set[Path] = set()
    for root in roots:
        if not root.exists():
            continue
        for path in guidance_files(root):
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for match in SECRET_ASSIGNMENT.finditer(text):
                if not SAFE_SECRET_VALUES.match(match.group(2).strip()):
                    errors.append(f"possible literal secret: {path}")
                    break


def main() -> int:
    args = parse_args()
    config = args.config_root.resolve()
    errors: list[str] = []
    audit_config(config, errors)
    roots = [config]
    if args.aimatic_root:
        aimatic = args.aimatic_root.resolve()
        roots.append(aimatic)
        audit_migrations(aimatic, config, errors)
    if args.pos_root:
        roots.append(args.pos_root.resolve())
    audit_secrets(roots, errors)
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    if errors:
        print(f"guidance audit failed: {len(errors)} error(s)", file=sys.stderr)
        return 1
    print("guidance audit passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
