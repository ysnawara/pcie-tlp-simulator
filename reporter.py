"""
Rich-formatted report generator for PCIe TLP simulation results.
Produces color-coded tables and summaries in the terminal.
"""

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from simulator import SimulationResult


console = Console()


def print_report(result: SimulationResult):
    """Print a complete simulation report with packet table and violations."""
    console.print()
    console.rule("[bold cyan]PCIe TLP Simulation Report[/bold cyan]")
    console.print()

    # --- Packet Summary Table ---
    _print_packet_table(result)

    # --- Validation Results ---
    _print_validation_summary(result)

    # --- Ordering Violations ---
    _print_ordering_violations(result)

    # --- Overall Result ---
    _print_overall(result)


def _print_packet_table(result: SimulationResult):
    """Print a table of all simulated packets."""
    table = Table(title="TLP Traffic", show_lines=False, padding=(0, 1))
    table.add_column("#", style="dim", width=4)
    table.add_column("Time", style="cyan", width=6)
    table.add_column("Type", style="bold", width=8)
    table.add_column("Requester", width=10)
    table.add_column("Tag", width=4)
    table.add_column("Address / Completer", width=14)
    table.add_column("Length", width=6)
    table.add_column("Valid", width=5)

    for i, tlp in enumerate(result.packets):
        vr = result.validation_results[i]

        # Color-code the type
        type_name = tlp.tlp_type.short_name
        if tlp.is_posted:
            type_style = "green"
        elif tlp.is_completion:
            type_style = "yellow"
        else:
            type_style = "blue"

        # Address or completer
        if tlp.is_completion:
            addr = str(tlp.header.completer_id)
        else:
            addr = f"0x{tlp.header.address:08X}"

        # Length
        length = f"{tlp.header.length} DW" if tlp.header.length > 0 else "-"

        # Validation status
        valid = "PASS" if vr.passed else "FAIL"

        table.add_row(
            str(i),
            str(tlp.timestamp),
            Text(type_name, style=type_style),
            str(tlp.header.requester_id),
            str(tlp.header.tag),
            addr,
            length,
            valid,
        )

    console.print(table)
    console.print()


def _print_validation_summary(result: SimulationResult):
    """Print validation pass/fail summary with details of failures."""
    passed = result.validation_pass_count
    failed = result.validation_fail_count
    total = result.total_packets

    if failed == 0:
        console.print(Panel(
            f"[green]All {total} packets passed protocol validation PASS[/green]",
            title="Validation",
            border_style="green",
        ))
    else:
        console.print(Panel(
            f"[red]{failed}/{total} packets failed validation FAIL[/red]",
            title="Validation",
            border_style="red",
        ))

        # Show details
        table = Table(title="Validation Failures", show_lines=True)
        table.add_column("Packet #", style="dim")
        table.add_column("Type")
        table.add_column("Issue", style="red")

        for vr in result.validation_results:
            if not vr.passed:
                for issue in vr.issues:
                    table.add_row(
                        str(vr.index),
                        vr.tlp.tlp_type.short_name,
                        issue,
                    )

        console.print(table)

    console.print()


def _print_ordering_violations(result: SimulationResult):
    """Print ordering rule violations."""
    violations = result.ordering_violations

    if not violations:
        console.print(Panel(
            "[green]No ordering violations detected PASS[/green]",
            title="Ordering Rules",
            border_style="green",
        ))
    else:
        console.print(Panel(
            f"[red]{len(violations)} ordering violation(s) detected FAIL[/red]",
            title="Ordering Rules",
            border_style="red",
        ))

        table = Table(title="Ordering Violations", show_lines=True)
        table.add_column("Rule", style="bold red")
        table.add_column("Packet #", style="dim")
        table.add_column("Description")

        for v in violations:
            table.add_row(v.rule, str(v.packet_index), v.description)

        console.print(table)

    console.print()


def _print_overall(result: SimulationResult):
    """Print overall pass/fail result."""
    if result.all_passed:
        console.print(Panel(
            "[bold green]SIMULATION PASSED — "
            "all packets valid, no ordering violations[/bold green]",
            border_style="green",
        ))
    else:
        issues = []
        if result.validation_fail_count > 0:
            issues.append(f"{result.validation_fail_count} validation failures")
        if result.ordering_violations:
            issues.append(f"{len(result.ordering_violations)} ordering violations")
        issue_str = ", ".join(issues)

        console.print(Panel(
            f"[bold red]SIMULATION FAILED — {issue_str}[/bold red]",
            border_style="red",
        ))

    console.print()
