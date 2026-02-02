"""
Mach-O binary parsing and manipulation.

This module handles reading and modifying Mach-O binaries,
specifically for extracting encryption information and patching
the cryptid field to mark binaries as decrypted.

References:
    - https://github.com/qyang-nj/llios
    - Apple Mach-O Reference
"""

from __future__ import annotations

import struct
import logging
from dataclasses import dataclass
from enum import IntEnum
from typing import Optional, BinaryIO

from orange.core.apps.decrypt.exceptions import MachOParseError

logger = logging.getLogger(__name__)


# Mach-O magic numbers
class MachOMagic(IntEnum):
    """Mach-O file magic numbers."""

    MH_MAGIC = 0xFEEDFACE  # 32-bit big-endian
    MH_CIGAM = 0xCEFAEDFE  # 32-bit little-endian
    MH_MAGIC_64 = 0xFEEDFACF  # 64-bit big-endian
    MH_CIGAM_64 = 0xCFFAEDFE  # 64-bit little-endian
    FAT_MAGIC = 0xCAFEBABE  # FAT binary big-endian
    FAT_CIGAM = 0xBEBAFECA  # FAT binary little-endian


# Mach-O CPU types
class MachOCPUType(IntEnum):
    """Mach-O CPU type identifiers."""

    ARM = 12
    ARM64 = 12 | 0x01000000  # CPU_ARCH_ABI64
    X86 = 7
    X86_64 = 7 | 0x01000000


# Load command types
class LoadCommand(IntEnum):
    """Mach-O load command types."""

    LC_SEGMENT = 0x1
    LC_SEGMENT_64 = 0x19
    LC_ENCRYPTION_INFO = 0x21
    LC_ENCRYPTION_INFO_64 = 0x2C


# Header sizes
MACH_HEADER_SIZE = 28  # 32-bit
MACH_HEADER_64_SIZE = 32  # 64-bit
FAT_HEADER_SIZE = 8
FAT_ARCH_SIZE = 20


@dataclass
class EncryptionInfo:
    """
    Encryption information from LC_ENCRYPTION_INFO(_64).

    Attributes:
        cryptoff: File offset to start of encrypted data.
        cryptsize: Size of encrypted data in bytes.
        cryptid: Encryption type (1 = encrypted, 0 = decrypted).
        cmd_offset: Offset of the load command in the file.
    """

    cryptoff: int
    cryptsize: int
    cryptid: int
    cmd_offset: int

    @property
    def is_encrypted(self) -> bool:
        """Check if the binary is encrypted."""
        return self.cryptid != 0


@dataclass
class MachOSlice:
    """
    Information about a single architecture slice in a Mach-O file.

    For non-FAT binaries, there is a single slice at offset 0.
    For FAT binaries, there may be multiple slices for different architectures.
    """

    offset: int  # Offset in file
    size: int  # Size of this slice
    cpu_type: MachOCPUType
    cpu_subtype: int
    is_64bit: bool
    encryption_info: Optional[EncryptionInfo] = None


@dataclass
class MachOBinary:
    """
    Parsed Mach-O binary information.

    Attributes:
        path: Original file path (if known).
        is_fat: Whether this is a FAT (universal) binary.
        slices: List of architecture slices.
    """

    path: Optional[str]
    is_fat: bool
    slices: list[MachOSlice]

    @property
    def encryption_info(self) -> Optional[EncryptionInfo]:
        """Get encryption info from the first encrypted slice."""
        for s in self.slices:
            if s.encryption_info and s.encryption_info.is_encrypted:
                return s.encryption_info
        # Return first slice's encryption info even if not encrypted
        for s in self.slices:
            if s.encryption_info:
                return s.encryption_info
        return None

    @property
    def is_encrypted(self) -> bool:
        """Check if any slice is encrypted."""
        return any(
            s.encryption_info and s.encryption_info.is_encrypted for s in self.slices
        )


