import json
import shutil
import tempfile
import zipfile
from pathlib import Path

import pytest

import xapktool
from xapktool import OBB_REGEX, XAPK, main


REAL_STUPAX_DIR = Path("/home/knight/GIT/com.StupaX.Flight")
REAL_PINGZERO_DIR = Path("/home/knight/GIT/com.pingzero.booster_was_XAPK")


class TestOBBRegex:
    """Validate strict Android OBB filename matching rules."""

    def test_valid_main_obb(self):
        match = OBB_REGEX.match("main.1.com.example.game.obb")
        assert match is not None
        assert match.group(1) == "main"
        assert match.group(2) == "1"
        assert match.group(3) == "com.example.game"

    def test_valid_patch_obb(self):
        match = OBB_REGEX.match("patch.105.org.test_app.pkg.obb")
        assert match is not None
        assert match.group(1) == "patch"
        assert match.group(2) == "105"
        assert match.group(3) == "org.test_app.pkg"

    def test_invalid_prefix(self):
        assert OBB_REGEX.match("foo.1.com.example.game.obb") is None
        assert OBB_REGEX.match("expansion.1.com.example.game.obb") is None

    def test_invalid_non_numeric_version(self):
        assert OBB_REGEX.match("main.abc.com.example.game.obb") is None
        assert OBB_REGEX.match("main.1a.com.example.game.obb") is None

    def test_invalid_single_segment_package(self):
        # Android packages require at least two dot-separated segments
        assert OBB_REGEX.match("main.1.single.obb") is None

    def test_invalid_extension(self):
        assert OBB_REGEX.match("main.1.com.example.game.zip") is None


class TestRealFixtures:
    """Tests executing against real-world APK/OBB fixtures."""

    def test_stupax_flight_v1_legacy(self, tmp_path):
        """Test Matrix A & B: Legacy v1 profile with single APK and main + patch OBBs."""
        out_file = tmp_path / "stupax_v1.xapk"
        tool = XAPK(
            folder=REAL_STUPAX_DIR,
            output=out_file,
            xapk_version=1,
            quiet=True,
        )
        dest = tool.save()
        assert dest.exists()
        assert dest.is_file()

        # Inspect manifest schema
        manifest = tool.manifest
        assert manifest["xapk_version"] == 1
        assert manifest["package_name"] == "com.StupaX.Flight"
        assert manifest["name"] == "Flight"
        assert manifest["version_code"] == 1
        assert manifest["version_name"] == "1.0"
        assert manifest["icon"] == "icon.png"
        assert len(manifest["expansions"]) == 2

        # Verify no modern v2 keys leaked into v1
        assert "split_apks" not in manifest
        assert "split_configs" not in manifest
        assert "locales_name" not in manifest

        # Inspect generated zip archive
        with zipfile.ZipFile(dest, "r") as zfd:
            names = set(zfd.namelist())
            assert "com.StupaX.Flight.apk" in names
            assert "Android/obb/com.StupaX.Flight/main.1.com.StupaX.Flight.obb" in names
            assert "Android/obb/com.StupaX.Flight/patch.1.com.StupaX.Flight.obb" in names
            assert "icon.png" in names
            assert "manifest.json" in names

    def test_stupax_flight_v2_modern(self, tmp_path):
        """Test Matrix A & B in modern v2 mode."""
        out_file = tmp_path / "stupax_v2.xapk"
        tool = XAPK(
            folder=REAL_STUPAX_DIR,
            output=out_file,
            xapk_version=2,
            quiet=True,
        )
        dest = tool.save()
        assert dest.exists()

        manifest = tool.manifest
        assert manifest["xapk_version"] == 2
        assert manifest["package_name"] == "com.StupaX.Flight"
        assert manifest["split_apks"] == [{"file": "com.StupaX.Flight.apk", "id": "base"}]
        assert len(manifest["expansions"]) == 2

    def test_pingzero_booster_v2_split_set(self, tmp_path):
        """Test Matrix G: Modern v2 profile with base APK + 2 split APKs."""
        out_file = tmp_path / "pingzero_v2.xapk"
        tool = XAPK(
            folder=REAL_PINGZERO_DIR,
            output=out_file,
            xapk_version=2,
            no_obb=True,
            quiet=True,
        )
        dest = tool.save()
        assert dest.exists()

        manifest = tool.manifest
        assert manifest["xapk_version"] == 2
        assert manifest["package_name"] == "com.pingzero.booster"
        assert manifest["split_configs"] == ["config.arm64_v8a", "config.mdpi"]
        assert len(manifest["split_apks"]) == 3
        assert manifest["split_apks"][0] == {"file": "com.pingzero.booster.apk", "id": "base"}
        assert manifest["split_apks"][1] == {"file": "config.arm64_v8a.apk", "id": "config.arm64_v8a"}
        assert manifest["split_apks"][2] == {"file": "config.mdpi.apk", "id": "config.mdpi"}
        assert manifest["total_size"] == 68313901  # Exact match to original manifest
        assert manifest["icon"] == "icon.png"

        # Verify archive contents
        with zipfile.ZipFile(dest, "r") as zfd:
            names = set(zfd.namelist())
            assert "com.pingzero.booster.apk" in names
            assert "config.arm64_v8a.apk" in names
            assert "config.mdpi.apk" in names
            assert "icon.png" in names
            assert "manifest.json" in names

    def test_pingzero_v1_rejects_splits(self, tmp_path):
        """Test Matrix J: XAPK v1 must reject split APKs."""
        out_file = tmp_path / "pingzero_v1.xapk"
        with pytest.raises(ValueError, match="XAPK v1 specification does not support split APKs"):
            XAPK(
                folder=REAL_PINGZERO_DIR,
                output=out_file,
                xapk_version=1,
                no_obb=True,
                quiet=True,
            )


