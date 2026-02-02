"""Tests for IPA builder."""

import struct
import zipfile
import tempfile
import shutil
from pathlib import Path

import pytest

from orange.core.apps.decrypt.ipa_builder import IPABuilder, build_ipa_simple
from orange.core.apps.decrypt.macho import EncryptionInfo, MachOMagic, MachOCPUType
from orange.core.apps.decrypt.exceptions import DecryptionError


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    path = Path(tempfile.mkdtemp())
    yield path
    shutil.rmtree(path, ignore_errors=True)


@pytest.fixture
def sample_app_bundle(temp_dir):
    """Create a minimal app bundle for testing."""
    app_path = temp_dir / "TestApp.app"
    app_path.mkdir()

    # Create Info.plist
    info_plist = app_path / "Info.plist"
    info_plist.write_bytes(
        b'<?xml version="1.0" encoding="UTF-8"?>\n'
        b'<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
        b'"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
        b'<plist version="1.0">\n'
        b"<dict>\n"
        b"    <key>CFBundleExecutable</key>\n"
        b"    <string>TestApp</string>\n"
        b"    <key>CFBundleIdentifier</key>\n"
        b"    <string>com.test.app</string>\n"
        b"</dict>\n"
        b"</plist>"
    )

    # Create fake encrypted binary
    binary = _create_fake_encrypted_binary()
    (app_path / "TestApp").write_bytes(binary)

    # Create some resources
    (app_path / "Assets.car").write_bytes(b"fake assets")

    return app_path


def _create_fake_encrypted_binary():
    """Create a minimal encrypted Mach-O binary for testing."""
    # Mach-O 64-bit header
    header = struct.pack(
        "<IIIIIIII",
        MachOMagic.MH_MAGIC_64,  # magic
        MachOCPUType.ARM64,  # cpu type
        0,  # cpu subtype
        2,  # filetype (executable)
        1,  # ncmds
        24,  # sizeofcmds
        0,  # flags
        0,  # reserved
    )

    # LC_ENCRYPTION_INFO_64 command
    enc_cmd = struct.pack(
        "<IIIIII",
        0x2C,  # cmd (LC_ENCRYPTION_INFO_64)
        24,  # cmdsize
        32 + 24,  # cryptoff (after header + cmd)
        16,  # cryptsize
        1,  # cryptid (encrypted)
        0,  # pad
    )

    # "Encrypted" section
    encrypted_section = b"ENCRYPTED_DATA!!"  # 16 bytes

    # Padding
    padding = b"\x00" * 100

    return header + enc_cmd + encrypted_section + padding


class TestIPABuilder:
    """Test IPABuilder class."""

    def test_build_creates_valid_ipa(self, sample_app_bundle, temp_dir):
        """Should create a valid IPA ZIP file."""
        output_path = temp_dir / "output.ipa"

        # Create mock dump info
        class MockDumpInfo:
            name = "TestApp"
            path = str(sample_app_bundle / "TestApp")
            decrypted_section = b"DECRYPTED_DATA!!"  # 16 bytes
            encryption_info = EncryptionInfo(
                cryptoff=32 + 24,
                cryptsize=16,
                cryptid=1,
                cmd_offset=32,
            )

        builder = IPABuilder()
        result = builder.build(
            app_bundle_path=sample_app_bundle,
            output_path=output_path,
            main_binary_dump=MockDumpInfo(),
        )

        assert result.exists()
        assert result.suffix == ".ipa"

        # Verify it's a valid ZIP
        with zipfile.ZipFile(result, "r") as zf:
            names = zf.namelist()
            assert any("Payload/TestApp.app/TestApp" in n for n in names)
            assert any("Payload/TestApp.app/Info.plist" in n for n in names)

    def test_build_replaces_binary(self, sample_app_bundle, temp_dir):
        """Should replace binary with decrypted version."""
        output_path = temp_dir / "output.ipa"

        class MockDumpInfo:
            name = "TestApp"
            path = str(sample_app_bundle / "TestApp")
            decrypted_section = b"DECRYPTED_DATA!!"
            encryption_info = EncryptionInfo(
                cryptoff=32 + 24,
                cryptsize=16,
                cryptid=1,
                cmd_offset=32,
            )

        builder = IPABuilder()
        builder.build(
            app_bundle_path=sample_app_bundle,
            output_path=output_path,
            main_binary_dump=MockDumpInfo(),
        )

        # Extract and verify binary contains decrypted data
        with zipfile.ZipFile(output_path, "r") as zf:
            for name in zf.namelist():
                if name.endswith("/TestApp"):
                    binary_data = zf.read(name)
                    assert b"DECRYPTED_DATA!!" in binary_data
                    assert b"ENCRYPTED_DATA!!" not in binary_data
                    break
            else:
                pytest.fail("Binary not found in IPA")

    def test_build_app_not_found(self, temp_dir):
        """Should raise when app bundle doesn't exist."""
        builder = IPABuilder()

        with pytest.raises(DecryptionError):
            builder.build(
                app_bundle_path=temp_dir / "nonexistent.app",
                output_path=temp_dir / "output.ipa",
                main_binary_dump=None,
            )

    def test_build_with_work_dir(self, sample_app_bundle, temp_dir):
        """Should use specified work directory."""
        output_path = temp_dir / "output.ipa"
        work_dir = temp_dir / "work"

        class MockDumpInfo:
            name = "TestApp"
            path = str(sample_app_bundle / "TestApp")
            decrypted_section = b"DECRYPTED_DATA!!"
            encryption_info = EncryptionInfo(
                cryptoff=32 + 24,
                cryptsize=16,
                cryptid=1,
                cmd_offset=32,
            )

        builder = IPABuilder(work_dir=work_dir)
        builder.build(
            app_bundle_path=sample_app_bundle,
            output_path=output_path,
            main_binary_dump=MockDumpInfo(),
        )

        assert output_path.exists()

    def test_build_creates_output_directory(self, sample_app_bundle, temp_dir):
        """Should create output directory if it doesn't exist."""
        output_path = temp_dir / "subdir" / "output.ipa"

        class MockDumpInfo:
            name = "TestApp"
            path = str(sample_app_bundle / "TestApp")
            decrypted_section = b"DECRYPTED_DATA!!"
            encryption_info = EncryptionInfo(
                cryptoff=32 + 24,
                cryptsize=16,
                cryptid=1,
                cmd_offset=32,
            )

        builder = IPABuilder()
        result = builder.build(
            app_bundle_path=sample_app_bundle,
            output_path=output_path,
            main_binary_dump=MockDumpInfo(),
        )

        assert result.exists()
        assert result.parent.exists()


