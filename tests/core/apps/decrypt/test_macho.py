"""Tests for Mach-O binary parsing and manipulation."""

import struct
import pytest

from orange.core.apps.decrypt.macho import (
    MachOParser,
    MachOBinary,
    MachOSlice,
    EncryptionInfo,
    MachOMagic,
    MachOCPUType,
    LoadCommand,
    MachOParseError,
)


class TestEncryptionInfo:
    """Test EncryptionInfo dataclass."""

    def test_is_encrypted_when_cryptid_nonzero(self):
        """Should report encrypted when cryptid is not 0."""
        info = EncryptionInfo(
            cryptoff=4096,
            cryptsize=1024,
            cryptid=1,
            cmd_offset=100,
        )
        assert info.is_encrypted is True

    def test_is_not_encrypted_when_cryptid_zero(self):
        """Should report not encrypted when cryptid is 0."""
        info = EncryptionInfo(
            cryptoff=4096,
            cryptsize=1024,
            cryptid=0,
            cmd_offset=100,
        )
        assert info.is_encrypted is False


class TestMachOBinary:
    """Test MachOBinary dataclass."""

    def test_encryption_info_returns_first_encrypted_slice(self):
        """Should return encryption info from first encrypted slice."""
        enc_info = EncryptionInfo(4096, 1024, 1, 100)
        slices = [
            MachOSlice(0, 1000, MachOCPUType.ARM64, 0, True, None),
            MachOSlice(1000, 1000, MachOCPUType.ARM64, 0, True, enc_info),
        ]
        binary = MachOBinary(path=None, is_fat=True, slices=slices)
        assert binary.encryption_info == enc_info

    def test_is_encrypted_true_when_any_slice_encrypted(self):
        """Should report encrypted if any slice is encrypted."""
        enc_info = EncryptionInfo(4096, 1024, 1, 100)
        slices = [
            MachOSlice(0, 1000, MachOCPUType.ARM64, 0, True, None),
            MachOSlice(1000, 1000, MachOCPUType.ARM64, 0, True, enc_info),
        ]
        binary = MachOBinary(path=None, is_fat=True, slices=slices)
        assert binary.is_encrypted is True

    def test_is_encrypted_false_when_no_slice_encrypted(self):
        """Should report not encrypted if no slice is encrypted."""
        enc_info = EncryptionInfo(4096, 1024, 0, 100)  # cryptid=0
        slices = [
            MachOSlice(0, 1000, MachOCPUType.ARM64, 0, True, enc_info),
        ]
        binary = MachOBinary(path=None, is_fat=False, slices=slices)
        assert binary.is_encrypted is False


