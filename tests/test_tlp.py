"""Tests for TLP data structures and validation."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tlp import TLP, TLPHeader, TLPType, DeviceID, CompletionStatus
from tlp_validator import validate_tlp, check_address_alignment, check_data_payload
from tlp_generator import (
    generate_memory_read, generate_memory_write,
    generate_completion, generate_io_read,
)


class TestTLPCreation:
    """Test TLP data structure creation."""

    def test_memory_read_32bit(self):
        dev = DeviceID(bus=0, device=1, function=0)
        tlp = generate_memory_read(dev, address=0x1000, length=4, tag=1)
        assert tlp.tlp_type == TLPType.MRd32
        assert tlp.header.address == 0x1000
        assert tlp.header.length == 4
        assert tlp.header.tag == 1
        assert not tlp.has_data

    def test_memory_read_64bit(self):
        dev = DeviceID(bus=0, device=1, function=0)
        tlp = generate_memory_read(dev, address=0x1_0000_0000, length=1, tag=5)
        assert tlp.tlp_type == TLPType.MRd64
        assert tlp.tlp_type.has_4dw_header

    def test_memory_write(self):
        dev = DeviceID(bus=0, device=1, function=0)
        data = bytes([0xDE, 0xAD, 0xBE, 0xEF])
        tlp = generate_memory_write(dev, address=0x2000, data=data)
        assert tlp.tlp_type == TLPType.MWr32
        assert tlp.has_data
        assert tlp.is_posted
        assert tlp.header.length == 1

    def test_completion_with_data(self):
        req = DeviceID(bus=0, device=1, function=0)
        cpl = DeviceID(bus=1, device=0, function=0)
        data = bytes([0x01, 0x02, 0x03, 0x04])
        tlp = generate_completion(cpl, req, tag=1, data=data)
        assert tlp.tlp_type == TLPType.CplD
        assert tlp.is_completion
        assert tlp.header.completer_id == cpl

    def test_completion_no_data(self):
        req = DeviceID(bus=0, device=1, function=0)
        cpl = DeviceID(bus=1, device=0, function=0)
        tlp = generate_completion(cpl, req, tag=1)
        assert tlp.tlp_type == TLPType.Cpl

    def test_device_id_validation(self):
        dev = DeviceID(bus=255, device=31, function=7)
        assert dev.bus == 255
        assert dev.device == 31
        assert dev.function == 7

    def test_tlp_type_properties(self):
        assert TLPType.MWr32.is_posted
        assert not TLPType.MRd32.is_posted
        assert TLPType.CplD.is_completion
        assert TLPType.MRd64.has_4dw_header
        assert not TLPType.MRd32.has_4dw_header


class TestTLPValidation:
    """Test TLP validation rules."""

    def test_valid_memory_read(self):
        dev = DeviceID(bus=0, device=1, function=0)
        tlp = generate_memory_read(dev, address=0x1000, length=4, tag=1)
        results = validate_tlp(tlp)
        assert all(passed for passed, _ in results)

    def test_valid_memory_write(self):
        dev = DeviceID(bus=0, device=1, function=0)
        data = bytes(16)
        tlp = generate_memory_write(dev, address=0x2000, data=data)
        results = validate_tlp(tlp)
        assert all(passed for passed, _ in results)

    def test_unaligned_address(self):
        dev = DeviceID(bus=0, device=1, function=0)
        header = TLPHeader(
            tlp_type=TLPType.MRd32,
            length=1,
            requester_id=dev,
            tag=1,
            address=0x1003,  # not 4-byte aligned
        )
        tlp = TLP(header=header)
        passed, msg = check_address_alignment(tlp)
        assert not passed
        assert "not doubleword-aligned" in msg

    def test_data_mismatch(self):
        dev = DeviceID(bus=0, device=1, function=0)
        header = TLPHeader(
            tlp_type=TLPType.MWr32,
            length=2,  # claims 2 DW
            requester_id=dev,
            address=0x1000,
        )
        tlp = TLP(header=header, data=bytes(4))  # only 1 DW of data
        passed, msg = check_data_payload(tlp)
        assert not passed
        assert "does not match" in msg

    def test_valid_completion(self):
        req = DeviceID(bus=0, device=1, function=0)
        cpl = DeviceID(bus=1, device=0, function=0)
        data = bytes(4)
        tlp = generate_completion(cpl, req, tag=1, data=data)
        results = validate_tlp(tlp)
        assert all(passed for passed, _ in results)


# Run tests with: python -m pytest tests/test_tlp.py -v
