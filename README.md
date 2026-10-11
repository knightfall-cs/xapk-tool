# XAPK Creation Tool

[![CI](https://github.com/knightfall-cs/xapk-tool/actions/workflows/ci.yml/badge.svg)](https://github.com/knightfall-cs/xapk-tool/actions/workflows/ci.yml)
[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A command-line tool to generate XAPK files from a directory containing an APK file and OBB files. It also generates the `icon.png` and `manifest.json` files from the APK.

---

## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
- [Notes](#notes)
- [License](#license)

---

## Features

- Generates XAPK files from APK and OBB files.
- Automatically creates `icon.png` and `manifest.json` from the APK.
- Supports multiple OBB files and split APK configurations.

---

## Installation

Before using the tool, ensure you have [Python 3](https://www.python.org/downloads/) installed.

### 1. Virtual Environment (Recommended)

```bash
git clone https://github.com/knightfall-cs/xapk-tool.git
cd xapk-tool

python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install .
```

This installs the `xapktool` command globally within the virtual environment.

### 2. Standalone Script

You can run the script directly without installing it:

```bash
git clone https://github.com/knightfall-cs/xapk-tool.git
cd xapk-tool

pip install -r requirements.txt
python3 xapktool.py <apk_obb_directory>
```

### 3. Global CLI via pipx

If you prefer a system-wide CLI managed in an isolated environment:

```bash
pipx install git+https://github.com/knightfall-cs/xapk-tool.git
```

Or install locally after cloning:

```bash
pipx install .
```

---

## Usage

```bash
xapktool [options] <directory>
```

*(Options can be placed before or after the directory).*

### Options

| Option | Description |
| :--- | :--- |
| `directory` | Path to directory containing APK and OBB files. |
| `-o, --output <path>` | Custom output `.xapk` file path or destination folder. |
| `-f, --force` | Overwrite output file if it already exists. |
| `--no-obb` | Allow packaging an APK without OBB expansion files. |
| `--skip-verify` | Skip strict package name matching between APK and OBB filenames. |
| `--xapk-version <1\|2>` | XAPK schema version (1=legacy, 2=modern; default: 2). |
| `-v, --verbose` | Enable verbose debug output. |
| `-q, --quiet` | Suppress output except errors. |
| `-V, --version` | Show version number and exit. |
| `-h, --help` | Show help message. |

### Examples

```bash
# Basic usage
xapktool ./my_game_folder

# Custom output destination
xapktool ./my_game_folder -o /dist/MyGame.xapk

# Overwrite existing output
xapktool ./my_game_folder -f

# Standalone APK or split APKs without OBB
xapktool ./my_app_folder --no-obb

# Non-standard OBB filenames
xapktool ./my_game_folder --skip-verify
```

---

## Notes

- The tool expects a directory containing an APK file and optional OBB files.
- Recommended OBB naming convention: `[main|patch].<version-code>.<package-name>.obb`
- Generated XAPK structure:
  ```text
  <package_name>_v<version>.xapk
  ├── <package_name>.apk
  ├── icon.png
  ├── manifest.json
  └── Android/
      └── obb/
          └── <package_name>/
              └── main.<version>.<package_name>.obb
  ```

---

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

Author: KNIGHTFALL
