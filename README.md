# XAPK Creation Tool

[![CI](https://github.com/knightfall-cs/xapk-tool/actions/workflows/ci.yml/badge.svg)](https://github.com/knightfall-cs/xapk-tool/actions/workflows/ci.yml)
[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A fast, modern command-line tool to create **XAPK** packages from Android **APK** and **OBB** expansion files.

The tool inspects the APK metadata using Androguard, validates corresponding OBB expansion files, generates standard APKPure-compatible `manifest.json` and `icon.png` assets, and archives everything into an `.xapk` package using direct in-memory streaming without wasting temporary disk space.

---

## Table of Contents

- [Features](#features)
- [Directory Layout](#directory-layout)
- [Installation](#installation)
  - [Option A: Global CLI via pipx (Recommended)](#option-a-global-cli-via-pipx-recommended)
  - [Option B: Virtual Environment](#option-b-virtual-environment)
  - [Option C: Standalone Script](#option-c-standalone-script)
- [Usage](#usage)
  - [Command Reference](#command-reference)
  - [Examples](#examples)
- [Android OBB Naming Convention](#android-obb-naming-convention)
- [Generated XAPK Structure](#generated-xapk-structure)
- [Troubleshooting](#troubleshooting)
- [License & Acknowledgments](#license--acknowledgments)

---

## Features

- ⚡ **Direct Stream Archiving**: Packages directly into `.xapk` zip archives without copying multi-gigabyte files to `/tmp`.
- 🧩 **Split APKs & App Bundles**: Automatically bundles Android App Bundle split configurations (`config.arm64_v8a.apk`, `config.xxhdpi.apk`, etc.) into XAPK v2 packages.
- 📋 **Rich Modern Manifest**: Emits full XAPK v2 metadata including `split_apks`, `split_configs`, `native_code` (CPU ABIs), `main_activity`, `features`, `libraries`, `locales_name`, and `icon`.
- 🖼️ **Icon & Asset Extraction**: Automatically extracts `icon.png` and links it in `manifest.json`.
- 📦 **Multi-OBB Support**: Handles both `main` and `patch` OBB files.
- 🛡️ **Package Verification**: Validates that OBB expansion files belong to the correct package to prevent broken installations.
- 🎛️ **Modern CLI**: Flexible flags for custom output (`-o`), force overwrite (`-f`), schema version selection (`--xapk-version`), bypass verification (`--skip-verify`), and allow OBB-less packaging (`--allow-no-obb`).

---

## Directory Layout

Place your APK file(s) and OBB expansion file(s) in a single directory:

### Standard APK with OBB
```text
my_game_folder/
├── base.apk
├── main.1024.com.example.game.obb
└── patch.1024.com.example.game.obb  (optional)
```

### Split APKs (App Bundle / AAB export)
```text
my_game_folder/
├── base.apk
├── config.arm64_v8a.apk
├── config.xxhdpi.apk
└── config.en.apk
```

---

## Installation

### Option A: Global CLI via pipx (Recommended)

[`pipx`](https://pypa.github.io/pipx/) installs the CLI in an isolated environment and makes it globally available in your terminal:

```bash
# Install directly from the repository
pipx install git+https://github.com/knightfall-cs/xapk-tool.git

# Or install locally after cloning
git clone https://github.com/knightfall-cs/xapk-tool.git
cd xapk-tool
pipx install .
```

Now you can invoke `xapktool` directly from anywhere!

---

### Option B: Virtual Environment

If using standard `pip` or on Debian/Ubuntu systems with PEP 668:

```bash
# 1. Clone the repository
git clone https://github.com/knightfall-cs/xapk-tool.git
cd xapk-tool

# 2. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# 3. Install the package
pip install .
```

---

### Option C: Standalone Script

You can also run the tool directly as a script without installing it:

```bash
pip install -r requirements.txt
python3 xapktool.py /path/to/folder
```

---

## Usage

```bash
xapktool [OPTIONS] <directory>
```

*(Note: `xapk-tool` and `python3 xapktool.py` can be used interchangeably).*

### Command Reference

| Flag / Argument | Description |
| :--- | :--- |
| `directory` | **Required.** Path to the directory containing the APK and OBB files. |
| `-o`, `--output <path>` | Custom output `.xapk` file path or destination folder. |
| `--xapk-version <1\|2>` | XAPK schema version (`1`=legacy, `2`=modern with split APKs; default: `2`). |
| `-f`, `--force` | Overwrite the output file if it already exists. |
| `--skip-verify` | Skip strict package name matching between APK and OBB filenames. |
| `--allow-no-obb` | Allow packaging an APK into XAPK format without OBB expansion files. |
| `-v`, `--verbose` | Enable detailed debug logs during processing. |
| `-q`, `--quiet` | Suppress all output except errors. |
| `-V`, `--version` | Display program version number and exit. |
| `-h`, `--help` | Show command-line help message. |

---

### Examples

#### 1. Basic Packaging
Automatically creates `<package_name>_v<version>.xapk` in the same directory:
```bash
xapktool ./my_game_folder
```

#### 2. Packaging Split APKs (App Bundles)
Place `base.apk` alongside configuration splits (`config.arm64_v8a.apk`, `config.xxhdpi.apk`) and run:
```bash
xapktool ./my_split_bundle_folder --allow-no-obb
```

#### 3. Specify Output File or Destination Directory
```bash
# Custom filename
xapktool ./my_game_folder -o /dist/MyGame.xapk

# Custom output folder (preserves automatic naming)
xapktool ./my_game_folder -o /dist/builds/
```

#### 4. Overwrite Existing Output
```bash
xapktool ./my_game_folder -f
```

#### 5. Non-standard OBB Filenames
If your OBB file does not follow the standard Google Play naming convention:
```bash
xapktool ./my_game_folder --skip-verify
```

#### 6. Convert Standalone APK to Legacy XAPK v1
```bash
xapktool ./folder_with_only_apk --allow-no-obb --xapk-version 1
```

---

## Android OBB Naming Convention

Android expansion files follow the official Google Play naming scheme:

```text
[main|patch].<version-code>.<package-name>.obb
```

- **`main` or `patch`**: `main` is the primary expansion file; `patch` is an optional update file.
- **`<version-code>`**: The integer `versionCode` defined in the APK's `AndroidManifest.xml`.
- **`<package-name>`**: The unique Android application ID (e.g., `com.example.game`).

**Example**:
For an APK with package name `com.epic.game` and version code `204`:
- Main expansion: `main.204.com.epic.game.obb`
- Patch expansion: `patch.204.com.epic.game.obb`

---

## Generated XAPK Structure

An XAPK file created by this tool is a standard ZIP archive containing:

```text
com.example.game_v1.0.xapk
├── com.example.game.apk         (base APK)
├── config.arm64_v8a.apk         (optional split APK)
├── icon.png                     (extracted application icon)
├── manifest.json                (rich metadata descriptor)
└── Android/
    └── obb/
        └── com.example.game/
            ├── main.1024.com.example.game.obb
            └── patch.1024.com.example.game.obb
```

### Manifest Schema (`manifest.json`)
The generated `manifest.json` provides complete metadata for modern installers:

```json
{
    "xapk_version": 2,
    "package_name": "com.example.game",
    "name": "Example Game",
    "version_code": 1024,
    "version_name": "1.0.0",
    "min_sdk_version": 21,
    "target_sdk_version": 34,
    "main_activity": "com.example.game.MainActivity",
    "icon": "icon.png",
    "locales_name": {
        "en": "Example Game"
    },
    "permissions": [
        "android.permission.INTERNET"
    ],
    "features": [
        "android.hardware.camera"
    ],
    "libraries": [
        "org.apache.http.legacy"
    ],
    "native_code": [
        "arm64-v8a"
    ],
    "split_apks": [
        { "file": "com.example.game.apk", "id": "base" },
        { "file": "config.arm64_v8a.apk", "id": "config.arm64_v8a" }
    ],
    "split_configs": [
        "config.arm64_v8a"
    ],
    "total_size": 157286400,
    "expansions": [
        {
            "file": "Android/obb/com.example.game/main.1024.com.example.game.obb",
            "install_location": "EXTERNAL_STORAGE",
            "install_path": "Android/obb/com.example.game/main.1024.com.example.game.obb"
        }
    ]
}
```

---

## Troubleshooting

### `ModuleNotFoundError: No module named 'androguard'`
Install the required dependencies:
```bash
pip install -r requirements.txt
# OR
pip install androguard>=3.4.0
```

### `error: externally-managed-environment` (Debian/Ubuntu)
Modern Linux distributions enforce PEP 668 to prevent breaking system Python packages. To install:
- Use `pipx install .` (recommended), or
- Create a virtual environment with `python3 -m venv .venv && source .venv/bin/activate`, or
- Install system androguard: `sudo apt install androguard`

### `ValueError: OBB file package does not match APK package`
Ensure your OBB file follows the `main.<version>.<package>.obb` pattern matching your APK. If you are using custom filenames or testing, pass the `--skip-verify` flag to bypass this verification.

---

## License & Acknowledgments

- **Author**: KNIGHTFALL
- **License**: Licensed under the [MIT License](LICENSE).
- **Inspiration**: Groundwork influenced by [BryghtShadow's xapktool](https://github.com/BryghtShadow/xapktool).
- **Core Parser**: Powered by [Androguard](https://github.com/androguard/androguard).
