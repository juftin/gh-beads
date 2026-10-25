"""Check a Beads workspace or wait for an external SQL service during Compose startup."""

from __future__ import annotations

import os
import re
import socket
import subprocess
import time
from pathlib import Path


def configure_remote_access() -> None:
    """Provision the database-scoped remote account without putting its password in argv."""
    password = os.environ.get("BEADS_REMOTE_PASSWORD", "")
    if not password or "\x00" in password:
        raise ValueError("Inject a nonempty BEADS_REMOTE_PASSWORD for the remote SQL account")
    database = os.environ.get("GH_BEADS_DATABASE", "gh_beads")
    if not re.fullmatch(r"[A-Za-z0-9_]+", database):
        raise ValueError("GH_BEADS_DATABASE must contain only letters, digits, and underscores")
    escaped = password.replace("\\", "\\\\").replace("'", "''")
    sql = (
        "CREATE USER IF NOT EXISTS 'beads'@'%';\n"
        f"ALTER USER 'beads'@'%' IDENTIFIED BY '{escaped}';\n"
        f"GRANT ALL PRIVILEGES ON `{database}`.* TO 'beads'@'%';\n"
    )
    result = subprocess.run(
        [
            "dolt",
            "--host",
            os.environ.get("BEADS_DOLT_SERVER_HOST", "127.0.0.1"),
            "--port",
            os.environ.get("BEADS_DOLT_SERVER_PORT", "3307"),
            "--user",
            "root",
            "--no-tls",
            "sql",
        ],
        input=sql,
        env={**os.environ, "DOLT_CLI_PASSWORD": ""},
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    if result.returncode:
        raise RuntimeError("Could not provision remote SQL account; SQL output suppressed")


def wait_for_hub(*, sql_only: bool = False, timeout: float = 120) -> None:
    """Check bd access for either backend, or explicitly wait for an external SQL listener."""
    deadline = time.monotonic() + timeout
    workspace = Path(os.environ.get("BEADS_WORKING_DIR", "."))
    while time.monotonic() < deadline:
        if sql_only:
            try:
                with socket.create_connection(
                    (
                        os.environ.get("BEADS_DOLT_SERVER_HOST", "127.0.0.1"),
                        int(os.environ.get("BEADS_DOLT_SERVER_PORT", "3307")),
                    ),
                    timeout=2,
                ):
                    return
            except OSError:
                pass
        elif (workspace / ".beads/metadata.json").is_file():
            result = subprocess.run(
                [os.environ.get("BEADS_PATH", "bd"), "info", "--json"],
                cwd=workspace,
                capture_output=True,
                timeout=10,
                check=False,
            )
            if result.returncode == 0:
                return
        time.sleep(1)
    raise TimeoutError("Dolt or hub initialization did not become ready within the startup timeout")
