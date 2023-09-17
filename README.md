# XAPK Creation Tool v2

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

To use the XAPK creation tool, follow these steps:

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
- Supports mutliplte OBB files.

## Installation

Before using the XAPK creation tool, ensure you have [Python 3](https://docs.python.org/3/) installed on your system.

To install any necessary dependencies, run the following command in your terminal:

```bash
pip install -r requirements.txt
```

## Notes

- The tool expects a directory with a single apk and obb files.

- There is no check to ensure that the OBB and APK are from the same application. There is also no check for cases where there is no obb file.

- Probably should enforce that obb files are correctly named (`[main|patch].<expansion-version>.<package-name>.obb`), as per <https://developer.android.com/google/play/expansion-files#GettingFilenames>

## Authors

- XAPK Creation Tool v2: KNIGHTFALL

- Androguard + tools: Anthony Desnos (desnos at t0t0.fr)

- DAD (DAD is A Decompiler): Geoffroy Gueguen (geoffroy dot gueguen at gmail dot com)

## License

This XAPK Creation Tool v2 is licensed under the MIT License. See the [LICENSE](https://github.com/knightfall-cs/xapktool/blob/main/LICENSE) file for details.

## Acknowledgments

This XAPK Creation Tool v2 was inspired by the work of [BryghtShadow](https://github.com/BryghtShadow/xapktool). I would like to express my gratitude for the original project's contributions and ideas that inspired the development of this tool.

---

Author: KNIGHTFALL
