"""Tests for the oss-steward skill and documentation references."""

import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = REPO_ROOT / "skills" / "oss-steward"
REFERENCES_DIR = SKILL_DIR / "references"


def test_oss_steward_skill_frontmatter() -> None:
    """The oss-steward skill entrypoint has valid YAML frontmatter."""
    skill_file = SKILL_DIR / "SKILL.md"
    assert skill_file.is_file(), f"Missing {skill_file}"

    content = skill_file.read_text(encoding="utf-8")
    parts = content.split("---", 2)
    assert len(parts) >= 3, "SKILL.md must have YAML frontmatter enclosed in '---'"

    frontmatter = yaml.safe_load(parts[1])
    assert isinstance(frontmatter, dict)
    assert frontmatter.get("name") == "oss-steward"
    assert "description" in frontmatter
    assert len(frontmatter["description"].strip()) > 20


def test_oss_steward_references_exist_and_linked() -> None:
    """All linked reference guides in SKILL.md exist on disk."""
    skill_file = SKILL_DIR / "SKILL.md"
    content = skill_file.read_text(encoding="utf-8")

    expected_refs = [
        "references/dependency-upgrades.md",
        "references/external-contributions.md",
        "references/bug-reports.md",
        "references/feature-requests.md",
        "references/companion-tools.md",
    ]

    for ref in expected_refs:
        assert ref in content, f"SKILL.md does not reference {ref}"
        ref_file = SKILL_DIR / ref
        assert ref_file.is_file(), f"Reference file {ref_file} does not exist"
        assert len(ref_file.read_text(encoding="utf-8").strip()) > 100


def test_no_broken_relative_links_in_skill_docs() -> None:
    """All relative markdown links within SKILL.md and references/ resolve to valid files."""
    link_pattern = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")

    files_to_check = [SKILL_DIR / "SKILL.md"] + list(REFERENCES_DIR.glob("*.md"))
    for md_file in files_to_check:
        text = md_file.read_text(encoding="utf-8")
        for match in link_pattern.finditer(text):
            url = match.group(2)
            # Skip web URLs and in-page anchor links
            if url.startswith(("http://", "https://", "#", "mailto:")):
                continue
            # Remove any fragment from relative file link
            target_path_str = url.split("#")[0]
            if not target_path_str:
                continue
            resolved = (md_file.parent / target_path_str).resolve()
            assert resolved.exists(), f"Broken link '{url}' in {md_file.name} -> {resolved}"


def test_readme_maintainer_walkthrough() -> None:
    """README.md contains the maintainer walkthrough and references the stewardship skill."""
    readme_file = REPO_ROOT / "README.md"
    assert readme_file.is_file()
    content = readme_file.read_text(encoding="utf-8")

    assert "## Maintain your first repository" in content
    assert "skills/oss-steward/SKILL.md" in content
    assert "gh-beads-snapshot" in content
    assert "gh-beads-triage" in content
    assert "receipt:" in content


def test_skill_discovery_and_content() -> None:
    """The skill module lists skills and extracts content and references properly."""
    from gh_beads.skill import (
        consolidate_skill,
        get_reference_content,
        get_skill_content,
        list_skills,
    )

    skills = list_skills()
    assert len(skills) >= 1
    oss_skill = next((s for s in skills if s["name"] == "oss-steward"), None)
    assert oss_skill is not None
    assert "Open-source maintainer" in oss_skill["description"]
    assert "bug-reports.md" in oss_skill["references"]

    content = get_skill_content("oss-steward")
    assert "Prompt Injection Defense" in content

    ref_content = get_reference_content("oss-steward", "bug-reports.md")
    assert "Bug Reports Stewardship Guide" in ref_content

    consolidated = consolidate_skill("oss-steward")
    assert "Prompt Injection Defense" in consolidated
    assert "Appendix: Inlined Domain References" in consolidated
    assert "Reference: Bug Reports" in consolidated


def test_install_skill_custom_and_collision(tmp_path: Path) -> None:
    """Installation respects collision preflight and overwrites when requested."""
    import pytest

    from gh_beads.skill import install_skill

    target_dir = tmp_path / "custom-dest"
    res1 = install_skill("oss-steward", target="custom", custom_dest=target_dir)
    assert res1["status"] == "success"
    assert (target_dir / "oss-steward" / "SKILL.md").is_file()

    # Re-install without overwrite should raise ValueError
    with pytest.raises(ValueError, match="already exists"):
        install_skill("oss-steward", target="custom", custom_dest=target_dir)

    # With overwrite=True, it succeeds
    res2 = install_skill("oss-steward", target="custom", custom_dest=target_dir, overwrite=True)
    assert res2["status"] == "success"


def test_install_skill_all_targets(tmp_path: Path) -> None:
    """The 'all' target installs into .agents, .claude, .cursor, and .github in one call."""
    from gh_beads.skill import install_skill

    res = install_skill("oss-steward", target="all", base_dir=tmp_path)
    assert res["status"] == "success"

    assert (tmp_path / ".agents" / "skills" / "oss-steward" / "SKILL.md").is_file()
    assert (tmp_path / ".claude" / "skills" / "oss-steward" / "SKILL.md").is_file()
    assert (tmp_path / ".cursor" / "rules" / "oss-steward.mdc").is_file()
    assert (tmp_path / ".github" / "copilot-instructions.md").is_file()

    # Verify Cursor rule content
    cursor_rule = (tmp_path / ".cursor" / "rules" / "oss-steward.mdc").read_text(encoding="utf-8")
    assert "alwaysApply: false" in cursor_rule
    assert "Prompt Injection Defense" in cursor_rule
