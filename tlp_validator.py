"""
TLP Validator — checks PCIe TLP packets for protocol compliance.
Each rule is a standalone function that returns (pass, reason).
This makes the code easy to understand and extend.
"""

from tlp import TLP, TLPType, CompletionStatus


# Maximum payload size in doublewords (512 bytes = 128 DW is a common default)
MAX_PAYLOAD_DW = 128
MAX_READ_REQUEST_DW = 128


def validate_tlp(tlp: TLP) -> list[tuple[bool, str]]:
    """
    Run all validation rules on a TLP.

    Returns a list of (passed, message) tuples, one per rule.
    A passed=False entry means a protocol violation was detected.
    """
    results = []
    results.append(check_format_type(tlp))
    results.append(check_length_field(tlp))
    results.append(check_data_payload(tlp))
    results.append(check_address_alignment(tlp))
    results.append(check_max_payload(tlp))
    results.append(check_requester_id(tlp))

    if tlp.is_completion:
        results.append(check_completion_status(tlp))
        results.append(check_completion_fields(tlp))

    results.append(check_traffic_class(tlp))
    return results


def check_format_type(tlp: TLP) -> tuple[bool, str]:
    """Verify the format/type combination is a valid PCIe TLP type."""
    try:
        _ = tlp.header.tlp_type.fmt
        _ = tlp.header.tlp_type.type_code
        return (True, "Format/Type combination is valid")
    except AttributeError:
        return (False, "Invalid format/type combination")


def check_length_field(tlp: TLP) -> tuple[bool, str]:
    """
    Verify the length field is valid.
    Length 0 encodes 1024 DW. For all others, must be 1-1024.
    Read requests must have length >= 1.
    """
    length = tlp.header.length

    # Length field is 10 bits: 0 means 1024 DW
    if length < 0 or length > 1024:
        return (False, f"Length {length} out of valid range 0-1024")

    # Non-posted reads must request at least 1 DW
    if not tlp.tlp_type.has_data and not tlp.is_completion:
        if length < 1:
            return (False, f"Read request with length {length} (must be >= 1)")

    return (True, f"Length field {length} is valid")


def check_data_payload(tlp: TLP) -> tuple[bool, str]:
    """
    Verify data payload matches the TLP type.
    Types with data (writes, CplD) must have payload.
    Types without data (reads, Cpl) must not.
    """
    has_data = len(tlp.data) > 0
    expects_data = tlp.tlp_type.has_data

    if expects_data and not has_data:
        return (False,
                f"{tlp.tlp_type.short_name} expects data payload but none present")

    if not expects_data and has_data:
        return (False,
                f"{tlp.tlp_type.short_name} should not have data but "
                f"{len(tlp.data)} bytes found")

    if has_data:
        # Check payload length matches header length field
        actual_dw = (len(tlp.data) + 3) // 4
        if actual_dw != tlp.header.length:
            return (False,
                    f"Data payload ({actual_dw} DW) does not match "
                    f"length field ({tlp.header.length} DW)")

    return (True, "Data payload consistent with TLP type")


def check_address_alignment(tlp: TLP) -> tuple[bool, str]:
    """
    Verify memory address alignment.
    Memory Read/Write addresses should be naturally aligned:
    - 4-byte aligned for 1 DW transfers
    - Start address must be DW-aligned (lower 2 bits = 0)
    """
    if tlp.tlp_type in (TLPType.MRd32, TLPType.MRd64,
                         TLPType.MWr32, TLPType.MWr64):
        addr = tlp.header.address
        if addr & 0x3:
            return (False,
                    f"Memory address 0x{addr:08X} is not doubleword-aligned "
                    f"(lower 2 bits must be 0)")

    return (True, "Address alignment is correct")


def check_max_payload(tlp: TLP) -> tuple[bool, str]:
    """
    Verify payload does not exceed max payload size.
    Default max is 128 DW (512 bytes).
    """
    if tlp.tlp_type.has_data:
        if tlp.header.length > MAX_PAYLOAD_DW:
            return (False,
                    f"Payload length {tlp.header.length} DW exceeds "
                    f"max payload {MAX_PAYLOAD_DW} DW")

    if tlp.tlp_type in (TLPType.MRd32, TLPType.MRd64):
        if tlp.header.length > MAX_READ_REQUEST_DW:
            return (False,
                    f"Read request length {tlp.header.length} DW exceeds "
                    f"max read request {MAX_READ_REQUEST_DW} DW")

    return (True, "Payload size within limits")


def check_requester_id(tlp: TLP) -> tuple[bool, str]:
    """Verify requester ID fields are in valid ranges."""
    rid = tlp.header.requester_id
    if not (0 <= rid.bus <= 255):
        return (False, f"Requester bus {rid.bus} out of range 0-255")
    if not (0 <= rid.device <= 31):
        return (False, f"Requester device {rid.device} out of range 0-31")
    if not (0 <= rid.function <= 7):
        return (False, f"Requester function {rid.function} out of range 0-7")
    return (True, f"Requester ID {rid} is valid")


def check_completion_status(tlp: TLP) -> tuple[bool, str]:
    """Verify completion status is a valid PCIe status code."""
    if not isinstance(tlp.header.status, CompletionStatus):
        return (False, f"Invalid completion status: {tlp.header.status}")
    return (True, f"Completion status {tlp.header.status.name} is valid")


def check_completion_fields(tlp: TLP) -> tuple[bool, str]:
    """Verify completion-specific fields are properly set."""
    if tlp.header.completer_id is None:
        return (False, "Completion TLP missing completer ID")

    if tlp.tlp_type == TLPType.CplD and tlp.header.byte_count == 0:
        return (False, "CplD has byte_count=0 (should be > 0 for data)")

    return (True, "Completion fields are valid")


def check_traffic_class(tlp: TLP) -> tuple[bool, str]:
    """Verify traffic class is in valid range (0-7)."""
    if not (0 <= tlp.header.tc <= 7):
        return (False, f"Traffic class {tlp.header.tc} out of range 0-7")
    return (True, f"Traffic class {tlp.header.tc} is valid")
