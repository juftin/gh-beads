# Optional DoltLab deployment

DoltLab adds a self-hosted Dolt remote and web interface for database history, SQL queries, and collaboration. It runs alongside gh-beads as an independent stack. The hub continues using its existing embedded database or Compose SQL server; installing DoltLab alone does not publish the backlog or make it visible there. Use the remote workflow below to publish database commits.

## Host and configuration

The helper pins DoltLab **v2.6.3** and verifies the release ZIP against its checked-in SHA-256 before extracting or executing it. It uses the [upstream installer](https://www.doltlab.com/docs/reference/installer/) to generate all seven services, configuration, and token keys. It supports a **Linux AMD64** host with Docker Engine, the Compose plugin, Task, Bash, curl, unzip, and sha256sum. Install the host dependencies yourself; the helper does not change system packages.

[Upstream recommends](https://www.doltlab.com/docs/guides/installation/) at least **4 CPUs, 16 GB RAM, and 300 GB disk** for DoltLab, in addition to the hub's resources. Use a stable hostname or IP reachable by browsers and Dolt clients. If gh-beads runs on macOS or ARM64, deploy this companion from a checkout on a separate Linux AMD64 host.

The generated stack publishes HTTP on **80**, remote API on **50051**, uploads on **4321**, and auxiliary endpoints on **2001** and **7770**, using upstream's host-wide bindings. Its application database uses internal port 3306. These ports do not overlap the hub's defaults. The basic configuration uses HTTP; choose a private network or configure TLS through the upstream installer before exposing it remotely. The API service mounts the Docker socket to run DoltLab jobs.

Securely inject three distinct passwords into your shell environment before setup and deployment. The installer reads these variables, and `use_env` keeps their values out of generated deployment files:

| Variable | Purpose |
| --- | --- |
| `DOLT_ADMIN_PASSWORD` | DoltLab application database administrator |
| `DOLT_DOLTHUBAPI_PASSWORD` | DoltLab application database API account |
| `DEFAULT_USER_PASSWORD` | Initial DoltLab web login for `admin` |
| `DOLTLAB_HOST` | Required during setup; hostname or IP without a scheme or port |
| `DOLTLAB_DIR` | Optional deployment directory; defaults to `.doltlab/` in this checkout |

These passwords are independent of `BEADS_REMOTE_PASSWORD` and `GH_TOKEN`. Keep the same passwords available for subsequent operations; changing their environment values alone does not rotate stored credentials. The default account is `admin`, with email `admin@localhost`. SMTP is optional for that single account. Follow the [administrator guide](https://www.doltlab.com/docs/guides/basic/) for additional accounts, SMTP, password rotation, or TLS.

## Deploy and operate

From the checkout on the DoltLab host:

```sh
export DOLTLAB_HOST=doltlab.example.internal
# Optional: choose a persistent directory outside the checkout before the first setup.
# export DOLTLAB_DIR=/srv/gh-beads-doltlab
: "${DOLT_ADMIN_PASSWORD:?Inject the DoltLab database admin password}"
: "${DOLT_DOLTHUBAPI_PASSWORD:?Inject the DoltLab database API password}"
: "${DEFAULT_USER_PASSWORD:?Inject the initial DoltLab web password}"

task doltlab:setup
task doltlab:validate
task doltlab:deploy
task doltlab:status
```

Open `http://doltlab.example.internal` and sign in as `admin`. Deployment starts containers in the background; it does not establish application readiness. Check service status, logs, and successful login before using it:

```sh
task doltlab:logs -- --tail=50
task doltlab:down     # Remove DoltLab containers; retain its volumes, network, and files
task doltlab:deploy   # Start again with the same data and injected passwords
```

The fixed Compose project and external network are `gh-beads-doltlab`. Named volumes are separate from `gh-beads_data`. The helper explicitly selects its Compose file/project and disables dotenv loading so the hub's Compose selection and `.env` files do not affect DoltLab. Ordinary `task deploy` and `task down` manage only the hub; DoltLab commands manage only the companion. One companion deployment per Docker host is supported by this helper.

Setup is a one-time operation. Repeating it preserves generated configuration and keys; deploy never downloads or regenerates assets. The directory is private by default and excluded from Git and the Docker build context. Keep it at a stable path without whitespace because generated files contain absolute mount paths. If using a custom directory, keep it outside the source/build context. Preserve that directory and all DoltLab volumes when replacing a checkout.

## Publish a Beads database

Create a private database in DoltLab, then use its displayed clone/remote URL. Authenticate the Dolt client **where the Beads database runs** using the [upstream client authentication procedure](https://www.doltlab.com/docs/guides/basic/#authenticate-a-dolt-client-to-use-a-doltlab-account). A host login does not automatically authenticate the container's Dolt process. Its credentials must be persisted separately from this deployment directory. For Compose, use a hostname reachable from inside the hub containers; container-local `localhost` addresses the container itself.

In the existing initialized Beads workspace, with matching native Beads 1.3.1:

```sh
bd dolt remote add doltlab YOUR_DOLTLAB_REMOTE_URL
bd dolt remote list --json
bd dolt push --remote doltlab --no-adopt
```

For the Compose workspace, run those `bd` commands through `docker compose exec -T hub bd ...` after authenticating its Dolt client. The helper does not create repositories, mount credentials, configure a remote, or push/pull automatically. No GitHub source refresh is involved in a Dolt push. DoltLab shows database commits you publish; it does not provide beads-ui's task board or remove its custom status/type limitations.

A Dolt remote does not contain the hub's filesystem checkpoints and is not a complete workspace backup. Retain the [hub backup procedure](usage.md#backup-and-restore) and back up DoltLab separately.

## Backups, configuration changes, and upgrades

Follow [DoltLab's backup guide](https://www.doltlab.com/docs/guides/basic/#backup-doltlab-data) for its application database, remote data, and uploads. Preserve generated configuration and token keys as well. `task doltlab:down` retains these files and volumes; do not pass `--volumes` to Compose during normal operations.

The helper refuses to overwrite an unmanaged installer or a different pinned release. It does not upgrade DoltLab automatically. Before changing versions or regenerating configuration, stop the companion, back up its data and deployment directory, and follow upstream version-specific instructions. Regenerating installer assets rotates token keys, so repeated setup intentionally skips that step. Review the pinned version/checksum and validate the generated stack when adding an upgrade to this project. Do not change project/network names or reuse the hub's data volume.

Offline wrapper tests and generated Compose validation are available; full DoltLab startup, login, and authenticated Beads push/pull still require validation on a suitable Docker host.
