"""
PCIe Transaction Layer Packet (TLP) data structures.
Defines the core types, headers, and packet format per PCIe specification.

A TLP is the fundamental communication unit in PCIe. Each TLP has:
- Header: describes the transaction type, addressing, and routing
- Data payload: optional, present in write and completion-with-data packets
- An optional ECRC (End-to-End CRC) digest
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class TLPType(Enum):
    """
    PCIe TLP types with their format/type encoding.
    Format is top 3 bits, type is bottom 5 bits of the Fmt/Type field.

    Format encoding:
      000 = 3 DW header, no data
      001 = 4 DW header, no data
      010 = 3 DW header, with data
      011 = 4 DW header, with data
    """
    # Memory transactions
    MRd32  = (0b000, 0b00000, "Memory Read 32-bit")
    MRd64  = (0b001, 0b00000, "Memory Read 64-bit")
    MWr32  = (0b010, 0b00000, "Memory Write 32-bit")
    MWr64  = (0b011, 0b00000, "Memory Write 64-bit")

    # IO transactions
    IORd   = (0b000, 0b00010, "IO Read")
    IOWr   = (0b010, 0b00010, "IO Write")

    # Configuration transactions (Type 0 = local device)
    CfgRd0 = (0b000, 0b00100, "Config Read Type 0")
    CfgWr0 = (0b010, 0b00100, "Config Write Type 0")

    # Completion transactions
    Cpl    = (0b000, 0b01010, "Completion without Data")
    CplD   = (0b010, 0b01010, "Completion with Data")

    # Message transactions
    Msg    = (0b001, 0b10000, "Message")
    MsgD   = (0b011, 0b10000, "Message with Data")

    def __init__(self, fmt, type_code, description):
        self.fmt = fmt
        self.type_code = type_code
        self.description = description

    @property
    def has_data(self) -> bool:
        """Whether this TLP type carries a data payload."""
        return self.fmt in (0b010, 0b011)

    @property
    def has_4dw_header(self) -> bool:
        """Whether this TLP type uses a 4-doubleword header (64-bit addressing)."""
        return self.fmt in (0b001, 0b011)

    @property
    def is_posted(self) -> bool:
        """Whether this is a posted transaction (no completion expected)."""
        return self in (TLPType.MWr32, TLPType.MWr64,
                        TLPType.Msg, TLPType.MsgD)

    @property
    def is_completion(self) -> bool:
        """Whether this is a completion TLP."""
        return self in (TLPType.Cpl, TLPType.CplD)

    @property
    def short_name(self) -> str:
        """Short display name."""
        return self.name


class CompletionStatus(Enum):
    """PCIe completion status codes."""
    SC  = (0b000, "Successful Completion")
    UR  = (0b001, "Unsupported Request")
    CRS = (0b010, "Configuration Request Retry Status")
    CA  = (0b100, "Completer Abort")

    def __init__(self, code, description):
        self.code = code
        self.description = description


@dataclass
class DeviceID:
    """
    PCIe device identifier: Bus / Device / Function.
    Used as requester ID and completer ID in TLP headers.
    """
    bus: int        # 0-255
    device: int     # 0-31
    function: int   # 0-7

    def __post_init__(self):
        assert 0 <= self.bus <= 255, f"Bus must be 0-255, got {self.bus}"
        assert 0 <= self.device <= 31, f"Device must be 0-31, got {self.device}"
        assert 0 <= self.function <= 7, f"Function must be 0-7, got {self.function}"

    def __str__(self):
        return f"{self.bus:02X}:{self.device:02X}.{self.function}"

    def to_int(self) -> int:
        """Encode as 16-bit BDF value."""
        return (self.bus << 8) | (self.device << 3) | self.function


@dataclass
class TLPHeader:
    """
    PCIe TLP header fields.
    Different TLP types use different subsets of these fields.
    """
    tlp_type: TLPType
    tc: int = 0                 # Traffic Class (0-7)
    td: bool = False            # TLP Digest present
    ep: bool = False            # Error Poisoned
    attr: int = 0               # Attributes (2 bits: relaxed ordering, no snoop)
    length: int = 0             # Payload length in doublewords (0 = 1024 DW)

    # Requester/Completer identification
    requester_id: DeviceID = field(default_factory=lambda: DeviceID(0, 0, 0))
    tag: int = 0                # Transaction tag (0-255)

    # Address (for memory/IO transactions)
    address: int = 0            # Target address

    # Completion-specific fields
    completer_id: Optional[DeviceID] = None
    status: CompletionStatus = CompletionStatus.SC
    byte_count: int = 0         # Remaining bytes for completion
    lower_address: int = 0      # Lower address bits for completion


@dataclass
class TLP:
    """
    A complete PCIe Transaction Layer Packet.
    Contains the header, optional data payload, and metadata.
    """
    header: TLPHeader
    data: bytes = b""           # Payload data (empty for reads/completions)
    timestamp: int = 0          # Simulation time (for ordering)

    @property
    def tlp_type(self) -> TLPType:
        return self.header.tlp_type

    @property
    def has_data(self) -> bool:
        return self.tlp_type.has_data

    @property
    def is_posted(self) -> bool:
        return self.tlp_type.is_posted

    @property
    def is_completion(self) -> bool:
        return self.tlp_type.is_completion

    @property
    def size_dw(self) -> int:
        """Total packet size in doublewords (header + data)."""
        header_dw = 4 if self.tlp_type.has_4dw_header else 3
        data_dw = self.header.length if self.has_data else 0
        return header_dw + data_dw

    def summary(self) -> str:
        """One-line summary of this TLP."""
        parts = [f"{self.tlp_type.short_name}"]
        parts.append(f"Req={self.header.requester_id}")
        parts.append(f"Tag={self.header.tag}")

        if self.is_completion:
            parts.append(f"Cpl={self.header.completer_id}")
            parts.append(f"Status={self.header.status.name}")
        else:
            parts.append(f"Addr=0x{self.header.address:08X}")

        if self.has_data:
            parts.append(f"Len={self.header.length}DW")

        return " | ".join(parts)
