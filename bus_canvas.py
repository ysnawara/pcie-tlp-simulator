"""
PCIe Bus Canvas — draws the bus diagram and animates packets.
Renders CPU and GPU device boxes connected by a PCIe link,
and animates colored packet rectangles between them.
"""

import tkinter as tk

# --- Color palette (Catppuccin Dark) ---
COLORS = {
    "bg": "#1E1E2E",
    "cpu_fill": "#1E3A5F",
    "cpu_border": "#89B4FA",
    "gpu_fill": "#1E3F2E",
    "gpu_border": "#A6E3A1",
    "bus_line": "#6C7086",
    "bus_glow": "#45475A",
    "text": "#CDD6F4",
    "dim_text": "#6C7086",
    "read": "#89B4FA",
    "write": "#A6E3A1",
    "completion": "#F9E2AF",
    "error": "#F38BA8",
    "pass": "#A6E3A1",
    "fail": "#F38BA8",
}

# Packet type to color mapping
PACKET_COLORS = {
    "read": COLORS["read"],
    "write": COLORS["write"],
    "completion": COLORS["completion"],
    "error": COLORS["error"],
}

# Animation settings
ANIMATION_STEPS = 30        # number of frames per animation
ANIMATION_DELAY_MS = 16     # ~60fps


class BusCanvas:
    """
    Draws and manages the PCIe bus diagram on a tkinter Canvas.
    Handles device boxes, bus lines, and packet animations.
    """

    def __init__(self, canvas: tk.Canvas):
        self.canvas = canvas
        self.animation_queue = []       # pending animations
        self.is_animating = False
        self.packet_items = []          # canvas item IDs for cleanup

        # Device box positions (calculated on resize)
        self.cpu_x = 0
        self.cpu_y = 0
        self.gpu_x = 0
        self.gpu_y = 0
        self.box_w = 120
        self.box_h = 80
        self.bus_y_top = 0
        self.bus_y_bot = 0

        # Callbacks
        self.on_animation_complete = None

        # Bind resize
        self.canvas.bind("<Configure>", self._on_resize)

    def _on_resize(self, event=None):
        """Recalculate positions and redraw on window resize."""
        self._draw_static()

    def _draw_static(self):
        """Draw the static bus diagram (devices + bus lines)."""
        self.canvas.delete("static")
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()

        if w < 50 or h < 50:
            return

        # Calculate positions
        margin_x = 60
        self.cpu_x = margin_x
        self.gpu_x = w - margin_x - self.box_w
        center_y = h // 2
        self.cpu_y = center_y - self.box_h // 2
        self.gpu_y = center_y - self.box_h // 2

        # Bus lines (two lanes: request + completion)
        bus_left = self.cpu_x + self.box_w + 15
        bus_right = self.gpu_x - 15
        self.bus_y_top = center_y - 12
        self.bus_y_bot = center_y + 12

        # Bus background glow
        self.canvas.create_rectangle(
            bus_left - 5, self.bus_y_top - 8,
            bus_right + 5, self.bus_y_bot + 8,
            fill=COLORS["bus_glow"], outline="", tags="static",
        )

        # Top lane (requests: CPU → GPU)
        self.canvas.create_line(
            bus_left, self.bus_y_top, bus_right, self.bus_y_top,
            fill=COLORS["bus_line"], width=2, tags="static",
        )
        # Arrow head →
        self.canvas.create_polygon(
            bus_right, self.bus_y_top,
            bus_right - 8, self.bus_y_top - 5,
            bus_right - 8, self.bus_y_top + 5,
            fill=COLORS["bus_line"], outline="", tags="static",
        )
        # Lane label
        self.canvas.create_text(
            (bus_left + bus_right) // 2, self.bus_y_top - 12,
            text="Request", fill=COLORS["dim_text"],
            font=("Consolas", 8), tags="static",
        )

        # Bottom lane (completions: GPU → CPU)
        self.canvas.create_line(
            bus_left, self.bus_y_bot, bus_right, self.bus_y_bot,
            fill=COLORS["bus_line"], width=2, tags="static",
        )
        # Arrow head ←
        self.canvas.create_polygon(
            bus_left, self.bus_y_bot,
            bus_left + 8, self.bus_y_bot - 5,
            bus_left + 8, self.bus_y_bot + 5,
            fill=COLORS["bus_line"], outline="", tags="static",
        )
        self.canvas.create_text(
            (bus_left + bus_right) // 2, self.bus_y_bot + 14,
            text="Completion", fill=COLORS["dim_text"],
            font=("Consolas", 8), tags="static",
        )

        # CPU box
        self.canvas.create_rectangle(
            self.cpu_x, self.cpu_y,
            self.cpu_x + self.box_w, self.cpu_y + self.box_h,
            fill=COLORS["cpu_fill"], outline=COLORS["cpu_border"],
            width=2, tags="static",
        )
        self.canvas.create_text(
            self.cpu_x + self.box_w // 2, self.cpu_y + self.box_h // 2 - 10,
            text="CPU", fill=COLORS["cpu_border"],
            font=("Consolas", 14, "bold"), tags="static",
        )
        self.canvas.create_text(
            self.cpu_x + self.box_w // 2, self.cpu_y + self.box_h // 2 + 10,
            text="Root Complex", fill=COLORS["dim_text"],
            font=("Consolas", 9), tags="static",
        )

        # GPU box
        self.canvas.create_rectangle(
            self.gpu_x, self.gpu_y,
            self.gpu_x + self.box_w, self.gpu_y + self.box_h,
            fill=COLORS["gpu_fill"], outline=COLORS["gpu_border"],
            width=2, tags="static",
        )
        self.canvas.create_text(
            self.gpu_x + self.box_w // 2, self.gpu_y + self.box_h // 2 - 10,
            text="GPU", fill=COLORS["gpu_border"],
            font=("Consolas", 14, "bold"), tags="static",
        )
        self.canvas.create_text(
            self.gpu_x + self.box_w // 2, self.gpu_y + self.box_h // 2 + 10,
            text="Endpoint", fill=COLORS["dim_text"],
            font=("Consolas", 9), tags="static",
        )

    def animate_packet(self, direction: str, packet_type: str,
                       label: str, callback=None):
        """
        Queue a packet animation.

        Args:
            direction: "right" (CPU→GPU) or "left" (GPU→CPU)
            packet_type: "read", "write", "completion", or "error"
            label: short text shown on the packet (e.g. "MRd32")
            callback: function called when animation finishes
        """
        self.animation_queue.append((direction, packet_type, label, callback))
        if not self.is_animating:
            self._run_next_animation()

    def _run_next_animation(self):
        """Start the next animation in the queue."""
        if not self.animation_queue:
            self.is_animating = False
            return

        self.is_animating = True
        direction, packet_type, label, callback = self.animation_queue.pop(0)
        color = PACKET_COLORS.get(packet_type, COLORS["read"])

        # Calculate start and end x positions
        bus_left = self.cpu_x + self.box_w + 15
        bus_right = self.gpu_x - 15

        if direction == "right":
            start_x = bus_left
            end_x = bus_right - 60
            y = self.bus_y_top
        else:
            start_x = bus_right - 60
            end_x = bus_left
            y = self.bus_y_bot

        # Create packet rectangle
        pw, ph = 60, 18
        rect = self.canvas.create_rectangle(
            start_x, y - ph // 2, start_x + pw, y + ph // 2,
            fill=color, outline="", tags="packet",
        )
        text = self.canvas.create_text(
            start_x + pw // 2, y,
            text=label, fill="#1E1E2E",
            font=("Consolas", 8, "bold"), tags="packet",
        )
        self.packet_items.extend([rect, text])

        # Animate
        dx = (end_x - start_x) / ANIMATION_STEPS
        self._animate_step(rect, text, dx, 0, ANIMATION_STEPS,
                           direction, packet_type, callback)

    def _animate_step(self, rect, text, dx, step, total_steps,
                      direction, packet_type, callback):
        """Execute one frame of the packet animation."""
        if step >= total_steps:
            # Animation complete — flash destination
            self._flash_destination(direction, packet_type)

            # Fade out packet after brief delay
            self.canvas.after(200, lambda: self._fade_packet(rect, text))

            # Call callback and start next animation
            self.canvas.after(300, lambda: self._finish_animation(callback))
            return

        self.canvas.move(rect, dx, 0)
        self.canvas.move(text, dx, 0)
        self.canvas.after(ANIMATION_DELAY_MS,
                         lambda: self._animate_step(rect, text, dx,
                                                     step + 1, total_steps,
                                                     direction, packet_type,
                                                     callback))

    def _flash_destination(self, direction, packet_type):
        """Briefly flash the destination device box."""
        if packet_type == "error":
            flash_color = COLORS["error"]
        else:
            flash_color = COLORS["pass"]

        if direction == "right":
            # Flash GPU box
            box_x, box_y = self.gpu_x, self.gpu_y
        else:
            # Flash CPU box
            box_x, box_y = self.cpu_x, self.cpu_y

        flash = self.canvas.create_rectangle(
            box_x, box_y,
            box_x + self.box_w, box_y + self.box_h,
            fill="", outline=flash_color, width=4, tags="flash",
        )
        self.canvas.after(300, lambda: self.canvas.delete(flash))

    def _fade_packet(self, rect, text):
        """Remove packet items from canvas."""
        try:
            self.canvas.delete(rect)
            self.canvas.delete(text)
        except tk.TclError:
            pass

    def _finish_animation(self, callback):
        """Complete current animation and proceed to next."""
        if callback:
            callback()
        self._run_next_animation()

    def clear_packets(self):
        """Remove all packet items from the canvas."""
        self.canvas.delete("packet")
        self.canvas.delete("flash")
        self.animation_queue.clear()
        self.is_animating = False
        self.packet_items.clear()
