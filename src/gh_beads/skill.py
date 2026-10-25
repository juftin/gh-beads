"""Discover, inspect, package, and install the oss-steward maintainer skill."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

DEFAULT_SKILL = "oss-steward"
SUPPORTED_TARGETS = ("workspace", "global", "claude", "cursor", "copilot", "all", "custom")


def get_skill_base_dir() -> Path:
    """Locate the root directory containing packaged or checkout skills."""
    packaged = Path(__file__).parent / "skills"
    if packaged.is_dir():
        return packaged
    checkout_skills = Path(__file__).resolve().parents[2] / "skills"
    if checkout_skills.is_dir():
        return checkout_skills
    agents_skills = Path(__file__).resolve().parents[2] / ".agents" / "skills"
    if agents_skills.is_dir():
        return agents_skills
    raise FileNotFoundError("Could not find skills directory in package or repository root.")


def get_skill_dir(skill_name: str = DEFAULT_SKILL) -> Path:
    """Return the absolute directory for a specific skill."""
    base = get_skill_base_dir()
    skill_path = base / skill_name
    if not skill_path.is_dir() or not (skill_path / "SKILL.md").is_file():
        raise FileNotFoundError(f"Skill '{skill_name}' not found at {skill_path}")
    return skill_path


def parse_frontmatter(content: str) -> dict[str, Any]:
    """Extract YAML frontmatter fields from a SKILL.md file without external dependencies."""
    if not content.startswith("---"):
        return {}
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}
    frontmatter_text = parts[1]
    result: dict[str, Any] = {}
    current_key: str | None = None
    multiline_val: list[str] = []

    for line in frontmatter_text.splitlines():
        line = line.rstrip()
        if not line or line.startswith("#"):
            continue
        if ":" in line and not line.startswith(" "):
            if current_key and multiline_val:
                result[current_key] = " ".join("".join(multiline_val).split())
                multiline_val = []
            key, val = line.split(":", 1)
            current_key = key.strip()
            val_clean = val.strip()
            if val_clean in (">-", ">", "|", "|-"):
                multiline_val = []
            else:
                result[current_key] = val_clean
        elif current_key and (line.startswith(" ") or line.startswith("\t")):
            multiline_val.append(line.strip())

    if current_key and multiline_val:
        result[current_key] = " ".join("".join(multiline_val).split())

    return result


def list_skills() -> list[dict[str, Any]]:
    """List all available skills with descriptions and reference listings."""
    base = get_skill_base_dir()
    skills: list[dict[str, Any]] = []

    for entry in sorted(base.iterdir()):
        skill_md = entry / "SKILL.md"
        if entry.is_dir() and skill_md.is_file():
            content = skill_md.read_text(encoding="utf-8")
            meta = parse_frontmatter(content)
            refs_dir = entry / "references"
            references = sorted(p.name for p in refs_dir.glob("*.md")) if refs_dir.is_dir() else []
            skills.append(
                {
                    "name": meta.get("name", entry.name),
                    "description": meta.get("description", ""),
                    "path": str(skill_md),
                    "directory": str(entry),
                    "references": references,
                }
            )
    return skills


def get_skill_content(skill_name: str = DEFAULT_SKILL) -> str:
    """Read the raw markdown content of a skill's SKILL.md."""
    skill_dir = get_skill_dir(skill_name)
    return (skill_dir / "SKILL.md").read_text(encoding="utf-8")


def get_reference_content(skill_name: str, reference_name: str) -> str:
    """Read the content of a reference file belonging to a skill."""
    skill_dir = get_skill_dir(skill_name)
    # Ensure reference name doesn't perform directory traversal
    safe_name = Path(reference_name).name
    if not safe_name.endswith(".md"):
        safe_name = f"{safe_name}.md"
    ref_path = skill_dir / "references" / safe_name
    if not ref_path.is_file():
        raise FileNotFoundError(f"Reference '{safe_name}' not found for skill '{skill_name}'")
    return ref_path.read_text(encoding="utf-8")


def consolidate_skill(skill_name: str = DEFAULT_SKILL) -> str:
    """Combine SKILL.md and all references into a single standalone markdown document."""
    skill_dir = get_skill_dir(skill_name)
    main_text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")

    refs_dir = skill_dir / "references"
    if not refs_dir.is_dir():
        return main_text

    sections = [main_text, "\n\n---\n# Appendix: Inlined Domain References\n"]
    for ref_file in sorted(refs_dir.glob("*.md")):
        ref_title = ref_file.stem.replace("-", " ").title()
        ref_body = ref_file.read_text(encoding="utf-8")
        sections.append(f"\n## Reference: {ref_title}\n\n{ref_body}\n")

    return "\n".join(sections)


