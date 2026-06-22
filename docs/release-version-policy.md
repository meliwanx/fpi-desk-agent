# Desktop Release Versions

## Release Version Policy

The root `package.json` is the single source of truth for the published desktop app version.

Use SemVer `MAJOR.MINOR.PATCH` only:

- Patch release: bug fixes or small compatible changes, for example `1.4.0` to `1.4.1`.
- Minor release: compatible product features, for example `1.4.1` to `1.5.0`.
- Major release: incompatible changes, for example `1.5.0` to `2.0.0`.

Before building or uploading a new desktop package, run:

```bash
npm run set:release-version -- 1.4.1
```

Then run:

```bash
npm run check:release-version
```

GitHub Actions runs the same version metadata check before producing Windows and macOS installers.

The Tauri runtime reports `desktop-tauri/src-tauri/tauri.conf.json` as the installed app version. If this value is stale, update checks will be wrong.

Backend update policy should compare the client version against the selected platform asset version. Do not use a macOS package version to force Windows users, or the reverse.

`sha256` is for downloaded package integrity verification. It must not replace SemVer for update ordering because the same version can be repackaged with a different hash.
