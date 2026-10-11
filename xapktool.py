#!/usr/bin/env python3
"""
XAPK Creation Tool
Generates .xapk package files from a directory containing an APK file and OBB files.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

__version__ = "2.1.0"

# Suppress internal androguard permission resource mapping logs
logging.getLogger("androguard").setLevel(logging.ERROR)

# Robust import of APK across different androguard versions
try:
    from androguard.core.bytecodes.apk import APK  # type: ignore
except ImportError:
    try:
        from androguard.core.apk import APK  # type: ignore
    except ImportError:
        APK = None  # type: ignore


class XAPK:
    """Handles parsing an APK, split APKs, and OBB files from a directory and packaging them into an XAPK archive."""

    def __init__(
        self,
        folder: str | Path,
        output: Optional[str | Path] = None,
        xapk_version: int = 2,
        skip_verify: bool = False,
        no_obb: bool = False,
        allow_no_obb: bool = False,
        force: bool = False,
        verbose: bool = False,
        quiet: bool = False,
    ) -> None:
        if APK is None:
            raise RuntimeError(
                "Androguard is not installed or could not be loaded. "
                "Please install it with: pip install androguard"
            )

        self.folder = Path(folder)
        self.output_param = Path(output) if output else None
        self.xapk_version = xapk_version
        self.skip_verify = skip_verify
        self.no_obb = no_obb or allow_no_obb
        self.force = force
        self.verbose = verbose
        self.quiet = quiet

        self.apk_src: Optional[Path] = None
        self.split_apks: List[Path] = []
        self.obb_files: List[Path] = []
        self.apk: Optional[APK] = None
        self.manifest: Optional[Dict[str, Any]] = None
        self.icon: Optional[bytes] = None
        self.output_path: Optional[Path] = None

        self.initialize()

    def _log(self, message: str) -> None:
        """Print progress message unless quiet mode is enabled."""
        if not self.quiet:
            print(message)

    def _debug(self, message: str) -> None:
        """Print debug message when verbose mode is enabled."""
        if self.verbose and not self.quiet:
            print(f"[DEBUG] {message}")

    @staticmethod
    def _sanitize_filename(name: str) -> str:
        """Sanitize a string for safe use in filenames across platforms."""
        return re.sub(r'[\\/*?:"<>| ]', "_", name)

    @staticmethod
    def _safe_int(val: Any, default: int = 0) -> int:
        """Safely convert value to integer."""
        try:
            return int(val)
        except (ValueError, TypeError):
            return default

    @staticmethod
    def _safe_int_or_str(val: Any) -> Any:
        """Safely convert value to integer if numeric, else string."""
        if val is None:
            return None
        try:
            return int(val)
        except (ValueError, TypeError):
            return str(val)

    def _categorize_apks(self, apk_candidates: List[Path]) -> Tuple[Path, List[Path]]:
        """Identify the base APK and any auxiliary split configuration APKs."""
        if len(apk_candidates) == 1:
            return apk_candidates[0], []

        # 1. Look for explicit 'base.apk'
        for apk in apk_candidates:
            if apk.name.lower() == "base.apk":
                splits = [a for a in apk_candidates if a != apk]
                return apk, splits

        # 2. Look for an APK that is not prefixed with 'config.' or 'split_'
        non_splits = [
            a for a in apk_candidates
            if not (a.stem.lower().startswith("config.") or a.stem.lower().startswith("split_"))
        ]
        if non_splits:
            base = non_splits[0]
            splits = [a for a in apk_candidates if a != base]
            return base, splits

        # 3. Fallback: use the first APK as base
        return apk_candidates[0], apk_candidates[1:]

    def _detect_native_code(self) -> List[str]:
        """Detect supported native CPU ABIs from native shared libraries and split APK names."""
        abis = set()
        if self.apk:
            try:
                for f in self.apk.get_files():
                    if f.startswith("lib/"):
                        parts = f.split("/")
                        if len(parts) >= 3 and parts[1]:
                            abis.add(parts[1])
            except Exception:
                pass

        known_abis = ["arm64-v8a", "armeabi-v7a", "armeabi", "x86", "x86_64", "mips", "mips64", "riscv64"]
        for split in self.split_apks:
            for abi in known_abis:
                abi_underscore = abi.replace("-", "_")
                if abi in split.name or abi_underscore in split.name:
                    abis.add(abi)

        return sorted(list(abis))

    def initialize(self) -> None:
        """Inspect the directory, locate APKs and OBBs, parse manifest and icon."""
        if not self.folder.is_dir():
            raise ValueError(f"The specified path '{self.folder}' does not exist or is not a directory.")

        # Discover APK file(s)
        apk_candidates = sorted(self.folder.glob("*.apk"))
        if not apk_candidates:
            raise FileNotFoundError(f"No APK file found in '{self.folder}'.")

        self.apk_src, self.split_apks = self._categorize_apks(apk_candidates)
        self._debug(f"Selected base APK: {self.apk_src.name}")
        if self.split_apks:
            self._log(f"Found {len(self.split_apks)} split configuration APK(s).")
            for split in self.split_apks:
                self._debug(f"Split APK: {split.name}")

        # Discover OBB files
        self.obb_files = sorted(self.folder.glob("*.obb"))
        if not self.obb_files and not self.no_obb:
            raise FileNotFoundError(
                f"No OBB files found in '{self.folder}'. "
                "If this APK does not require OBB expansions, run with --no-obb."
            )

        # Parse APK metadata
        self._debug("Parsing APK metadata with androguard...")
        self.apk = APK(self.apk_src)

        apk_package_name = self.apk.get_package()
        if not apk_package_name:
            raise ValueError("Unable to determine package name from APK.")
        self._debug(f"APK Package: {apk_package_name}")

        # Extract app icon safely
        try:
            icon_path = self.apk.get_app_icon()
            if icon_path:
                self.icon = self.apk.get_file(icon_path)
                self._debug(f"Extracted icon from '{icon_path}' ({len(self.icon) if self.icon else 0} bytes)")
        except Exception as e:
            self._debug(f"Could not extract APK icon: {e}")
            self.icon = None

        # Build manifest
        self.manifest = self.make_manifest()

        # Verify OBBs
        if self.obb_files:
            self._debug("Verifying OBB files...")
            self.verify_obb_files(apk_package_name)
        self._log("Verification: OK")

    def verify_obb_files(self, apk_package_name: str) -> None:
        """Verify that OBB files correspond to the same application package."""
        for obb_file in self.obb_files:
            # Android OBB naming: [main|patch].<version-code>.<package-name>.obb
            parts = obb_file.stem.split(".")
            obb_package_name = ".".join(parts[2:]) if len(parts) >= 3 else ""

            if obb_package_name != apk_package_name:
                err_msg = (
                    f"OBB file '{obb_file.name}' package ('{obb_package_name}') does not match "
                    f"APK package ('{apk_package_name}'). "
                    f"Standard format is [main|patch].<version-code>.<package-name>.obb."
                )
                if self.skip_verify:
                    self._log(f"Warning: {err_msg} (ignoring due to --skip-verify)")
                else:
                    raise ValueError(f"{err_msg} Use --skip-verify to bypass.")

    def make_manifest(self) -> Dict[str, Any]:
        """Construct the rich XAPK manifest dictionary with modern fields."""
        if not self.apk_src or not self.apk:
            raise RuntimeError("APK source is not initialized.")

        apk_size = self.apk_src.stat().st_size
        total_size = apk_size
        package_name = self.apk.get_package()

        # OBB Expansions
        obb_info = []
        for obb_file in self.obb_files:
            obb_size = obb_file.stat().st_size
            total_size += obb_size

            obb_rel_path = f"Android/obb/{package_name}/{obb_file.name}"
            obb_info.append({
                "file": obb_rel_path,
                "install_location": "EXTERNAL_STORAGE",
                "install_path": obb_rel_path,
            })

        # Split APKs & Configurations
        base_apk_arcname = f"{package_name}.apk"
        split_apks_info = [
            {
                "file": base_apk_arcname,
                "id": "base",
            }
        ]
        split_configs = []

        for split_file in self.split_apks:
            split_size = split_file.stat().st_size
            total_size += split_size

            # Extract split identifier (e.g., config.arm64_v8a from split_config.arm64_v8a.apk)
            split_id = split_file.stem
            if split_id.startswith("split_"):
                split_id = split_id[6:]

            split_apks_info.append({
                "file": split_file.name,
                "id": split_id,
            })
            split_configs.append(split_id)

        # Basic metadata
        app_name = self.apk.get_app_name() or package_name
        version_name = self.apk.get_androidversion_name() or "1.0"
        version_code = self._safe_int(self.apk.get_androidversion_code())
        min_sdk = self._safe_int_or_str(self.apk.get_min_sdk_version())
        target_sdk = self._safe_int_or_str(self.apk.get_target_sdk_version())
        permissions = list(self.apk.get_permissions() or [])

        # Additional modern features
        manifest: Dict[str, Any] = {
            "xapk_version": self.xapk_version,
            "package_name": package_name,
            "name": app_name,
            "version_code": version_code,
            "version_name": str(version_name),
            "min_sdk_version": min_sdk,
            "target_sdk_version": target_sdk,
        }

        # Optional Max SDK
        try:
            max_sdk = self.apk.get_max_sdk_version()
            if max_sdk is not None:
                manifest["max_sdk_version"] = self._safe_int_or_str(max_sdk)
        except Exception:
            pass

        # Main launcher activity
        try:
            main_activity = self.apk.get_main_activity()
            if main_activity:
                manifest["main_activity"] = str(main_activity)
        except Exception:
            pass

        # App Icon pointer
        if self.icon:
            manifest["icon"] = "icon.png"

        # Localized names
        manifest["locales_name"] = {
            "en": str(app_name)
        }

        # Permissions
        manifest["permissions"] = permissions

        # Hardware/software features (<uses-feature>)
        try:
            raw_features = self.apk.get_features()
            if raw_features:
                manifest["features"] = sorted(list(set(str(f) for f in raw_features if f)))
        except Exception:
            pass

        # Shared libraries (<uses-library>)
        try:
            raw_libs = self.apk.get_libraries()
            if raw_libs:
                manifest["libraries"] = sorted(list(set(str(l) for l in raw_libs if l)))
        except Exception:
            pass

        # Native ABIs / Architecture
        native_abis = self._detect_native_code()
        if native_abis:
            manifest["native_code"] = native_abis

        # Leanback / TV / Wearable detection
        try:
            if self.apk.is_leanback() or self.apk.is_androidtv():
                manifest["is_leanback"] = True
        except Exception:
            pass

        try:
            if self.apk.is_wearable():
                manifest["is_wearable"] = True
        except Exception:
            pass

        # Split APKs information (standard in v2 or when splits are present)
        if self.xapk_version >= 2 or self.split_apks:
            manifest["split_apks"] = split_apks_info
            if split_configs:
                manifest["split_configs"] = split_configs

        # Size and expansions
        manifest["total_size"] = total_size
        manifest["expansions"] = obb_info

        return manifest

    def resolve_output_path(self) -> Path:
        """Determine destination path for the generated XAPK file."""
        if not self.apk:
            raise RuntimeError("APK is not initialized.")

        package_name = self.apk.get_package()
        raw_version = str(self.apk.get_androidversion_name() or "1.0")
        safe_version = self._sanitize_filename(raw_version)
        default_name = f"{package_name}_v{safe_version}.xapk"

        if self.output_param:
            if self.output_param.is_dir():
                dest = self.output_param / default_name
            else:
                dest = self.output_param
        else:
            dest = self.folder / default_name

        if dest.exists() and not self.force:
            raise FileExistsError(
                f"Destination file '{dest}' already exists. Use --force to overwrite."
            )

        return dest

    def save(self) -> Path:
        """Create the .xapk zip archive directly without temporary file copying."""
        if not self.apk_src or not self.apk or not self.manifest:
            raise RuntimeError("XAPK instance is not ready to save.")

        dest_path = self.resolve_output_path()
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        package_name = self.apk.get_package()
        self._log(f"Creating XAPK: {dest_path.name}")

        try:
            with zipfile.ZipFile(dest_path, "w", compression=zipfile.ZIP_DEFLATED) as zfd:
                # 1. Base APK
                apk_arcname = f"{package_name}.apk"
                self._debug(f"Adding APK: {self.apk_src.name} -> {apk_arcname}")
                zfd.write(self.apk_src, arcname=apk_arcname)

                # 2. Split APKs (if present)
                for split_file in self.split_apks:
                    self._debug(f"Adding Split APK: {split_file.name}")
                    zfd.write(split_file, arcname=split_file.name)

                # 3. OBB expansion files
                for obb_file in self.obb_files:
                    obb_arcname = f"Android/obb/{package_name}/{obb_file.name}"
                    self._debug(f"Adding OBB: {obb_file.name} -> {obb_arcname}")
                    zfd.write(obb_file, arcname=obb_arcname)

                # 4. Icon
                if self.icon:
                    self._debug("Adding icon.png")
                    zfd.writestr("icon.png", self.icon)

                # 5. Manifest
                self._debug("Adding manifest.json")
                manifest_json = json.dumps(self.manifest, indent=4).encode("utf-8")
                zfd.writestr("manifest.json", manifest_json)

            self._log(f"Success! XAPK generated at: {dest_path}")
            self.output_path = dest_path
            return dest_path

        except Exception:
            # Clean up partial archive on error
            if dest_path.exists():
                try:
                    dest_path.unlink()
                except OSError:
                    pass
            raise


def create_parser() -> argparse.ArgumentParser:
    """Create and configure the command-line argument parser."""
    parser = argparse.ArgumentParser(
        prog="xapktool",
        description="Modern tool to generate XAPK packages from Android APK, Split APKs, and OBB expansion files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  xapktool /path/to/apk_folder
  xapktool /path/to/apk_folder -o output.xapk
  xapktool /path/to/apk_folder -o /dist/folder --force
  xapktool /path/to/apk_folder --xapk-version 2
  xapktool /path/to/apk_folder --skip-verify
  xapktool /path/to/apk_folder --no-obb
""",
    )

    parser.add_argument(
        "directory",
        type=str,
        help="Path to directory containing the APK file and OBB files.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default=None,
        help="Custom output .xapk file path or destination directory.",
    )
    parser.add_argument(
        "--xapk-version",
        type=int,
        choices=[1, 2],
        default=2,
        help="XAPK specification version to target (1=legacy, 2=modern with split APKs; default: 2).",
    )
    parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Overwrite the output file if it already exists.",
    )
    parser.add_argument(
        "--skip-verify",
        action="store_true",
        help="Skip strict package name verification of OBB files.",
    )
    parser.add_argument(
        "--no-obb",
        "--allow-no-obb",
        dest="no_obb",
        action="store_true",
        help="Allow packaging an APK without OBB expansion files.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose debug output.",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress standard informative output.",
    )
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    return parser


def main(args: Optional[List[str]] = None) -> int:
    """CLI entrypoint function. Returns status exit code (0 for success)."""
    parser = create_parser()
    parsed_args = parser.parse_args(args)

    try:
        xapk = XAPK(
            folder=parsed_args.directory,
            output=parsed_args.output,
            xapk_version=parsed_args.xapk_version,
            skip_verify=parsed_args.skip_verify,
            no_obb=parsed_args.no_obb,
            force=parsed_args.force,
            verbose=parsed_args.verbose,
            quiet=parsed_args.quiet,
        )
        xapk.save()
        return 0
    except (FileNotFoundError, ValueError, FileExistsError, RuntimeError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nProcess interrupted by user.", file=sys.stderr)
        return 130
    except Exception as e:
        print(f"An unexpected error occurred: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