class TestOBBValidationEdgeCases:
    """Synthetic tests for OBB edge cases, invalid names, and duplicates."""

    def test_mismatched_package_fails(self, tmp_path):
        """Test Matrix C: OBB with wrong package fails."""
        # Copy real APK
        shutil.copy(REAL_STUPAX_DIR / "com.StupaX.Flight.apk", tmp_path / "com.StupaX.Flight.apk")
        # Create mismatched OBB
        bad_obb = tmp_path / "main.1.com.other.package.obb"
        bad_obb.write_bytes(b"dummy")

        with pytest.raises(ValueError, match="package .* does not match APK package"):
            XAPK(folder=tmp_path, quiet=True)

        # --skip-verify allows it
        tool = XAPK(folder=tmp_path, skip_verify=True, quiet=True)
        assert len(tool.obb_expansions) == 1

    def test_invalid_obb_naming_fails(self, tmp_path):
        """Test Matrix D: Non-standard OBB naming fails."""
        shutil.copy(REAL_STUPAX_DIR / "com.StupaX.Flight.apk", tmp_path / "com.StupaX.Flight.apk")
        bad_obb = tmp_path / "foo.1.com.StupaX.Flight.obb"
        bad_obb.write_bytes(b"dummy")

        with pytest.raises(ValueError, match="does not follow Android naming convention"):
            XAPK(folder=tmp_path, quiet=True)

    def test_duplicate_main_obb_fails(self, tmp_path):
        """Test Matrix E: Multiple main OBBs fail."""
        shutil.copy(REAL_STUPAX_DIR / "com.StupaX.Flight.apk", tmp_path / "com.StupaX.Flight.apk")
        (tmp_path / "main.1.com.StupaX.Flight.obb").write_bytes(b"1")
        (tmp_path / "main.2.com.StupaX.Flight.obb").write_bytes(b"2")

        with pytest.raises(ValueError, match="Multiple main OBB files found"):
            XAPK(folder=tmp_path, quiet=True)

    def test_duplicate_patch_obb_fails(self, tmp_path):
        """Test Matrix E: Multiple patch OBBs fail."""
        shutil.copy(REAL_STUPAX_DIR / "com.StupaX.Flight.apk", tmp_path / "com.StupaX.Flight.apk")
        (tmp_path / "patch.1.com.StupaX.Flight.obb").write_bytes(b"1")
        (tmp_path / "patch.2.com.StupaX.Flight.obb").write_bytes(b"2")

        with pytest.raises(ValueError, match="Multiple patch OBB files found"):
            XAPK(folder=tmp_path, quiet=True)


class TestSplitAPKValidationEdgeCases:
    """Synthetic tests for split APK set coherence."""

    def test_mismatched_packages_fail(self, tmp_path):
        """Test Matrix H: Different packages in the same folder fail."""
        shutil.copy(REAL_STUPAX_DIR / "com.StupaX.Flight.apk", tmp_path / "com.StupaX.Flight.apk")
        shutil.copy(REAL_PINGZERO_DIR / "com.pingzero.booster.apk", tmp_path / "com.pingzero.booster.apk")

        with pytest.raises(ValueError, match="Incoherent APK set: multiple package names detected"):
            XAPK(folder=tmp_path, no_obb=True, quiet=True)

    def test_no_base_apk_fails(self, tmp_path):
        """Test Matrix H: Only split configuration APKs present without base fails."""
        shutil.copy(REAL_PINGZERO_DIR / "config.arm64_v8a.apk", tmp_path / "config.arm64_v8a.apk")
        shutil.copy(REAL_PINGZERO_DIR / "config.mdpi.apk", tmp_path / "config.mdpi.apk")

        with pytest.raises(ValueError, match="No base APK found in split set"):
            XAPK(folder=tmp_path, no_obb=True, quiet=True)


class TestIconFallbackAndOptions:
    """Tests for fallback icon, --no-obb, and overwrite behaviors."""

    def test_no_obb_flag(self, tmp_path):
        """Test Matrix K: Without --no-obb fails; with --no-obb succeeds."""
        shutil.copy(REAL_STUPAX_DIR / "com.StupaX.Flight.apk", tmp_path / "com.StupaX.Flight.apk")

        with pytest.raises(FileNotFoundError, match="No OBB files found"):
            XAPK(folder=tmp_path, quiet=True)

        tool = XAPK(folder=tmp_path, no_obb=True, quiet=True)
        assert tool.obb_expansions == []

    def test_force_overwrite(self, tmp_path):
        """Test Matrix L: Collision without --force fails; with --force succeeds."""
        out_file = tmp_path / "target.xapk"
        out_file.write_bytes(b"existing")

        with pytest.raises(FileExistsError, match="already exists"):
            tool = XAPK(folder=REAL_STUPAX_DIR, output=out_file, quiet=True)
            tool.save()

        tool = XAPK(folder=REAL_STUPAX_DIR, output=out_file, force=True, quiet=True)
        tool.save()
        assert out_file.stat().st_size > 1000

    def test_cli_main_success(self, tmp_path):
        """Test CLI main() entrypoint."""
        out_file = tmp_path / "cli_test.xapk"
        exit_code = main([
            str(REAL_STUPAX_DIR),
            "-o", str(out_file),
            "--xapk-version", "1",
            "--quiet",
        ])
        assert exit_code == 0
        assert out_file.exists()
