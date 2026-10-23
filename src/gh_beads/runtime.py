"""Check workspace readiness and configure shared workflow or remote SQL access."""

from __future__ import annotations

import argparse
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


def main() -> None:
    """Wait for a runtime dependency or configure the shared workspace."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sql", action="store_true", help="Wait only for the SQL listener")
    parser.add_argument(
        "--configure-remote", action="store_true", help="Provision remote SQL access"
    )
    parser.add_argument(
        "--configure-workflow", action="store_true", help="Register hub statuses and issue types"
    )
    args = parser.parse_args()
    if args.configure_workflow:
        from gh_beads.sync import Beads

        Beads().configure_workflow()
    elif args.configure_remote:
        configure_remote_access()
    else:
        wait_for_hub(sql_only=args.sql)


if __name__ == "__main__":
    main()
