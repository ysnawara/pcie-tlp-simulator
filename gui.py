"""
PCIe TLP Simulator — GUI Application.
CustomTkinter-based desktop interface with animated bus diagram,
interactive controls, real-time validation, and packet log.
"""

import tkinter as tk
from tkinter import Canvas
import customtkinter as ctk

from tlp import TLP, TLPHeader, TLPType, DeviceID
from tlp_generator import (
    generate_memory_read, generate_memory_write,
    generate_completion, generate_random_traffic,
)
from tlp_validator import validate_tlp
from ordering import OrderingEngine
from bus_canvas import BusCanvas, COLORS

import random


class PCIeSimulatorApp(ctk.CTk):
    """Main GUI application for the PCIe TLP Simulator."""

    def __init__(self):
        super().__init__()

        self.title("PCIe Bus Simulator")
        self.geometry("1000x650")
        self.minsize(800, 550)
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # --- State ---
        self.cpu = DeviceID(bus=0, device=0, function=0)
        self.gpu = DeviceID(bus=1, device=0, function=0)
        self.tag_counter = 0
        self.time_counter = 0
        self.packet_log = []            # list of (TLP, results)
        self.ordering_engine = OrderingEngine()
        self.pending_reads = {}         # tag -> TLP

        # --- Build UI ---
        self._build_ui()

    def _build_ui(self):
        """Construct the full UI layout."""
        # --- Top: Bus diagram canvas ---
        canvas_frame = ctk.CTkFrame(self, corner_radius=0)
        canvas_frame.pack(fill="both", expand=True, padx=0, pady=0)

        # Bus canvas (left, takes most space)
        self.canvas = Canvas(canvas_frame, bg=COLORS["bg"],
                             highlightthickness=0)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.bus = BusCanvas(self.canvas)

        # Controls + Validation panel (right sidebar)
        sidebar = ctk.CTkFrame(canvas_frame, width=220, corner_radius=0)
        sidebar.pack(side="right", fill="y", padx=0, pady=0)
        sidebar.pack_propagate(False)

        # Controls section
        controls_label = ctk.CTkLabel(sidebar, text="Controls",
                                       font=("Consolas", 13, "bold"))
        controls_label.pack(pady=(12, 6))

        btn_read = ctk.CTkButton(sidebar, text="Send Read",
                                  fg_color="#1E3A5F",
                                  hover_color="#2A5080",
                                  border_color="#89B4FA",
                                  border_width=1,
                                  command=self._send_read)
        btn_read.pack(padx=12, pady=3, fill="x")

        btn_write = ctk.CTkButton(sidebar, text="Send Write",
                                   fg_color="#1E3F2E",
                                   hover_color="#2A5540",
                                   border_color="#A6E3A1",
                                   border_width=1,
                                   command=self._send_write)
        btn_write.pack(padx=12, pady=3, fill="x")

        btn_test = ctk.CTkButton(sidebar, text="Run Full Test",
                                  fg_color="#2A2040",
                                  hover_color="#3A3060",
                                  border_color="#CBA6F7",
                                  border_width=1,
                                  command=self._run_full_test)
        btn_test.pack(padx=12, pady=3, fill="x")

        btn_error = ctk.CTkButton(sidebar, text="Inject Error",
                                   fg_color="#3D1F2F",
                                   hover_color="#5D2F3F",
                                   border_color="#F38BA8",
                                   border_width=1,
                                   command=self._inject_error)
        btn_error.pack(padx=12, pady=3, fill="x")

        btn_clear = ctk.CTkButton(sidebar, text="Clear",
                                   fg_color="#313244",
                                   hover_color="#45475A",
                                   command=self._clear)
        btn_clear.pack(padx=12, pady=(3, 10), fill="x")

        # Divider
        divider = ctk.CTkFrame(sidebar, height=2, fg_color="#45475A")
        divider.pack(fill="x", padx=12, pady=4)

        # Validation results section
        val_label = ctk.CTkLabel(sidebar, text="Last Validation",
                                  font=("Consolas", 13, "bold"))
        val_label.pack(pady=(6, 4))

        self.validation_frame = ctk.CTkFrame(sidebar, fg_color="#181825")
        self.validation_frame.pack(padx=12, pady=2, fill="both", expand=True)

        self.val_labels = {}
        rules = ["Format/Type", "Length", "Payload", "Alignment",
                 "Max Size", "Requester ID", "Traffic Class"]
        for rule in rules:
            row = ctk.CTkFrame(self.validation_frame, fg_color="transparent")
            row.pack(fill="x", padx=6, pady=1)

            icon = ctk.CTkLabel(row, text="-", width=20,
                                font=("Consolas", 11))
            icon.pack(side="left")

            name = ctk.CTkLabel(row, text=rule,
                                font=("Consolas", 10),
                                text_color="#6C7086")
            name.pack(side="left", padx=4)

            self.val_labels[rule] = icon

        # --- Bottom: Packet log ---
        log_frame = ctk.CTkFrame(self, height=200, corner_radius=0)
        log_frame.pack(fill="x", padx=0, pady=0)
        log_frame.pack_propagate(False)

        log_header = ctk.CTkFrame(log_frame, height=28, fg_color="#181825")
        log_header.pack(fill="x")
        log_header.pack_propagate(False)

        headers = [("#", 30), ("Dir", 30), ("Type", 65), ("Address", 110),
                   ("Tag", 35), ("Len", 50), ("Status", 55)]
        for text, width in headers:
            lbl = ctk.CTkLabel(log_header, text=text, width=width,
                               font=("Consolas", 10, "bold"),
                               text_color="#6C7086")
            lbl.pack(side="left", padx=2)

        self.log_scroll = ctk.CTkScrollableFrame(log_frame,
                                                  fg_color=COLORS["bg"])
        self.log_scroll.pack(fill="both", expand=True)

        # Status bar
        self.status_bar = ctk.CTkFrame(self, height=28, corner_radius=0,
                                        fg_color="#181825")
        self.status_bar.pack(fill="x")

        self.status_label = ctk.CTkLabel(
            self.status_bar,
            text="Ready — click a button to send packets",
            font=("Consolas", 10), text_color="#6C7086",
        )
        self.status_label.pack(side="left", padx=10)

        self.status_stats = ctk.CTkLabel(
            self.status_bar, text="Total: 0  |  Pass: 0  |  Fail: 0",
            font=("Consolas", 10), text_color="#6C7086",
        )
        self.status_stats.pack(side="right", padx=10)

    # -----------------------------------------------------------------
    # Actions
    # -----------------------------------------------------------------

    def _send_read(self):
        """Send a Memory Read TLP (CPU → GPU), then its completion (GPU → CPU)."""
        self.tag_counter = (self.tag_counter + 1) % 256
        self.time_counter += random.randint(5, 15)
        addr = random.randint(0, 0xFFFFF) * 4  # aligned

        tlp = generate_memory_read(
            self.cpu, address=addr, length=1,
            tag=self.tag_counter, timestamp=self.time_counter,
        )

        # Process and animate request
        self._process_and_animate(tlp, "right", "read", "MRd32",
                                  animate_completion=True)

    def _send_write(self):
        """Send a Memory Write TLP (CPU → GPU). Posted — no completion."""
        self.time_counter += random.randint(5, 15)
        addr = random.randint(0, 0xFFFFF) * 4

        data = bytes(random.randint(0, 255) for _ in range(4))
        tlp = generate_memory_write(
            self.cpu, address=addr, data=data,
            timestamp=self.time_counter,
        )

        self._process_and_animate(tlp, "right", "write", "MWr32")

    def _inject_error(self):
        """Send a TLP with an unaligned address — triggers validation failure."""
        self.tag_counter = (self.tag_counter + 1) % 256
        self.time_counter += random.randint(5, 15)

        # Create a TLP with unaligned address (violates DW alignment)
        tlp = TLP(
            header=TLPHeader(
                tlp_type=TLPType.MRd32,
                length=1,
                requester_id=self.cpu,
                tag=self.tag_counter,
                address=0x3003,  # NOT 4-byte aligned
            ),
            timestamp=self.time_counter,
        )

        self._process_and_animate(tlp, "right", "error", "ERROR")

    def _run_full_test(self):
        """Generate and animate a sequence of random packets."""
        packets = generate_random_traffic(num_packets=8, seed=random.randint(1, 999))

        delay = 0
        for tlp in packets:
            direction = "left" if tlp.is_completion else "right"

            if tlp.is_completion:
                ptype = "completion"
                label = "CplD"
            elif tlp.is_posted:
                ptype = "write"
                label = "MWr32"
            else:
                ptype = "read"
                label = tlp.tlp_type.short_name

            # Stagger animations
            self.after(delay, lambda t=tlp, d=direction, p=ptype, l=label:
                       self._process_and_animate(t, d, p, l))
            delay += 700

    def _clear(self):
        """Reset everything."""
        self.bus.clear_packets()
        self.packet_log.clear()
        self.ordering_engine = OrderingEngine()
        self.pending_reads.clear()
        self.tag_counter = 0
        self.time_counter = 0

        # Clear log display
        for widget in self.log_scroll.winfo_children():
            widget.destroy()

        # Reset validation icons
        for icon in self.val_labels.values():
            icon.configure(text="-", text_color="#6C7086")

        self._update_status_bar()
        self.status_label.configure(text="Cleared")

    # -----------------------------------------------------------------
    # Core processing
    # -----------------------------------------------------------------

    def _process_and_animate(self, tlp, direction, packet_type, label,
                             animate_completion=False):
        """Validate a TLP, animate it, and log the result."""
        # Run validation
        results = validate_tlp(tlp)
        issues = [msg for passed, msg in results if not passed]
        is_valid = len(issues) == 0

        # Track ordering
        idx = len(self.packet_log)
        self.ordering_engine.process_packet(idx, tlp)

        # Log it
        self.packet_log.append((tlp, is_valid, issues))

        # Update validation panel
        self._update_validation(results)

        # Add to packet log display
        self._add_log_row(tlp, direction, is_valid)

        # Update status
        self._update_status_bar()

        # Animate
        def on_complete():
            if animate_completion and is_valid:
                # Send completion back
                self.time_counter += random.randint(10, 20)
                cpl = generate_completion(
                    self.gpu, self.cpu, tag=tlp.header.tag,
                    data=bytes(4), timestamp=self.time_counter,
                )
                self._process_and_animate(cpl, "left", "completion", "CplD")

        self.bus.animate_packet(direction, packet_type, label, on_complete)

    def _update_validation(self, results):
        """Update the validation panel with results from the latest packet."""
        rule_names = ["Format/Type", "Length", "Payload", "Alignment",
                      "Max Size", "Requester ID", "Traffic Class"]

        for i, (passed, _) in enumerate(results):
            if i < len(rule_names):
                icon = self.val_labels[rule_names[i]]
                if passed:
                    icon.configure(text="OK", text_color=COLORS["pass"])
                else:
                    icon.configure(text="X", text_color=COLORS["fail"])

    def _add_log_row(self, tlp, direction, is_valid):
        """Add a row to the packet log display."""
        row = ctk.CTkFrame(self.log_scroll, fg_color="transparent", height=22)
        row.pack(fill="x", padx=2, pady=0)

        idx = len(self.packet_log) - 1
        dir_arrow = "->" if direction == "right" else "<-"
        type_name = tlp.tlp_type.short_name
        tag = str(tlp.header.tag) if tlp.header.tag else "-"
        length = f"{tlp.header.length}DW" if tlp.header.length else "-"

        if tlp.is_completion:
            addr = f"cpl tag={tlp.header.tag}"
        else:
            addr = f"0x{tlp.header.address:08X}"

        status = "PASS" if is_valid else "FAIL"
        status_color = COLORS["pass"] if is_valid else COLORS["fail"]

        # Determine type color
        if tlp.is_posted:
            type_color = COLORS["write"]
        elif tlp.is_completion:
            type_color = COLORS["completion"]
        else:
            type_color = COLORS["read"]

        if not is_valid:
            type_color = COLORS["fail"]

        values = [
            (str(idx), 30, "#6C7086"),
            (dir_arrow, 30, "#CDD6F4"),
            (type_name, 65, type_color),
            (addr, 110, "#CDD6F4"),
            (tag, 35, "#6C7086"),
            (length, 50, "#6C7086"),
            (status, 55, status_color),
        ]

        for text, width, color in values:
            lbl = ctk.CTkLabel(row, text=text, width=width,
                               font=("Consolas", 10),
                               text_color=color)
            lbl.pack(side="left", padx=2)

    def _update_status_bar(self):
        """Update the bottom status bar with packet counts."""
        total = len(self.packet_log)
        passed = sum(1 for _, v, _ in self.packet_log if v)
        failed = total - passed
        ordering_viols = len(self.ordering_engine.violations)

        self.status_stats.configure(
            text=f"Total: {total}  |  Pass: {passed}  |  "
                 f"Fail: {failed}  |  Ordering: "
                 f"{'OK' if ordering_viols == 0 else f'{ordering_viols} violations'}"
        )
