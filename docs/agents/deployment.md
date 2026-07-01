# Agent Deployment Notes

This file is the tracked deployment reference for agents working on this repo.
Local `AGENT.md` and `CLAUDE.md` files may exist, but they are ignored by git.

## Production Server

| Item | Value |
| --- | --- |
| Host | `120.26.208.161` |
| SSH user | `root` |
| Local SSH alias | `fpi-agent-prod` |
| Local SSH key | `~/.ssh/fpi-agent-prod-ed25519` |
| Backend path | `/opt/fpi-agent/backend` |
| Systemd service | `fpi-agent-backend.service` |
| Runtime port | `0.0.0.0:5201` |
| Public admin URL | `https://fpiagent.hangzhoupuyu.work/admin` |
| Direct admin URL | `http://120.26.208.161:5201/admin` |

Do not store the root password in this repository. This Mac has key-based SSH
login configured through the alias:

```bash
ssh fpi-agent-prod
```

For non-interactive checks, use:

```bash
ssh -o BatchMode=yes fpi-agent-prod 'hostname && whoami'
```

If the key is missing or login fails with `Permission denied`, ask the project
owner for the root password again and use it only to reinstall the public key.
Never paste the password into tracked files.

## Service Boundaries

Only restart or inspect `fpi-agent-backend.service` for this project. Do not
touch unrelated services such as Nginx on `80`/`443`, MySQL on `3306`/`33060`,
Redis/docker proxy on `26739`, the separate Node service on `5200`, or other
application ports on the same host.

## Safe Admin/API Deploy

Build the admin frontend locally:

```bash
npm run build:admin
```

Do not create full backend backups before deploys. The production backend
contains user uploads and server-side package assets under `data/`, which can
grow very large and must not be copied into release backups.

If a rollback snapshot is needed, back up code only and exclude runtime data,
virtualenvs, secrets, tokens, and caches:

```bash
ssh fpi-agent-prod '
  mkdir -p /opt/fpi-agent/backups
  tar -czf /opt/fpi-agent/backups/backend-code-$(date +%Y%m%d_%H%M%S).tar.gz \
    -C /opt/fpi-agent/backend \
    --exclude=./data \
    --exclude=./venv \
    --exclude=./.server.env \
    --exclude=./session_token.json \
    --exclude="*/__pycache__" \
    --exclude="*.pyc" \
    .
'
```

The production server currently does not have `rsync`; use targeted `scp` and
preserve production-only files such as `.server.env`, `venv/`, `data/`, and
`session_token.json`.

Never back up user-uploaded or server-generated file directories for deploys:
`data/uploads`, `data/audit_uploads`, `data/update_assets`, and
`data/feedback_uploads`. Treat the whole `data/` tree as runtime state.

For admin/API changes:

```bash
ssh fpi-agent-prod 'rm -rf /opt/fpi-agent/backend/app/admin_static'
scp -r backend/app/admin_static fpi-agent-prod:/opt/fpi-agent/backend/app/admin_static
scp backend/app/api/admin.py fpi-agent-prod:/opt/fpi-agent/backend/app/api/admin.py
```

If the change also touches other backend modules, copy those files explicitly or
package the backend carefully without deleting production-only files.

Restart and verify only this service:

```bash
ssh fpi-agent-prod 'systemctl restart fpi-agent-backend.service && sleep 3 && systemctl status fpi-agent-backend.service --no-pager -l | sed -n "1,80p"'
curl -sS -o /dev/null -w '%{http_code}\n' https://fpiagent.hangzhoupuyu.work/admin
```
