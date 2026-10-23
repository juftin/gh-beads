"""Exercise the optional deployment boundary without downloading or starting services."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/doltlab.sh"


@pytest.fixture
def deployment(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    """Provide synthetic credentials and isolated fake upstream/Docker executables."""
    directory = tmp_path / "doltlab"
    directory.mkdir()
    tools = tmp_path / "bin"
    tools.mkdir()
    env = {
        "PATH": f"{tools}:{os.defpath}",
        "DOLTLAB_DIR": str(directory),
        "DOLTLAB_HOST": "doltlab.example.test",
        "DOLT_ADMIN_PASSWORD": "synthetic-admin-'$",
        "DOLT_DOLTHUBAPI_PASSWORD": "synthetic-api-'$",
        "DEFAULT_USER_PASSWORD": "synthetic-login-'$",
        "COMPOSE_PROJECT_NAME": "existing-hub",
        "COMPOSE_FILE": "hub.yaml",
        "COMPOSE_PROFILES": "unrelated",
        "COMPOSE_ENV_FILES": "unrelated.env",
    }
    installer = directory / "installer"
    installer.write_text(
        f"#!{sys.executable}\n"
        "import json, os, pathlib, sys\n"
        "p = pathlib.Path('.')\n"
        "with (p / 'installer-calls.jsonl').open('a') as log:\n"
        "    log.write(json.dumps(sys.argv[1:]) + '\\n')\n"
        "if os.environ.get('FAIL_INSTALLER'): sys.exit(1)\n"
        "(p / 'docker-compose.yaml').write_text('services: {}\\n')\n"
        "(p / 'synthetic.keys').write_text('keep-this-key')\n"
    )
    installer.chmod(0o700)
    (directory / ".gh-beads-release").write_text("v2.6.3\n")
    docker = tools / "docker"
    docker.write_text(
        f"#!{sys.executable}\n"
        "import json, os, pathlib, sys\n"
        "with pathlib.Path('docker-calls.jsonl').open('a') as log:\n"
        "    log.write(json.dumps({'args': sys.argv[1:], 'cwd': os.getcwd(), 'env': {\n"
        "        k: v for k, v in os.environ.items() if k.startswith('COMPOSE_')\n"
        "    }}) + '\\n')\n"
        "if os.environ.get('FAIL_VALIDATE') and sys.argv[-2:] == ['config', '--quiet']:\n"
        "    sys.exit(1)\n"
        "if sys.argv[1:3] == ['network', 'inspect']: sys.exit(1)\n"
    )
    docker.chmod(0o700)
    uname = tools / "uname"
    uname.write_text('#!/bin/sh\ncase "$1" in -s) echo Linux;; -m) echo x86_64;; esac\n')
    uname.chmod(0o700)
    return directory, env


def run(env: dict[str, str], action: str) -> subprocess.CompletedProcess[str]:
    """Invoke the checked-in shell entrypoint with only synthetic configuration."""
    return subprocess.run(["bash", str(SCRIPT), action], env=env, capture_output=True, text=True)


def calls(path: Path) -> list[Any]:
    """Read recorded process boundaries, or an empty list before any invocation."""
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def test_setup_preserves_configuration_and_keys(deployment: tuple[Path, dict[str, str]]) -> None:
    directory, env = deployment
    result = run(env, "setup")
    assert result.returncode == 0, result.stderr
    config_path = directory / "installer_config.yaml"
    config = yaml.safe_load(config_path.read_text())
    assert config["use_env"] is True
    assert config["whitelist_all_users"] is False
    assert config["default_user"]["password"] == "${DEFAULT_USER_PASSWORD}"
    for name in ("DOLT_ADMIN_PASSWORD", "DOLT_DOLTHUBAPI_PASSWORD", "DEFAULT_USER_PASSWORD"):
        assert env[name] not in config_path.read_text() + result.stdout + result.stderr
    args = calls(directory / "installer-calls.jsonl")[0]
    assert args[args.index("--host") + 1] == env["DOLTLAB_HOST"]
    assert "--use-env" in args
    assert (directory / ".gh-beads-configured").exists()
    config_path.write_text(config_path.read_text() + "# operator customization\n")
    (directory / "synthetic.keys").write_text("operator-key")
    assert run(env, "setup").returncode == 0
    assert "operator customization" in config_path.read_text()
    assert (directory / "synthetic.keys").read_text() == "operator-key"
    assert len(calls(directory / "installer-calls.jsonl")) == 1
    assert not calls(directory / "docker-calls.jsonl")


def test_lifecycle_isolated_from_hub_and_retains_volumes(
    deployment: tuple[Path, dict[str, str]],
) -> None:
    directory, env = deployment
    assert run(env, "setup").returncode == 0
    for action in ("validate", "deploy", "status", "down"):
        result = run(env, action)
        assert result.returncode == 0, result.stderr
    recorded = calls(directory / "docker-calls.jsonl")
    assert [entry["args"] for entry in recorded if entry["args"][0] == "network"] == [
        ["network", "inspect", "gh-beads-doltlab"],
        ["network", "create", "gh-beads-doltlab"],
    ]
    compose = [entry for entry in recorded if entry["args"][0] == "compose"]
    prefix = [
        "compose",
        "--project-name",
        "gh-beads-doltlab",
        "--env-file",
        "/dev/null",
        "--file",
        str(directory / "docker-compose.yaml"),
    ]
    assert [entry["args"][len(prefix) :] for entry in compose] == [
        ["config", "--quiet"],
        ["config", "--quiet"],
        ["up", "-d"],
        ["ps"],
        ["down"],
    ]
    for entry in compose:
        assert entry["args"][: len(prefix)] == prefix
        assert entry["cwd"] == str(directory)
        assert entry["env"] == {
            "COMPOSE_PROJECT_NAME": "gh-beads-doltlab",
            "COMPOSE_DISABLE_ENV_FILE": "true",
        }
        assert not any(env[name] in str(entry) for name in env if "PASSWORD" in name)
    assert (directory / "synthetic.keys").exists()


@pytest.mark.parametrize(
    "name", ["DOLT_ADMIN_PASSWORD", "DOLT_DOLTHUBAPI_PASSWORD", "DEFAULT_USER_PASSWORD"]
)
def test_missing_password_prevents_start(
    deployment: tuple[Path, dict[str, str]],
    name: str,
) -> None:
    directory, env = deployment
    assert run(env, "setup").returncode == 0
    env.pop(name)
    result = run(env, "deploy")
    assert result.returncode != 0 and name in result.stderr
    assert not calls(directory / "docker-calls.jsonl")


def test_invalid_configuration_never_starts_services(
    deployment: tuple[Path, dict[str, str]],
) -> None:
    directory, env = deployment
    assert run(env, "setup").returncode == 0
    env["FAIL_VALIDATE"] = "1"
    assert run(env, "deploy").returncode != 0
    recorded = calls(directory / "docker-calls.jsonl")
    assert len(recorded) == 1
    assert recorded[0]["args"][-2:] == ["config", "--quiet"]


@pytest.mark.parametrize("marker", [None, "v0.0.0"])
def test_setup_refuses_unmanaged_or_different_release(
    deployment: tuple[Path, dict[str, str]],
    marker: str | None,
) -> None:
    directory, env = deployment
    path = directory / ".gh-beads-release"
    path.unlink() if marker is None else path.write_text(marker)
    result = run(env, "setup")
    assert result.returncode != 0 and "unmanaged or a different release" in result.stderr
    assert not calls(directory / "installer-calls.jsonl")


def test_failed_setup_cannot_be_deployed_and_can_retry(
    deployment: tuple[Path, dict[str, str]],
) -> None:
    directory, env = deployment
    env["FAIL_INSTALLER"] = "1"
    assert run(env, "setup").returncode != 0
    assert not (directory / ".gh-beads-configured").exists()
    assert run(env, "deploy").returncode != 0
    assert not calls(directory / "docker-calls.jsonl")
    env.pop("FAIL_INSTALLER")
    assert run(env, "setup").returncode == 0


def test_checksum_failure_prevents_extraction(deployment: tuple[Path, dict[str, str]]) -> None:
    directory, env = deployment
    (directory / "installer").unlink()
    tools = Path(env["PATH"].split(":")[0])
    curl = tools / "curl"
    curl.write_text(
        f"#!{sys.executable}\nimport pathlib, sys\n"
        "pathlib.Path(sys.argv[sys.argv.index('--output') + 1]).write_bytes(b'corrupted')\n"
    )
    curl.chmod(0o700)
    unzip = tools / "unzip"
    unzip.write_text('#!/bin/sh\ntouch "$DOLTLAB_DIR/unzip-was-called"\n')
    unzip.chmod(0o700)
    result = run(env, "setup")
    assert result.returncode != 0 and "checksum mismatch" in result.stderr
    assert not (directory / "unzip-was-called").exists()
    assert not (directory / "installer").exists()
