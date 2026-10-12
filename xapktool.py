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
import shutil
import sys
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

__version__ = "2.1.0"

# Suppress internal androguard permission resource mapping logs
logging.getLogger("androguard").setLevel(logging.ERROR)
try:
    from loguru import logger  # type: ignore
    logger.disable("androguard")
except ImportError:
    pass

# Robust import of APK across different androguard versions
try:
    from androguard.core.bytecodes.apk import APK  # type: ignore
except ImportError:
    try:
        from androguard.core.apk import APK  # type: ignore
    except ImportError:
        APK = None  # type: ignore

# 1x1 transparent PNG fallback bytes (67 bytes)
FALLBACK_ICON_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00"
    b"\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)

# Android OBB naming convention regex: [main|patch].<version-code>.<package-name>.obb
OBB_REGEX = re.compile(r"^(main|patch)\.([0-9]+)\.([a-zA-Z0-9_]+(?:\.[a-zA-Z0-9_]+)+)\.obb$")


@dataclass
class OBBExpansion:
    """Represents a validated Android OBB expansion file."""
    src: Path
    kind: str  # 'main' or 'patch'
    version: int
    package: str
    archive_path: str


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
        self.split_ids: Dict[Path, str] = {}
        self.obb_files: List[Path] = []
        self.obb_expansions: List[OBBExpansion] = []
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
    def _safe_int_or_str(val: Any) -> Any:
        """Safely convert value to integer if numeric, else string."""
        if val is None:
            return None
        try:
            return int(val)
        except (ValueError, TypeError):
            return str(val)

    def _categorize_apks(self, apk_candidates: List[Path]) -> Tuple[Path, List[Path], Dict[Path, str]]:
        """Identify the base APK, auxiliary split APKs, and validate consistency across the split set."""
        if len(apk_candidates) == 1:
            return apk_candidates[0], [], {}

        # Parse all candidate APKs
        parsed_apks: Dict[Path, APK] = {}
        for cand in apk_candidates:
            try:
                parsed_apks[cand] = APK(cand)
            except Exception as e:
                raise ValueError(f"Failed to parse candidate APK '{cand.name}': {e}")

        # 1. Validate package name consistency
        packages = {p: apk.get_package() for p, apk in parsed_apks.items()}
        unique_packages = set(packages.values())
        if len(unique_packages) > 1 or None in unique_packages:
            pkg_summary = {p.name: pkg for p, pkg in packages.items()}
            raise ValueError(
                f"Incoherent APK set: multiple package names detected ({pkg_summary}). "
                "All APKs must belong to the same package."
            )
        base_package = next(iter(unique_packages))

        # 2. Validate version code consistency
        version_codes = {p: str(apk.get_androidversion_code()) for p, apk in parsed_apks.items()}
        unique_versions = set(version_codes.values())
        if len(unique_versions) > 1:
            ver_summary = {p.name: ver for p, ver in version_codes.items()}
            raise ValueError(
                f"Incoherent APK set: mismatched version codes detected ({ver_summary}). "
                "All APKs must share the same version code."
            )

        # 3. Validate signing certificate consistency
        certs_map: Dict[Path, set] = {}
        for p, apk in parsed_apks.items():
            try:
                certs = set(c.sha256_fingerprint for c in (apk.get_certificates() or []))
                if certs:
                    certs_map[p] = certs
            except Exception:
                pass
        unique_certs = list(certs_map.values())
        if len(unique_certs) > 1 and not all(c == unique_certs[0] for c in unique_certs):
            err_msg = "Incoherent APK set: signing certificates differ between APKs."
            if not self.skip_verify:
                raise ValueError(f"{err_msg} Use --skip-verify to bypass.")
            self._log(f"Warning: {err_msg} (ignoring due to --skip-verify)")

        # 4. Identify base APK and splits
        base_candidates: List[Path] = []
        split_candidates: List[Path] = []
        split_id_map: Dict[Path, str] = {}

        for cand, apk in parsed_apks.items():
            split_attr = apk.get_attribute_value("manifest", "split")
            if split_attr:
                split_candidates.append(cand)
                split_id_map[cand] = str(split_attr)
            elif cand.name.lower() != "base.apk" and (
                cand.stem.lower().startswith("config.") or cand.stem.lower().startswith("split_")
            ):
                split_candidates.append(cand)
                sid = cand.stem[6:] if cand.stem.lower().startswith("split_") else cand.stem
                split_id_map[cand] = sid
            else:
                base_candidates.append(cand)

        if not base_candidates:
            raise ValueError(
                "No base APK found in split set. At least one APK must be the base application."
            )

        if len(base_candidates) > 1:
            # Check if one is named base.apk or matches package name
            named_bases = [
                b for b in base_candidates
                if b.stem.lower() == "base" or b.stem.lower() == str(base_package).lower()
            ]
            if len(named_bases) == 1:
                base_apk = named_bases[0]
                extra_splits = [b for b in base_candidates if b != base_apk]
                for extra in extra_splits:
                    split_candidates.append(extra)
                    split_id_map[extra] = extra.stem[6:] if extra.stem.startswith("split_") else extra.stem
            else:
                names = [b.name for b in base_candidates]
                raise ValueError(
                    f"Ambiguous base APK: found multiple candidates {names}. "
                    "Ensure there is exactly one base APK or name it 'base.apk'."
                )
        else:
            base_apk = base_candidates[0]

        return base_apk, split_candidates, split_id_map

    def _verify_and_collect_obbs(
        self,
        apk_package_name: str,
        apk_version_code: int,
        skip_verification: bool = False,
    ) -> List[OBBExpansion]:
        """Validate OBB filenames against Android naming conventions and APK version code."""
        expansions: List[OBBExpansion] = []
        bypass = self.skip_verify or skip_verification

        for obb_file in self.obb_files:
            match = OBB_REGEX.match(obb_file.name)
            archive_path = f"Android/obb/{apk_package_name}/{obb_file.name}"

            if not match:
                err_msg = (
                    f"OBB file '{obb_file.name}' does not follow Android naming convention: "
                    "[main|patch].<version-code>.<package-name>.obb."
                )
                if not bypass:
                    raise ValueError(f"{err_msg} Use --skip-verify to bypass.")
                self._log(f"Warning: {err_msg} (ignoring due to verification bypass)")
                parts = obb_file.stem.split(".")
                kind = "patch" if parts[0].lower() == "patch" else "main"
                expansions.append(
                    OBBExpansion(
                        src=obb_file,
                        kind=kind,
                        version=0,
                        package=apk_package_name,
                        archive_path=archive_path,
                    )
                )
                continue

            kind, version_str, obb_pkg = match.group(1), match.group(2), match.group(3)
            obb_version = int(version_str)

            expansions.append(
                OBBExpansion(
                    src=obb_file,
                    kind=kind,
                    version=obb_version,
                    package=obb_pkg,
                    archive_path=archive_path,
                )
            )

        # Enforce multiplicity, package, and version checks
        if not bypass:
            main_obbs = [o for o in expansions if o.kind == "main"]
            patch_obbs = [o for o in expansions if o.kind == "patch"]

            if len(main_obbs) > 1:
                err_msg = (
                    f"Multiple main OBB files found: {[o.src.name for o in main_obbs]}. "
                    "Android supports at most one main expansion."
                )
                raise ValueError(f"{err_msg} Use --skip-verify to bypass.")

            if len(patch_obbs) > 1:
                err_msg = (
                    f"Multiple patch OBB files found: {[o.src.name for o in patch_obbs]}. "
                    "Android supports at most one patch expansion."
                )
                raise ValueError(f"{err_msg} Use --skip-verify to bypass.")

            # Validate package name and expansion version for each expansion
            for o in expansions:
                if o.package != apk_package_name:
                    err_msg = (
                        f"OBB file '{o.src.name}' package ('{o.package}') does not match "
                        f"APK package ('{apk_package_name}')."
                    )
                    raise ValueError(f"{err_msg} Use --skip-verify to bypass.")

                if o.version != apk_version_code:
                    err_msg = (
                        f"OBB file '{o.src.name}' expansion version ({o.version}) does not match "
                        f"APK version code ({apk_version_code})."
                    )
                    raise ValueError(
                        f"{err_msg} Standard Android format requires matching version code. "
                        "Use --skip-verify to bypass."
                    )
        else:
            for o in expansions:
                if o.package != apk_package_name:
                    self._log(
                        f"Warning: OBB file '{o.src.name}' package ('{o.package}') does not match "
                        f"APK package ('{apk_package_name}') (ignoring due to verification bypass)"
                    )
                if o.version != apk_version_code:
                    self._log(
                        f"Warning: OBB file '{o.src.name}' expansion version ({o.version}) does not match "
                        f"APK version code ({apk_version_code}) (ignoring due to verification bypass)"
                    )

        return expansions

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

        self.apk_src, self.split_apks, self.split_ids = self._categorize_apks(apk_candidates)
        self._debug(f"Selected base APK: {self.apk_src.name}")
        if self.split_apks:
            self._log(f"Found {len(self.split_apks)} split configuration APK(s).")
            for split in self.split_apks:
                self._debug(f"Split APK: {split.name} (id: {self.split_ids.get(split)})")

        # Discover OBB files
        self.obb_files = sorted(self.folder.glob("*.obb"))
        is_split_setup = bool(self.split_apks)

        # In a split APK setup, OBB expansion files are optional by default
        if not self.obb_files and not self.no_obb and not is_split_setup:
            raise FileNotFoundError(
                f"No OBB files found in '{self.folder}'. "
                "If this APK does not require OBB expansions, run with --no-obb."
            )

        # Parse base APK metadata
        self._debug("Parsing APK metadata with androguard...")
        self.apk = APK(self.apk_src)

        apk_package_name = self.apk.get_package()
        if not apk_package_name:
            raise ValueError("Unable to determine package name from APK.")
        self._debug(f"APK Package: {apk_package_name}")

        # Validate APK version code
        raw_version_code = self.apk.get_androidversion_code()
        try:
            apk_version_code = int(raw_version_code)
            if apk_version_code < 0:
                raise ValueError(f"Negative version code: {apk_version_code}")
        except (ValueError, TypeError):
            raise ValueError(
                f"Invalid or missing Android version_code ({raw_version_code!r}) in APK '{self.apk_src.name}'."
            )

        # Enforce XAPK specification constraints
        if self.xapk_version == 1 and self.split_apks:
            raise ValueError(
                "XAPK v1 specification does not support split APKs. "
                "Please use '--xapk-version 2' to package split APKs."
            )

        # Verify and collect OBBs (skip verification if it's a split APK setup)
        if self.obb_files:
            if is_split_setup:
                self._debug("Split APK setup detected: skipping strict OBB verification.")
            else:
                self._debug("Verifying OBB files against APK package and version code...")
            self.obb_expansions = self._verify_and_collect_obbs(
                apk_package_name=apk_package_name,
                apk_version_code=apk_version_code,
                skip_verification=is_split_setup,
            )
        else:
            self.obb_expansions = []

        # Resolve app icon (prefer local icon.png, fallback to APK, then to transparent 1x1 PNG)
        local_icon = self.folder / "icon.png"
        if local_icon.is_file():
            try:
                self.icon = local_icon.read_bytes()
                self._debug(f"Loaded existing icon.png from directory ({len(self.icon)} bytes)")
            except Exception:
                self.icon = None

        if not self.icon:
            try:
                icon_path = self.apk.get_app_icon()
                if icon_path:
                    self.icon = self.apk.get_file(icon_path)
                    self._debug(f"Extracted icon from APK '{icon_path}' ({len(self.icon) if self.icon else 0} bytes)")
            except Exception as e:
                self._debug(f"Could not extract APK icon: {e}")
                self.icon = None

        if not self.icon:
            self.icon = FALLBACK_ICON_PNG
            self._debug("Using fallback 1x1 transparent PNG icon")

        # Build manifest
        self.manifest = self.make_manifest()
        self._log("Verification: OK")

    def make_manifest(self) -> Dict[str, Any]:
        """Construct the XAPK manifest dictionary according to the targeted specification profile."""
        if not self.apk_src or not self.apk:
            raise RuntimeError("APK source is not initialized.")

        package_name = self.apk.get_package()

        # Validate version code strictly
        raw_version_code = self.apk.get_androidversion_code()
        try:
            version_code = int(raw_version_code)
            if version_code < 0:
                raise ValueError(f"Negative version code: {version_code}")
        except (ValueError, TypeError):
            raise ValueError(
                f"Invalid or missing Android version_code ({raw_version_code!r}) in APK '{self.apk_src.name}'."
            )

        # App name resolution (safe against resources.arsc parse errors)
        try:
            app_name = self.apk.get_app_name()
        except Exception:
            app_name = None
        if not app_name or str(app_name).startswith("@"):
            app_name = package_name

        version_name = self.apk.get_androidversion_name() or "1.0"
        min_sdk = self._safe_int_or_str(self.apk.get_min_sdk_version())
        target_sdk = self._safe_int_or_str(self.apk.get_target_sdk_version())
        permissions = sorted(list(set(str(p) for p in (self.apk.get_permissions() or []) if p)))

        # Total uncompressed payload size (APKs and OBBs)
        total_size = self.apk_src.stat().st_size
        for split_file in self.split_apks:
            total_size += split_file.stat().st_size
        for obb in self.obb_expansions:
            total_size += obb.src.stat().st_size

        # OBB Expansions layout
        expansions_info = [
            {
                "file": obb.archive_path,
                "install_location": "EXTERNAL_STORAGE",
                "install_path": obb.archive_path,
            }
            for obb in self.obb_expansions
        ]

        if self.xapk_version == 1:
            # Clean, standardized legacy v1 manifest
            manifest: Dict[str, Any] = {
                "xapk_version": 1,
                "package_name": package_name,
                "name": str(app_name),
                "version_code": version_code,
                "version_name": str(version_name),
                "min_sdk_version": min_sdk,
                "target_sdk_version": target_sdk,
                "permissions": permissions,
                "total_size": total_size,
                "icon": "icon.png",
            }
            if expansions_info:
                manifest["expansions"] = expansions_info
            return manifest

        # Modern v2 manifest profile
        # Preserve full multi-locale dictionary if present in existing manifest.json
        locales_name: Dict[str, str] = {"en": str(app_name)}
        local_manifest_file = self.folder / "manifest.json"
        if local_manifest_file.is_file():
            try:
                with open(local_manifest_file, "r", encoding="utf-8") as f:
                    old_manifest = json.load(f)
                    if isinstance(old_manifest.get("locales_name"), dict):
                        locales_name = {str(k): str(v) for k, v in old_manifest["locales_name"].items()}
            except Exception:
                pass

        split_apks_info = [
            {
                "file": f"{package_name}.apk",
                "id": "base",
            }
        ]
        split_configs = []
        for split_file in self.split_apks:
            sid = self.split_ids.get(split_file, split_file.stem)
            split_apks_info.append({
                "file": split_file.name,
                "id": sid,
            })
            split_configs.append(sid)

        manifest = {
            "xapk_version": 2,
            "package_name": package_name,
            "name": str(app_name),
            "locales_name": locales_name,
            "version_code": str(version_code),
            "version_name": str(version_name),
            "min_sdk_version": str(min_sdk) if min_sdk is not None else None,
            "target_sdk_version": str(target_sdk) if target_sdk is not None else None,
            "permissions": permissions,
            "total_size": total_size,
            "icon": "icon.png",
            "split_apks": split_apks_info,
        }

        # Optional Max SDK
        try:
            max_sdk = self.apk.get_max_sdk_version()
            if max_sdk is not None:
                manifest["max_sdk_version"] = str(self._safe_int_or_str(max_sdk))
        except Exception:
            pass

        # Main launcher activity (critical for 3rd-party installers to launch app)
        try:
            main_activity = self.apk.get_main_activity()
            if main_activity:
                manifest["main_activity"] = str(main_activity)
        except Exception:
            pass

        # Native ABIs / Architecture
        native_abis = self._detect_native_code()
        if native_abis:
            manifest["native_code"] = native_abis

        # Hardware/software features (<uses-feature>)
        try:
            raw_features = self.apk.get_features()
            if raw_features:
                feats = sorted(list(set(str(f) for f in raw_features if f)))
                if feats:
                    manifest["features"] = feats
        except Exception:
            pass

        # Shared libraries (<uses-library>)
        try:
            raw_libs = self.apk.get_libraries()
            if raw_libs:
                libs = sorted(list(set(str(l) for l in raw_libs if l)))
                if libs:
                    manifest["libraries"] = libs
        except Exception:
            pass

        # Leanback / Android TV detection
        try:
            if self.apk.is_leanback() or self.apk.is_androidtv():
                manifest["is_leanback"] = True
        except Exception:
            pass

        # Wearable / Wear OS detection
        try:
            if self.apk.is_wearable():
                manifest["is_wearable"] = True
        except Exception:
            pass

        if split_configs:
            manifest["split_configs"] = split_configs

        if expansions_info:
            manifest["expansions"] = expansions_info

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

    @staticmethod
    def _safe_zip_write(zfd: zipfile.ZipFile, file_path: Path, arcname: str) -> None:
        """Write a file to ZipFile, clamping timestamp to at least 1980-01-01 to avoid ZIP errors."""
        stat = file_path.stat()
        mtime = time.localtime(stat.st_mtime)
        if mtime.tm_year < 1980:
            date_time = (1980, 1, 1, 0, 0, 0)
        else:
            date_time = (mtime.tm_year, mtime.tm_mon, mtime.tm_mday, mtime.tm_hour, mtime.tm_min, mtime.tm_sec)

        zinfo = zipfile.ZipInfo(arcname, date_time=date_time)
        zinfo.compress_type = zfd.compression
        zinfo.external_attr = (stat.st_mode & 0xFFFF) << 16

        with file_path.open("rb") as src, zfd.open(zinfo, "w") as dst:
            shutil.copyfileobj(src, dst)

    def save(self) -> Path:
        """Create the .xapk zip archive directly and verify archive integrity."""
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
                self._safe_zip_write(zfd, self.apk_src, arcname=apk_arcname)

                # 2. Split APKs (if present)
                for split_file in self.split_apks:
                    self._debug(f"Adding Split APK: {split_file.name}")
                    self._safe_zip_write(zfd, split_file, arcname=split_file.name)

                # 3. OBB expansion files
                for obb in self.obb_expansions:
                    self._debug(f"Adding OBB: {obb.src.name} -> {obb.archive_path}")
                    self._safe_zip_write(zfd, obb.src, arcname=obb.archive_path)

                # 4. Icon
                if self.icon:
                    self._debug("Adding icon.png")
                    zfd.writestr("icon.png", self.icon)

                # 5. Manifest
                self._debug("Adding manifest.json")
                manifest_json = json.dumps(self.manifest, indent=4).encode("utf-8")
                zfd.writestr("manifest.json", manifest_json)

            # Strict archive integrity verification
            with zipfile.ZipFile(dest_path, "r") as zfd:
                written_entries = set(zfd.namelist())

            if f"{package_name}.apk" not in written_entries:
                raise RuntimeError(f"Archive integrity error: '{package_name}.apk' is missing.")
            for split_file in self.split_apks:
                if split_file.name not in written_entries:
                    raise RuntimeError(f"Archive integrity error: split '{split_file.name}' is missing.")
            for obb in self.obb_expansions:
                if obb.archive_path not in written_entries:
                    raise RuntimeError(f"Archive integrity error: OBB '{obb.archive_path}' is missing.")
            if "icon.png" not in written_entries:
                raise RuntimeError("Archive integrity error: 'icon.png' is missing.")
            if "manifest.json" not in written_entries:
                raise RuntimeError("Archive integrity error: 'manifest.json' is missing.")

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
  xapktool /path/to/apk_folder --xapk-version 1
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