def _copy_directory_contents(src: Path, dst: Path, overwrite: bool) -> list[str]:
    """Copy all files from src to dst; fails if destination exists without overwrite."""
    installed: list[str] = []
    if dst.exists():
        if not overwrite:
            raise ValueError(f"Destination '{dst}' already exists. Pass overwrite=True to update.")
        if dst.is_dir():
            shutil.rmtree(dst)
        else:
            dst.unlink()

    dst.mkdir(parents=True, exist_ok=True)

    for item in src.rglob("*"):
        if item.is_file():
            rel = item.relative_to(src)
            target = dst / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, target)
            installed.append(str(target))

    return installed


def install_skill(
    skill_name: str = DEFAULT_SKILL,
    target: str = "workspace",
    base_dir: Path | None = None,
    custom_dest: Path | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Install a skill into designated agent directories (workspace, global, claude, etc.)."""
    src_dir = get_skill_dir(skill_name)
    base = (base_dir or Path(os.environ.get("BEADS_WORKING_DIR", "."))).resolve()

    installed_paths: list[str] = []
    actions_taken: list[str] = []

    if target in ("workspace", "agents"):
        dest = base / ".agents" / "skills" / skill_name
        files = _copy_directory_contents(src_dir, dest, overwrite)
        installed_paths.extend(files)
        actions_taken.append(f"Installed {skill_name} to .agents/skills/{skill_name}")

    elif target == "global":
        home = Path.home()
        global_targets = [
            home / ".gemini" / "antigravity-cli" / "skills" / skill_name,
            home / ".agents" / "skills" / skill_name,
        ]
        for g_dest in global_targets:
            try:
                files = _copy_directory_contents(src_dir, g_dest, overwrite)
                installed_paths.extend(files)
                actions_taken.append(f"Installed {skill_name} to {g_dest}")
            except Exception as exc:  # noqa: BLE001
                # If one global path fails permissions, continue with others
                actions_taken.append(f"Failed global install to {g_dest}: {exc}")

    elif target == "claude":
        dest = base / ".claude" / "skills" / skill_name
        files = _copy_directory_contents(src_dir, dest, overwrite)
        installed_paths.extend(files)
        actions_taken.append(f"Installed {skill_name} to .claude/skills/{skill_name}")

    elif target == "cursor":
        dest_dir = base / ".cursor" / "rules"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_file = dest_dir / f"{skill_name}.mdc"
        if dest_file.exists() and not overwrite:
            raise ValueError(f"Destination '{dest_file}' already exists. Pass overwrite=True.")

        consolidated = consolidate_skill(skill_name)
        cursor_content = (
            f"---\ndescription: Open-source maintainer stewardship skill using gh-beads\n"
            f"globs: *\nalwaysApply: false\n---\n\n{consolidated}"
        )
        dest_file.write_text(cursor_content, encoding="utf-8")
        installed_paths.append(str(dest_file))
        actions_taken.append(
            f"Installed {skill_name} Cursor rule to .cursor/rules/{skill_name}.mdc"
        )

    elif target == "copilot":
        dest_dir = base / ".github"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_file = dest_dir / "copilot-instructions.md"
        if dest_file.exists() and not overwrite:
            raise ValueError(f"Destination '{dest_file}' already exists. Pass overwrite=True.")

        consolidated = consolidate_skill(skill_name)
        dest_file.write_text(consolidated, encoding="utf-8")
        installed_paths.append(str(dest_file))
        actions_taken.append(f"Installed {skill_name} to .github/copilot-instructions.md")

    elif target == "all":
        # Install to workspace, claude, cursor, and copilot
        for sub_target in ("workspace", "claude", "cursor", "copilot"):
            sub_res = install_skill(
                skill_name=skill_name,
                target=sub_target,
                base_dir=base,
                overwrite=overwrite,
            )
            installed_paths.extend(sub_res.get("installed_paths", []))
            actions_taken.extend(sub_res.get("actions", []))

    elif target == "custom":
        if not custom_dest:
            raise ValueError("custom_dest is required when target='custom'")
        dest = custom_dest.resolve()
        if dest.name != skill_name:
            dest = dest / skill_name
        files = _copy_directory_contents(src_dir, dest, overwrite)
        installed_paths.extend(files)
        actions_taken.append(f"Installed {skill_name} to {dest}")

    else:
        targets_str = ", ".join(SUPPORTED_TARGETS)
        raise ValueError(f"Unsupported target '{target}'. Supported: {targets_str}")

    return {
        "status": "success",
        "skill": skill_name,
        "target": target,
        "installed_paths": installed_paths,
        "actions": actions_taken,
    }
