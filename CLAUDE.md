# Agent Notes

## Web UI Design Scope

- The vendored shadcn-ui guidance under `.agents/skills/shadcn-ui/` applies only
  to the repo-owned browser surfaces:
  - `admin-frontend/` for the management console.
  - `backend/app/website.py` for the public landing/download website.
- Do not apply this design system to the desktop client UI in `frontend/` or the
  native shell in `desktop-tauri/`.
- macOS and Windows client UI changes require a separate, explicit desktop
  redesign request. Web-only styling work must not trigger desktop package
  rebuilds or desktop release version bumps.
- For admin changes, build `admin-frontend` and deploy
  `backend/app/admin_static`. For website changes, deploy
  `backend/app/website.py`. Keep these paths separate from desktop app code.

## Server Deployment

- Host: `120.26.208.161`
- User: `root`
- Local SSH alias: `fpi-agent-prod`
- Local SSH key: `~/.ssh/fpi-agent-prod-ed25519`
- Service: `fpi-agent-backend.service`
- Backend path: `/opt/fpi-agent/backend`
- Public admin URL: `http://120.26.208.161:5201/admin`
- Deployment package staging path: `/tmp/fpi-agent-server-*.tar.gz`
- Runtime command: `/opt/fpi-agent/backend/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 5201`
- Systemd unit: `/etc/systemd/system/fpi-agent-backend.service`

Do not store the root password in this repository. Use the credential supplied
by the project owner or operations channel only to bootstrap SSH access. This
Mac has key-based login configured:

```bash
ssh fpi-agent-prod
```

Future agents should use the SSH alias and local private key, not the root
password:

```bash
ssh -o BatchMode=yes fpi-agent-prod 'hostname && whoami'
```

If the key is missing or login fails with `Permission denied`, ask the project
owner for the root password again and use it only to reinstall the public key.
Never paste the password into tracked files.

Deployment boundary: only restart `fpi-agent-backend.service` for this project.
It listens on `0.0.0.0:5201` and serves `/admin`. Do not touch unrelated
services such as Nginx (`80`/`443`), MySQL (`3306`/`33060`), Redis/docker proxy
(`26739`), the separate Node service on `5200`, or other app ports.

Safe deploy summary:

```bash
npm run build:admin
ssh fpi-agent-prod 'mkdir -p /opt/fpi-agent/backups && tar -czf /opt/fpi-agent/backups/backend-$(date +%Y%m%d_%H%M%S).tar.gz -C /opt/fpi-agent backend'
# Current server does not have rsync installed; use scp for targeted admin/API deploys.
ssh fpi-agent-prod 'rm -rf /opt/fpi-agent/backend/app/admin_static'
scp -r backend/app/admin_static fpi-agent-prod:/opt/fpi-agent/backend/app/admin_static
scp backend/app/api/admin.py fpi-agent-prod:/opt/fpi-agent/backend/app/api/admin.py
ssh fpi-agent-prod 'systemctl restart fpi-agent-backend.service && sleep 3 && systemctl status fpi-agent-backend.service --no-pager -l | sed -n "1,80p"'
curl -sS -o /dev/null -w '%{http_code}\n' http://120.26.208.161:5201/admin
```
