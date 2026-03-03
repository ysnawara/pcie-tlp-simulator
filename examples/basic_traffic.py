"""
Example: Basic PCIe read/write traffic.
Demonstrates a simple sequence of memory reads, writes, and completions.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tlp import DeviceID
from tlp_generator import (
    generate_memory_read, generate_memory_write, generate_completion,
)
from simulator import run_simulation
from reporter import print_report


def main():
    # Define two devices on the PCIe bus
    cpu = DeviceID(bus=0, device=0, function=0)      # Root Complex (CPU)
    gpu = DeviceID(bus=1, device=0, function=0)      # PCIe endpoint (GPU)

    # Build a simple traffic sequence
    packets = [
        # CPU writes configuration data to GPU
        generate_memory_write(cpu, address=0x1000, data=bytes(4), timestamp=10),
        generate_memory_write(cpu, address=0x1004, data=bytes(8), timestamp=20),

        # CPU reads status register from GPU
        generate_memory_read(cpu, address=0x2000, length=1, tag=1, timestamp=30),

        # GPU responds with completion data
        generate_completion(gpu, cpu, tag=1, data=bytes(4), timestamp=45),

        # CPU starts DMA write
        generate_memory_write(cpu, address=0x3000, data=bytes(16), timestamp=50),

        # CPU reads another register
        generate_memory_read(cpu, address=0x2004, length=2, tag=2, timestamp=60),

        # GPU responds
        generate_completion(gpu, cpu, tag=2, data=bytes(8), timestamp=75),
    ]

    # Run simulation and print report
    result = run_simulation(packets)
    print_report(result)


if __name__ == "__main__":
    main()
