# XAPK Creation Tool V2

This XAPK Creation Tool is designed to generate XAPK files from a directory containing an APK file and OBB files. It also generates the `icon.png` and `manifest.json` files from the APK file.

## Table of Contents

- [Usage](#usage)
- [Features](#features)
- [Installation](#installation)
- [Notes](#notes)
- [Authors](#authors)
- [License](#license)
- [Acknowledgments](#acknowledgments)

## Usage

To use the tool, follow these steps:

1. Clone or download this repository.

2. Open a terminal in the repository directory.

3. Run the following command:

   ```bash
   python3 xapktool.py <apk_obb_directory>
   ```

   Replace `<apk_obb_directory>` with the path to the directory containing the APK and OBB files.

   Example: `python3 xapktool.py D:\Programs\xapktool\xapk`

## Features

- Generates XAPK file from APK and OBB files.

- Automatically creates `icon.png` and `manifest.json` files from the APK.

- Supports multiple OBB files.

## Installation

Before using the XAPK creation tool, ensure you have [Python 3](https://www.python.org/downloads/) installed on your system.

To install any necessary dependencies, run the following command in your terminal:

```bash
python -m pip install -r requirements.txt
```

OR (only in linux):

```bash
sudo apt install adroguard
```
This installs all necessary dependencies with androguard.

## Notes

- The tool expects a directory with a single APK file and one or more OBB files.

- It's recommended to follow the Android expansion file naming convention for OBB files: `[main|patch].<expansion-version>.<package-name>.obb` as described in the [Android documentation](https://developer.android.com/google/play/expansion-files#GettingFilenames).

- If you encounter a module error related to importing `APK` from `androguard.core.bytecodes.apk`, modify the import statement,

From:

```python
from androguard.core.apk import APK
```

To:

```python
from androguard.core.bytecodes.apk import APK
```

## Authors

- XAPK Creation Tool V2: KNIGHTFALL

- Androguard + tools: Anthony Desnos (desnos at t0t0.fr)

- DAD (DAD is A Decompiler): Geoffroy Gueguen (geoffroy dot gueguen at gmail dot com)

## License

This [XAPK Creation Tool V2](https://github.com/knightfall-cs/xapktool.git) is licensed under the MIT License. See the [LICENSE](https://github.com/knightfall-cs/xapktool/blob/main/LICENSE) file for details.

## Acknowledgments

The development of [XAPK Creation Tool V2](https://github.com/knightfall-cs/xapktool.git) was influenced by [BryghtShadow's xapktool](https://github.com/BryghtShadow/xapktool), which provided the groundwork for this project.

---

Author: KNIGHTFALL
