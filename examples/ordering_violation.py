"""
Example: Deliberate PCIe ordering violation.
Shows a non-posted read passing a posted write, which violates
PCIe strong ordering rules.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tlp import TLP, TLPHeader, TLPType, DeviceID
from tlp_generator import (
    generate_memory_read, generate_memory_write,
    generate_completion,
)
from simulator import run_simulation
from reporter import print_report


def main():
    cpu = DeviceID(bus=0, device=0, function=0)
    gpu = DeviceID(bus=1, device=0, function=0)

    packets = [
        # Normal write at t=10
        generate_memory_write(cpu, address=0x1000, data=bytes(4), timestamp=10),

        # This read has timestamp BEFORE the write above (t=5 < t=10),
        # but appears later in the stream — this means it "passed" the write
        # which violates non-posted-cannot-pass-posted ordering rule
        generate_memory_read(cpu, address=0x2000, length=1, tag=1, timestamp=5),

        # Deliberate validation error: unaligned memory address
        TLP(
            header=TLPHeader(
                tlp_type=TLPType.MRd32,
                length=1,
                requester_id=cpu,
                tag=2,
                address=0x3003,  # NOT 4-byte aligned — violation!
            ),
            timestamp=20,
        ),

        # Completion for tag 1
        generate_completion(gpu, cpu, tag=1, data=bytes(4), timestamp=30),

        # Missing completion for tag 2 — will be flagged as unmatched
    ]

    result = run_simulation(packets)
    print_report(result)


if __name__ == "__main__":
    main()
