"""Tests for PCIe ordering rules engine."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tlp import TLP, TLPHeader, TLPType, DeviceID
from ordering import OrderingEngine
from tlp_generator import (
    generate_memory_read, generate_memory_write, generate_completion,
)


class TestOrderingRules:
    """Test PCIe transaction ordering rule enforcement."""

    def test_valid_ordering(self):
        """Normal traffic with proper ordering should have no violations."""
        dev = DeviceID(bus=0, device=1, function=0)
        cpl_dev = DeviceID(bus=1, device=0, function=0)

        packets = [
            generate_memory_write(dev, 0x1000, bytes(4), timestamp=10),
            generate_memory_write(dev, 0x2000, bytes(4), timestamp=20),
            generate_memory_read(dev, 0x3000, tag=1, timestamp=30),
            generate_completion(cpl_dev, dev, tag=1, data=bytes(4), timestamp=40),
        ]

        engine = OrderingEngine()
        for i, pkt in enumerate(packets):
            engine.process_packet(i, pkt)

        violations = engine.get_all_violations()
        assert len(violations) == 0

    def test_unmatched_request(self):
        """Non-posted request without completion should be flagged."""
        dev = DeviceID(bus=0, device=1, function=0)

        packets = [
            generate_memory_read(dev, 0x1000, tag=1, timestamp=10),
            generate_memory_read(dev, 0x2000, tag=2, timestamp=20),
            # No completions
        ]

        engine = OrderingEngine()
        for i, pkt in enumerate(packets):
            engine.process_packet(i, pkt)

        violations = engine.get_all_violations()
        # Should have 2 unmatched request violations
        unmatched = [v for v in violations if v.rule == "UNMATCHED_REQUEST"]
        assert len(unmatched) == 2

    def test_completions_clear_pending(self):
        """Completions should remove requests from pending tracking."""
        dev = DeviceID(bus=0, device=1, function=0)
        cpl_dev = DeviceID(bus=1, device=0, function=0)

        packets = [
            generate_memory_read(dev, 0x1000, tag=1, timestamp=10),
            generate_completion(cpl_dev, dev, tag=1, data=bytes(4), timestamp=20),
        ]

        engine = OrderingEngine()
        for i, pkt in enumerate(packets):
            engine.process_packet(i, pkt)

        violations = engine.get_all_violations()
        assert len(violations) == 0


# Run tests with: python -m pytest tests/test_ordering.py -v
