"""
PCIe TLP Simulator — Entry point.

Usage:
    python main.py               # launch GUI
    python main.py --cli         # run CLI simulation
    python main.py --cli -n 30   # CLI with 30 packets
"""

import sys
import argparse


def main():
    parser = argparse.ArgumentParser(
        description="PCIe TLP Simulator — generates, validates, and "
                    "visualizes PCIe Transaction Layer Packets",
    )
    parser.add_argument(
        "--cli", action="store_true",
        help="Run in CLI mode instead of GUI",
    )
    parser.add_argument(
        "-n", "--packets", type=int, default=20,
        help="Number of packets for CLI mode (default: 20)",
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="Random seed for CLI mode (default: 42)",
    )
    args = parser.parse_args()

    if args.cli:
        # CLI mode — generate traffic, validate, print report
        from tlp_generator import generate_random_traffic
        from simulator import run_simulation
        from reporter import print_report

        packets = generate_random_traffic(args.packets, args.seed)
        result = run_simulation(packets)
        print_report(result)
    else:
        # GUI mode — launch interactive simulator
        from gui import PCIeSimulatorApp
        app = PCIeSimulatorApp()
        app.mainloop()


if __name__ == "__main__":
    main()
