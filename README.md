# PCIe TLP Simulator

An interactive PCIe Transaction Layer Packet (TLP) simulator with animated bus visualization. Generates, validates, and analyzes PCIe traffic with protocol compliance checking, request-completion matching, and ordering rule verification.

Built with Python and CustomTkinter.

## Features

- **Interactive GUI** — visual bus diagram with CPU (Root Complex) and GPU (Endpoint) connected by a PCIe link
- **Animated Packet Flow** — colored packets slide between devices (blue = read, green = write, yellow = completion, red = error)
- **One-Click Controls** — Send Read, Send Write, Inject Error, Run Full Test, Clear
- **Real-Time Validation** — 7 protocol rules checked per packet with live OK/X indicators
- **Packet Log** — scrollable table with direction, type, address, tag, and pass/fail status
- **TLP Generation** — creates Memory Read/Write, IO Read, Config Read, and Completion packets with proper format/type encoding
- **Protocol Validation** — checks each TLP against PCIe spec rules:
  - Format/type field combinations
  - Data payload presence and length consistency
  - Address alignment (doubleword-aligned)
  - Max payload size limits
  - Requester/Completer ID validity
  - Completion status and field checks
  - Traffic class range
- **Ordering Rule Engine** — enforces PCIe transaction ordering:
  - Posted writes cannot pass earlier posted writes
  - Non-posted reads cannot pass posted writes (strong ordering)
  - Completion ordering for same-tag transactions
  - Unmatched request detection
- **CLI Mode** — Rich-formatted terminal reports as an alternative to the GUI
- **Test Suite** — 15 pytest tests for TLP creation, validation, and ordering

## Architecture

```
gui.py               # CustomTkinter GUI (controls, validation panel, packet log)
bus_canvas.py         # Bus diagram drawing + packet animation engine
tlp.py               # TLP data structures (TLPType, DeviceID, TLPHeader, TLP)
tlp_generator.py     # Factory functions for creating TLPs
tlp_validator.py     # Per-packet protocol compliance rules
ordering.py          # Transaction ordering rule engine
simulator.py         # Orchestrates validation + ordering checks
reporter.py          # Rich-formatted terminal reports (CLI mode)
main.py              # Entry point (GUI default, --cli for terminal)
tests/               # pytest test suite
examples/            # Example traffic scenarios
```

### PCIe TLP Overview

A Transaction Layer Packet (TLP) is the fundamental communication unit in PCIe:

| Field | Description |
|-------|-------------|
| Format | 3DW or 4DW header, with or without data |
| Type | Memory, IO, Config, Completion, or Message |
| Requester ID | Bus:Device.Function of the sender |
| Tag | Transaction identifier (for request-completion matching) |
| Address | Target memory/IO/config address |
| Length | Payload size in doublewords (4-byte units) |

**Transaction types:**
- **Posted** (MWr): fire-and-forget, no completion expected
- **Non-posted** (MRd, IORd, CfgRd): expects a completion response
- **Completion** (Cpl, CplD): response to a non-posted request

## Usage

```bash
# Install dependencies
pip install -r requirements.txt

# Launch GUI (default)
python main.py

# CLI mode
python main.py --cli
python main.py --cli -n 50 --seed 123

# Run examples
python examples/basic_traffic.py
python examples/ordering_violation.py

# Run tests
python -m pytest tests/ -v
```

### GUI Controls

| Button | Action |
|--------|--------|
| Send Read | Memory Read (CPU → GPU), completion animates back |
| Send Write | Memory Write (CPU → GPU), no completion (posted) |
| Run Full Test | 8 random packets animated in sequence |
| Inject Error | Sends unaligned address — triggers validation failure |
| Clear | Reset all state |

## Requirements

- Python 3.10+
- customtkinter >= 5.2.0
- rich >= 13.0.0
- pytest >= 7.0.0
