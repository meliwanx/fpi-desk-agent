# Agent Notes

## Web UI Design Scope

- The vendored shadcn-ui guidance under `.agents/skills/shadcn-ui/` is only for
  the web surfaces owned by this repo:
  - `admin-frontend/` — the browser admin console built into
    `backend/app/admin_static`.
  - `backend/app/website.py` — the public landing/download website rendered by
    the backend.
- Do not apply this shadcn-style visual system to the desktop client:
  - `frontend/`
  - `desktop-tauri/`
- The macOS and Windows desktop app should keep its existing product UI and
  design language unless the project owner explicitly asks for a separate
  desktop-client redesign.
- When changing web UI, keep the deployment boundary narrow: build
  `admin-frontend` for admin changes and deploy `backend/app/website.py` for
  public website changes. Do not rebuild or publish desktop packages for web-only
  styling changes.

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
machine now has key-based login from this Mac; use:

```bash
ssh fpi-agent-prod
```

Future agents should not ask for, store, or commit the server password for
normal deployment. The login credential is the local private key referenced
above, and the SSH alias is enough:

```bash
ssh -o BatchMode=yes fpi-agent-prod 'hostname && whoami'
```

If this key is deleted, the Mac is replaced, or `ssh fpi-agent-prod` fails with
`Permission denied`, ask the project owner for the root password again and use
it only to reinstall a public key. Never paste the password into tracked files.

### Production Service Boundaries

- `fpi-agent-backend.service` is the only service for this project.
- The service listens directly on `0.0.0.0:5201`; the admin console is served at `/admin`.
- Do not restart or reconfigure unrelated services while deploying this project.
- Important existing services/ports on the same host include:
  - `80` / `443`: Nginx
  - `3306` / `33060`: MySQL
  - `26739`: Redis/docker proxy
  - `5200`: separate Node service
  - `5201`: this fpi-agent backend/admin service
  - several other app ports (`5000`-`5005`, `5166`, `5167`, `5188`, `5199`, etc.)

### Safe Backend/Admin Deployment

1. Build the admin frontend locally:

```bash
npm run build:admin
```

2. Backup the current production backend directory:

```bash
ssh fpi-agent-prod 'mkdir -p /opt/fpi-agent/backups && tar -czf /opt/fpi-agent/backups/backend-$(date +%Y%m%d_%H%M%S).tar.gz -C /opt/fpi-agent backend'
```

3. The production server currently does not have `rsync`; use `scp`/`ssh` for
   targeted deploys. Preserve production-only files such as `.server.env`,
   `venv/`, `data/`, and `session_token.json`.

For admin-console/API changes like `backend/app/api/admin.py` plus built admin
static assets:

```bash
ssh fpi-agent-prod 'rm -rf /opt/fpi-agent/backend/app/admin_static'
scp -r backend/app/admin_static fpi-agent-prod:/opt/fpi-agent/backend/app/admin_static
scp backend/app/api/admin.py fpi-agent-prod:/opt/fpi-agent/backend/app/api/admin.py
```

4. Restart and verify only this service:

```bash
ssh fpi-agent-prod 'systemctl restart fpi-agent-backend.service && sleep 3 && systemctl status fpi-agent-backend.service --no-pager -l | sed -n "1,80p"'
curl -sS -o /dev/null -w '%{http_code}\n' http://120.26.208.161:5201/admin
```

## Release Version Policy

- The root `package.json` is the single source of truth for the published desktop app version.
- Use SemVer `MAJOR.MINOR.PATCH` only. Bug fixes should bump patch, compatible features should bump minor, and incompatible changes should bump major.
- Before building or uploading a new desktop package, run `npm run set:release-version -- 1.4.1` with the intended release version.
- After changing a release version, run `npm run check:release-version`. GitHub Actions runs the same check before producing Windows and macOS installers.
- The Tauri runtime reports `desktop-tauri/src-tauri/tauri.conf.json` as the installed app version. If this value is stale, update checks will be wrong.
- Backend update policy should compare client version against the selected platform asset version. Do not use a macOS package version to force Windows users, or the reverse.
- `sha256` is for downloaded package integrity verification. It must not replace SemVer for update ordering because the same version can be repackaged with a different hash.

## Apple Signing and GitHub Actions Secrets

已经在当前仓库 `meliwanx/fpi-desk-agent` 的 GitHub Actions Secrets 里创建了这 7 个：

`APPLE_CERTIFICATE`
`APPLE_CERTIFICATE_PASSWORD`
`APPLE_ID`
`APPLE_PASSWORD`
`APPLE_TEAM_ID`
`TAURI_SIGNING_PRIVATE_KEY`
`TAURI_SIGNING_PRIVATE_KEY_PASSWORD`

`.p12` 是从本机钥匙串里的 `Developer ID Application: rui dong (53BDDF5YZM)` 导出的，转成 base64 后写进 GitHub Secret；临时 `.p12`、base64、private key 文件都已经从 `/tmp` 删除了。

代码里的签名身份和 Tauri updater public key 已经对齐，并 push 了：

`1197c34 Configure Apple signing identity and updater key`

GitHub Actions 已经自动触发新构建：`Desktop Package Build #11`，当时状态是 `In progress`。Chrome 里也把 Actions 页面留着了，可以直接看构建进度。

注意：当前按本机证书设置的是 Team ID `53BDDF5YZM`。如果 Apple notarization 步骤失败，最可能原因是 Apple ID 不属于这个 Apple Developer Team；需要换成有这个 Team 权限的 Apple ID，或者重新用对应 Apple 账号生成 Developer ID 证书。