class MachOParser:
    """
    Parser for Mach-O binary files.

    This class provides methods for parsing Mach-O headers,
    extracting encryption information, and patching binaries.

    Example:
        # Parse a binary
        binary = MachOParser.parse(data)
        if binary.is_encrypted:
            print(f"Encrypted: {binary.encryption_info.cryptsize} bytes")

        # Patch cryptid to 0
        patched = MachOParser.patch_cryptid(data)
    """

    @staticmethod
    def parse(data: bytes, path: Optional[str] = None) -> MachOBinary:
        """
        Parse a Mach-O binary from bytes.

        Args:
            data: Binary data to parse.
            path: Optional path for reference.

        Returns:
            MachOBinary with parsed information.

        Raises:
            MachOParseError: If the binary cannot be parsed.
        """
        if len(data) < 4:
            raise MachOParseError("Data too small to be a Mach-O binary")

        magic = struct.unpack("<I", data[:4])[0]

        # Check for FAT binary
        if magic in (MachOMagic.FAT_MAGIC, MachOMagic.FAT_CIGAM):
            return MachOParser._parse_fat(data, path)

        # Single architecture
        return MachOParser._parse_single(data, 0, len(data), path)

    @staticmethod
    def _parse_fat(data: bytes, path: Optional[str]) -> MachOBinary:
        """Parse a FAT (universal) binary."""
        magic = struct.unpack(">I", data[:4])[0]
        is_swap = magic == MachOMagic.FAT_CIGAM

        # Read number of architectures
        nfat_arch = struct.unpack(">I" if not is_swap else "<I", data[4:8])[0]
        logger.debug(f"FAT binary with {nfat_arch} architectures")

        slices = []
        offset = FAT_HEADER_SIZE

        for i in range(nfat_arch):
            # Read fat_arch structure
            fmt = ">IIIII" if not is_swap else "<IIIII"
            cpu_type, cpu_subtype, arch_offset, arch_size, align = struct.unpack(
                fmt, data[offset : offset + FAT_ARCH_SIZE]
            )
            offset += FAT_ARCH_SIZE

            # Parse this slice
            slice_data = data[arch_offset : arch_offset + arch_size]
            slice_info = MachOParser._parse_slice(
                slice_data, arch_offset, arch_size, cpu_type, cpu_subtype
            )
            if slice_info:
                slices.append(slice_info)

        return MachOBinary(path=path, is_fat=True, slices=slices)

    @staticmethod
    def _parse_single(
        data: bytes, offset: int, size: int, path: Optional[str]
    ) -> MachOBinary:
        """Parse a single-architecture Mach-O binary."""
        magic = struct.unpack("<I", data[:4])[0]

        if magic == MachOMagic.MH_MAGIC_64:
            is_64bit = True
            is_swap = False
        elif magic == MachOMagic.MH_CIGAM_64:
            is_64bit = True
            is_swap = True
        elif magic == MachOMagic.MH_MAGIC:
            is_64bit = False
            is_swap = False
        elif magic == MachOMagic.MH_CIGAM:
            is_64bit = False
            is_swap = True
        else:
            raise MachOParseError(f"Invalid Mach-O magic: 0x{magic:08x}")

        # Read header to get CPU type
        fmt = "<IIIIIIII" if not is_swap else ">IIIIIIII"
        if is_64bit:
            # 64-bit header has reserved field
            fmt = "<IIIIIIII" if not is_swap else ">IIIIIIII"

        header_size = MACH_HEADER_64_SIZE if is_64bit else MACH_HEADER_SIZE
        if len(data) < header_size:
            raise MachOParseError("Data too small for Mach-O header")

        header = struct.unpack(fmt, data[:header_size])
        cpu_type = header[1]
        cpu_subtype = header[2]

        slice_info = MachOParser._parse_slice(data, offset, size, cpu_type, cpu_subtype)

        return MachOBinary(
            path=path, is_fat=False, slices=[slice_info] if slice_info else []
        )

    @staticmethod
    def _parse_slice(
        data: bytes,
        file_offset: int,
        size: int,
        cpu_type: int,
        cpu_subtype: int,
    ) -> Optional[MachOSlice]:
        """Parse a single architecture slice."""
        if len(data) < 4:
            return None

        magic = struct.unpack("<I", data[:4])[0]

        # Determine if 64-bit and byte order
        if magic == MachOMagic.MH_MAGIC_64:
            is_64bit = True
            endian = "<"
        elif magic == MachOMagic.MH_CIGAM_64:
            is_64bit = True
            endian = ">"
        elif magic == MachOMagic.MH_MAGIC:
            is_64bit = False
            endian = "<"
        elif magic == MachOMagic.MH_CIGAM:
            is_64bit = False
            endian = ">"
        else:
            logger.warning(f"Unknown magic in slice: 0x{magic:08x}")
            return None

        header_size = MACH_HEADER_64_SIZE if is_64bit else MACH_HEADER_SIZE

        # Parse header
        if is_64bit:
            fmt = f"{endian}IIIIIIII"
        else:
            fmt = f"{endian}IIIIIII"

        header = struct.unpack(fmt, data[:header_size])
        ncmds = header[4]
        sizeofcmds = header[5]

        # Find encryption info in load commands
        encryption_info = MachOParser._find_encryption_info(
            data, header_size, ncmds, endian, file_offset
        )

        try:
            cpu_type_enum = MachOCPUType(cpu_type)
        except ValueError:
            cpu_type_enum = cpu_type  # type: ignore

        return MachOSlice(
            offset=file_offset,
            size=size,
            cpu_type=cpu_type_enum,
            cpu_subtype=cpu_subtype,
            is_64bit=is_64bit,
            encryption_info=encryption_info,
        )

    @staticmethod
    def _find_encryption_info(
        data: bytes,
        header_size: int,
        ncmds: int,
        endian: str,
        file_offset: int,
    ) -> Optional[EncryptionInfo]:
        """Find LC_ENCRYPTION_INFO(_64) load command."""
        offset = header_size

        for _ in range(ncmds):
            if offset + 8 > len(data):
                break

            cmd, cmdsize = struct.unpack(f"{endian}II", data[offset : offset + 8])

            if cmd in (LoadCommand.LC_ENCRYPTION_INFO, LoadCommand.LC_ENCRYPTION_INFO_64):
                # Parse encryption_info_command
                if cmd == LoadCommand.LC_ENCRYPTION_INFO_64:
                    # 64-bit: cmd, cmdsize, cryptoff, cryptsize, cryptid, pad
                    if offset + 24 > len(data):
                        break
                    cryptoff, cryptsize, cryptid = struct.unpack(
                        f"{endian}III", data[offset + 8 : offset + 20]
                    )
                else:
                    # 32-bit: cmd, cmdsize, cryptoff, cryptsize, cryptid
                    if offset + 20 > len(data):
                        break
                    cryptoff, cryptsize, cryptid = struct.unpack(
                        f"{endian}III", data[offset + 8 : offset + 20]
                    )

                logger.debug(
                    f"Found encryption info: cryptoff={cryptoff}, "
                    f"cryptsize={cryptsize}, cryptid={cryptid}"
                )

                return EncryptionInfo(
                    cryptoff=cryptoff,
                    cryptsize=cryptsize,
                    cryptid=cryptid,
                    cmd_offset=file_offset + offset,
                )

            offset += cmdsize

        return None

    @staticmethod
    def get_encryption_info(data: bytes) -> Optional[EncryptionInfo]:
        """
        Extract encryption info from binary data.

        Args:
            data: Binary data.

        Returns:
            EncryptionInfo if found, None otherwise.
        """
        try:
            binary = MachOParser.parse(data)
            return binary.encryption_info
        except MachOParseError:
            return None

    @staticmethod
    def is_encrypted(data: bytes) -> bool:
        """
        Check if a binary is FairPlay encrypted.

        Args:
            data: Binary data.

        Returns:
            True if encrypted, False otherwise.
        """
        info = MachOParser.get_encryption_info(data)
        return info is not None and info.is_encrypted

    @staticmethod
    def patch_cryptid(
        data: bytes,
        new_cryptid: int = 0,
        slice_offset: int = 0,
    ) -> bytes:
        """
        Patch the cryptid field in a Mach-O binary.

        This modifies the LC_ENCRYPTION_INFO(_64) load command
        to set cryptid to the specified value (typically 0 for decrypted).

        Args:
            data: Original binary data.
            new_cryptid: New cryptid value (default 0).
            slice_offset: Offset of the slice in FAT binary (default 0).

        Returns:
            Modified binary data with patched cryptid.

        Raises:
            MachOParseError: If encryption info not found.
        """
        # Parse to find the encryption info
        binary = MachOParser.parse(data)

        if not binary.encryption_info:
            raise MachOParseError("No encryption info found in binary")

        encryption_info = binary.encryption_info

        # Calculate the offset to the cryptid field
        # Structure: cmd (4), cmdsize (4), cryptoff (4), cryptsize (4), cryptid (4)
        cryptid_offset = encryption_info.cmd_offset + 16  # After cmd, cmdsize, cryptoff, cryptsize

        # Adjust for slice offset if this is part of a FAT binary read
        if slice_offset > 0:
            cryptid_offset = cryptid_offset - slice_offset

        logger.debug(f"Patching cryptid at offset {cryptid_offset} to {new_cryptid}")

        # Create mutable copy and patch
        result = bytearray(data)
        struct.pack_into("<I", result, cryptid_offset, new_cryptid)

        return bytes(result)

    @staticmethod
    def patch_binary_cryptid(
        binary_data: bytes,
        decrypted_section: bytes,
        encryption_info: EncryptionInfo,
    ) -> bytes:
        """
        Replace encrypted section with decrypted data and patch cryptid.

        This is the main method for creating a decrypted binary from
        a memory dump.

        Args:
            binary_data: Original encrypted binary.
            decrypted_section: Decrypted bytes from memory.
            encryption_info: Encryption info from the binary.

        Returns:
            Fully decrypted binary with cryptid=0.

        Raises:
            ValueError: If decrypted section size doesn't match.
        """
        if len(decrypted_section) != encryption_info.cryptsize:
            raise ValueError(
                f"Decrypted section size ({len(decrypted_section)}) "
                f"doesn't match cryptsize ({encryption_info.cryptsize})"
            )

        result = bytearray(binary_data)

        # Replace encrypted section with decrypted data
        start = encryption_info.cryptoff
        end = start + encryption_info.cryptsize
        result[start:end] = decrypted_section

        # Patch cryptid to 0
        result = bytearray(MachOParser.patch_cryptid(bytes(result), 0))

        return bytes(result)
