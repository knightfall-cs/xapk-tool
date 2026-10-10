# Changelog

All notable changes to the **XAPK Creation Tool** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [2.1.0] - 2026-10-10

### 🚀 Highlights
- **Zero-Copy Stream Archiving**: Packages directly into `.xapk` archives via in-memory streaming. Completely removes the disk-intensive temporary directory (`/tmp`) copying, enabling multi-gigabyte games to package in seconds with zero extra disk space overhead.
- **Full XAPK v2 Manifest Specification**: Emits modern `manifest.json` metadata compatible with modern installers (APKPure, Uptodown, SAI) including split APKs, CPU architectures, launch activities, and features.
- **App Bundle Split APK Support**: Automatically discovers, categorizes, and bundles split configuration APKs (`config.arm64_v8a.apk`, `config.xxhdpi.apk`, etc.) alongside the base APK.

---

### ✨ New Features & Improvements
- **Rich Manifest Metadata**:
  - `main_activity`: Extracted directly from APK (`AndroidManifest.xml`) so installers can launch the application immediately upon installation.
  - `native_code`: Auto-detects supported CPU architectures (`arm64-v8a`, `armeabi-v7a`, `x86`, `x86_64`) from embedded `.so` libraries and split configuration files.
  - `split_apks` & `split_configs`: Full mapping of base and configuration splits.
  - `features` & `libraries`: Populates `<uses-feature>` and `<uses-library>` declarations.
  - `locales_name`: Localized app title mapping.
  - `icon`: Explicit `"icon": "icon.png"` manifest pointer.
  - `max_sdk_version`: Captured if declared in the APK.
  - `is_leanback` / `is_wearable`: Target platform indicators.
- **Direct API Level Preservation**:
  - `min_sdk_version` and `target_sdk_version` are retrieved directly from the APK as-is.
  - Suppressed internal Androguard permission database mapping logs that previously displayed misleading API level fallback warnings.
- **Modern CLI Flags**:
  - `-o, --output <path>`: Specify a custom output `.xapk` filename or destination directory.
  - `-f, --force`: Overwrite existing output files safely (prevents accidental overwriting by default).
  - `--xapk-version <1|2>`: Choose manifest schema version (default: `2`).
  - `--skip-verify`: Bypass strict OBB filename package matching for non-standard files.
  - `--allow-no-obb`: Allow packaging APKs without OBB expansions (e.g. standalone APKs or Split APK sets).
  - `-v, --verbose` & `-q, --quiet`: Verbose debug logs or quiet execution for automated scripts.
  - `-V, --version`: Display program version number.
- **Resilient Androguard Imports**:
  - Dynamically resolves both modern (`androguard.core.bytecodes.apk`) and legacy (`androguard.core.apk`) imports without requiring manual code modifications.
- **Standard Python Packaging**:
  - Added PEP 517/518/621 `pyproject.toml` exposing global `xapktool` command via `pip` / `pipx`.
  - Trimmed bloated `requirements.txt` from 28 packages to just `androguard>=3.4.0`.

---

### 🛡️ Repository Hygiene & CI
- Added `.gitignore` covering Python cache, virtual environments, packaging files, and Android binary assets (`*.apk`, `*.obb`, `*.xapk`).
- Added `.gitattributes` to enforce consistent LF line endings and binary file handling.
- Added GitHub Actions CI workflow (`.github/workflows/ci.yml`) validating package installation and CLI functionality across Python 3.8 through 3.12.
- Added GitHub issue templates for bug reporting and feature requests, and a pull request template.
- Overhauled `README.md` with status badges, installation guides (`pipx`/`venv`/script), CLI reference table, OBB naming guide, and troubleshooting.

---

## [2.0.0] - Prior Release
- Initial V2 release generating XAPK archives from an APK and OBB files.
