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

The Tauri runtime reports `desktop-tauri/src-tauri/tauri.conf.json` as the installed app version. If this value is stale, in-app Tauri updater manifests can be wrong.

Enterprise backend update policy uses the selected platform asset SHA-256 as the installed package identity. The admin console records every uploaded package and the administrator manually chooses the latest package for macOS, Windows, Linux, or the default fallback slot. A client is current only when its stored package identity SHA-256 equals that selected latest package SHA-256.

SemVer is still required for human-readable release naming, package labels, Tauri metadata, and signed updater manifest compatibility. It is not the source of truth for enterprise update detection because the same version can be rebuilt with a different package hash.

SHA-256 also remains the downloaded package integrity check before installation. MD5 is recorded for quick admin-side comparison only and must not be used as the security check.