class TestMachOParser:
    """Test MachOParser methods."""

    def _create_macho_header(
        self,
        magic: int = MachOMagic.MH_MAGIC_64,
        cpu_type: int = MachOCPUType.ARM64,
        cpu_subtype: int = 0,
        filetype: int = 2,  # MH_EXECUTE
        ncmds: int = 0,
        sizeofcmds: int = 0,
        flags: int = 0,
    ) -> bytes:
        """Create a minimal Mach-O header."""
        # 64-bit header: magic, cpu_type, cpu_subtype, filetype, ncmds, sizeofcmds, flags, reserved
        return struct.pack(
            "<IIIIIIII",
            magic,
            cpu_type,
            cpu_subtype,
            filetype,
            ncmds,
            sizeofcmds,
            flags,
            0,  # reserved
        )

    def _create_encryption_cmd(
        self,
        cryptoff: int = 4096,
        cryptsize: int = 1024,
        cryptid: int = 1,
        is_64bit: bool = True,
    ) -> bytes:
        """Create an LC_ENCRYPTION_INFO(_64) load command."""
        if is_64bit:
            cmd = LoadCommand.LC_ENCRYPTION_INFO_64
            # cmd, cmdsize, cryptoff, cryptsize, cryptid, pad
            return struct.pack("<IIIIII", cmd, 24, cryptoff, cryptsize, cryptid, 0)
        else:
            cmd = LoadCommand.LC_ENCRYPTION_INFO
            # cmd, cmdsize, cryptoff, cryptsize, cryptid
            return struct.pack("<IIIII", cmd, 20, cryptoff, cryptsize, cryptid)

    def test_parse_detects_64bit_magic(self):
        """Should correctly detect 64-bit Mach-O magic."""
        header = self._create_macho_header(MachOMagic.MH_MAGIC_64)
        data = header + b"\x00" * 100  # Padding

        binary = MachOParser.parse(data)

        assert len(binary.slices) == 1
        assert binary.slices[0].is_64bit is True

    def test_parse_finds_encryption_info(self):
        """Should find LC_ENCRYPTION_INFO_64 in load commands."""
        enc_cmd = self._create_encryption_cmd(cryptoff=4096, cryptsize=2048, cryptid=1)
        header = self._create_macho_header(
            ncmds=1, sizeofcmds=len(enc_cmd)
        )
        data = header + enc_cmd + b"\x00" * 100

        binary = MachOParser.parse(data)

        assert binary.encryption_info is not None
        assert binary.encryption_info.cryptoff == 4096
        assert binary.encryption_info.cryptsize == 2048
        assert binary.encryption_info.cryptid == 1
        assert binary.is_encrypted is True

    def test_parse_no_encryption_info(self):
        """Should handle binaries without encryption info."""
        header = self._create_macho_header(ncmds=0, sizeofcmds=0)
        data = header + b"\x00" * 100

        binary = MachOParser.parse(data)

        assert binary.encryption_info is None
        assert binary.is_encrypted is False

    def test_parse_too_small_raises_error(self):
        """Should raise error for data too small to be Mach-O."""
        with pytest.raises(MachOParseError):
            MachOParser.parse(b"\x00\x00\x00")

    def test_parse_invalid_magic_raises_error(self):
        """Should raise error for invalid magic number."""
        data = b"\x00\x00\x00\x00" + b"\x00" * 100
        with pytest.raises(MachOParseError):
            MachOParser.parse(data)

    def test_get_encryption_info_convenience_method(self):
        """get_encryption_info should work as convenience method."""
        enc_cmd = self._create_encryption_cmd(cryptoff=8192, cryptsize=4096, cryptid=1)
        header = self._create_macho_header(ncmds=1, sizeofcmds=len(enc_cmd))
        data = header + enc_cmd + b"\x00" * 100

        info = MachOParser.get_encryption_info(data)

        assert info is not None
        assert info.cryptoff == 8192
        assert info.cryptsize == 4096

    def test_get_encryption_info_returns_none_on_invalid(self):
        """get_encryption_info should return None for invalid data."""
        info = MachOParser.get_encryption_info(b"invalid")
        assert info is None

    def test_is_encrypted_convenience_method(self):
        """is_encrypted should work as convenience method."""
        enc_cmd = self._create_encryption_cmd(cryptid=1)
        header = self._create_macho_header(ncmds=1, sizeofcmds=len(enc_cmd))
        data = header + enc_cmd + b"\x00" * 100

        assert MachOParser.is_encrypted(data) is True

    def test_is_encrypted_returns_false_for_decrypted(self):
        """is_encrypted should return False when cryptid=0."""
        enc_cmd = self._create_encryption_cmd(cryptid=0)
        header = self._create_macho_header(ncmds=1, sizeofcmds=len(enc_cmd))
        data = header + enc_cmd + b"\x00" * 100

        assert MachOParser.is_encrypted(data) is False

    def test_patch_cryptid_sets_to_zero(self):
        """patch_cryptid should set cryptid to 0."""
        enc_cmd = self._create_encryption_cmd(cryptid=1)
        header = self._create_macho_header(ncmds=1, sizeofcmds=len(enc_cmd))
        data = header + enc_cmd + b"\x00" * 100

        patched = MachOParser.patch_cryptid(data, new_cryptid=0)

        # Verify the patched binary
        new_info = MachOParser.get_encryption_info(patched)
        assert new_info is not None
        assert new_info.cryptid == 0

    def test_patch_cryptid_preserves_other_fields(self):
        """patch_cryptid should not modify other fields."""
        enc_cmd = self._create_encryption_cmd(
            cryptoff=4096, cryptsize=2048, cryptid=1
        )
        header = self._create_macho_header(ncmds=1, sizeofcmds=len(enc_cmd))
        data = header + enc_cmd + b"\x00" * 100

        patched = MachOParser.patch_cryptid(data, new_cryptid=0)

        new_info = MachOParser.get_encryption_info(patched)
        assert new_info.cryptoff == 4096
        assert new_info.cryptsize == 2048

    def test_patch_cryptid_raises_without_encryption_info(self):
        """patch_cryptid should raise when no encryption info exists."""
        header = self._create_macho_header(ncmds=0, sizeofcmds=0)
        data = header + b"\x00" * 100

        with pytest.raises(MachOParseError):
            MachOParser.patch_cryptid(data)

    def test_patch_binary_cryptid_replaces_encrypted_section(self):
        """patch_binary_cryptid should replace encrypted section."""
        # Create a binary with "encrypted" data
        enc_cmd = self._create_encryption_cmd(
            cryptoff=32 + 24,  # After header + cmd
            cryptsize=16,
            cryptid=1,
        )
        header = self._create_macho_header(ncmds=1, sizeofcmds=len(enc_cmd))
        encrypted_data = b"ENCRYPTED_DATA!!"  # 16 bytes
        data = header + enc_cmd + encrypted_data + b"\x00" * 100

        # Decrypted replacement
        decrypted_section = b"DECRYPTED_DATA!!"

        # Get encryption info
        info = MachOParser.get_encryption_info(data)

        # Patch
        result = MachOParser.patch_binary_cryptid(data, decrypted_section, info)

        # Verify decrypted data is in place
        assert decrypted_section in result
        assert encrypted_data not in result

        # Verify cryptid is 0
        new_info = MachOParser.get_encryption_info(result)
        assert new_info.cryptid == 0

    def test_patch_binary_cryptid_wrong_size_raises(self):
        """patch_binary_cryptid should raise for wrong section size."""
        enc_cmd = self._create_encryption_cmd(cryptsize=16, cryptid=1)
        header = self._create_macho_header(ncmds=1, sizeofcmds=len(enc_cmd))
        data = header + enc_cmd + b"\x00" * 100

        info = MachOParser.get_encryption_info(data)

        with pytest.raises(ValueError):
            MachOParser.patch_binary_cryptid(
                data,
                b"wrong_size",  # Not 16 bytes
                info,
            )


class TestMachOParserEdgeCases:
    """Test edge cases and error handling."""

    def test_parse_with_path(self):
        """Should store path in binary object."""
        header = struct.pack(
            "<IIIIIIII",
            MachOMagic.MH_MAGIC_64,
            MachOCPUType.ARM64,
            0, 2, 0, 0, 0, 0,
        )
        data = header + b"\x00" * 100

        binary = MachOParser.parse(data, path="/path/to/binary")

        assert binary.path == "/path/to/binary"

    def test_parse_handles_big_endian(self):
        """Should handle big-endian magic."""
        # MH_CIGAM_64 is big-endian 64-bit
        header = struct.pack(
            ">IIIIIIII",
            MachOMagic.MH_CIGAM_64,
            MachOCPUType.ARM64,
            0, 2, 0, 0, 0, 0,
        )
        data = header + b"\x00" * 100

        binary = MachOParser.parse(data)

        assert len(binary.slices) == 1
        assert binary.slices[0].is_64bit is True