class TestIPABuilderFrameworks:
    """Test framework handling."""

    def test_build_with_frameworks(self, temp_dir):
        """Should handle embedded frameworks."""
        # Create app with framework
        app_path = temp_dir / "TestApp.app"
        app_path.mkdir()

        # Info.plist
        info_plist = app_path / "Info.plist"
        info_plist.write_bytes(
            b'<?xml version="1.0" encoding="UTF-8"?>\n'
            b'<plist version="1.0"><dict>'
            b"<key>CFBundleExecutable</key><string>TestApp</string>"
            b"</dict></plist>"
        )

        # Main binary
        (app_path / "TestApp").write_bytes(_create_fake_encrypted_binary())

        # Framework
        framework_path = app_path / "Frameworks" / "TestFramework.framework"
        framework_path.mkdir(parents=True)
        (framework_path / "TestFramework").write_bytes(_create_fake_encrypted_binary())

        output_path = temp_dir / "output.ipa"

        class MockMainDump:
            name = "TestApp"
            path = str(app_path / "TestApp")
            decrypted_section = b"DECRYPTED_DATA!!"
            encryption_info = EncryptionInfo(
                cryptoff=32 + 24, cryptsize=16, cryptid=1, cmd_offset=32
            )

        class MockFrameworkDump:
            name = "TestFramework"
            path = str(framework_path / "TestFramework")
            decrypted_section = b"FRAMEWORK_DECRYP"
            encryption_info = EncryptionInfo(
                cryptoff=32 + 24, cryptsize=16, cryptid=1, cmd_offset=32
            )

        builder = IPABuilder()
        builder.build(
            app_bundle_path=app_path,
            output_path=output_path,
            main_binary_dump=MockMainDump(),
            framework_dumps=[MockFrameworkDump()],
        )

        # Verify IPA contains framework
        with zipfile.ZipFile(output_path, "r") as zf:
            framework_found = any(
                "TestFramework.framework" in n for n in zf.namelist()
            )
            assert framework_found


class TestBuildIPASimple:
    """Test simplified IPA builder function."""

    def test_build_ipa_simple(self, temp_dir):
        """Should create IPA with provided binary."""
        # Create minimal app
        app_path = temp_dir / "Simple.app"
        app_path.mkdir()
        (app_path / "Info.plist").write_bytes(b"<plist></plist>")
        (app_path / "Simple").write_bytes(b"original")

        output_path = temp_dir / "output.ipa"
        decrypted_binary = b"decrypted_binary_content"

        result = build_ipa_simple(
            app_bundle=app_path,
            output_path=output_path,
            decrypted_binary=decrypted_binary,
            executable_name="Simple",
        )

        assert result.exists()

        # Verify binary was replaced
        with zipfile.ZipFile(result, "r") as zf:
            for name in zf.namelist():
                if name.endswith("/Simple"):
                    assert zf.read(name) == decrypted_binary
                    break
