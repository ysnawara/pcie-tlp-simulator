"""
PCIe TLP Simulator — orchestrates traffic generation, validation,
and ordering rule checking.
"""

from dataclasses import dataclass, field
from tlp import TLP
from tlp_validator import validate_tlp
from ordering import OrderingEngine, OrderingViolation


@dataclass
class ValidationResult:
    """Result of validating a single TLP."""
    index: int
    tlp: TLP
    passed: bool
    issues: list[str] = field(default_factory=list)


@dataclass
class SimulationResult:
    """Complete results from a simulation run."""
    total_packets: int = 0
    validation_results: list[ValidationResult] = field(default_factory=list)
    ordering_violations: list[OrderingViolation] = field(default_factory=list)
    packets: list[TLP] = field(default_factory=list)

    @property
    def validation_pass_count(self) -> int:
        return sum(1 for r in self.validation_results if r.passed)

    @property
    def validation_fail_count(self) -> int:
        return sum(1 for r in self.validation_results if not r.passed)

    @property
    def all_passed(self) -> bool:
        return (self.validation_fail_count == 0 and
                len(self.ordering_violations) == 0)


def run_simulation(packets: list[TLP]) -> SimulationResult:
    """
    Run a full simulation: validate each packet and check ordering.

    This is the main entry point for the simulator. It takes a list of
    TLPs (from the generator or from a test scenario), validates each
    one against protocol rules, and then checks global ordering rules.

    Args:
        packets: list of TLPs to simulate

    Returns:
        SimulationResult with all validation and ordering results
    """
    result = SimulationResult(
        total_packets=len(packets),
        packets=packets,
    )

    # --- Phase 1: Validate each packet individually ---
    for i, tlp in enumerate(packets):
        rule_results = validate_tlp(tlp)

        issues = [msg for passed, msg in rule_results if not passed]
        vr = ValidationResult(
            index=i,
            tlp=tlp,
            passed=len(issues) == 0,
            issues=issues,
        )
        result.validation_results.append(vr)

    # --- Phase 2: Check ordering rules across the packet stream ---
    ordering_engine = OrderingEngine()
    for i, tlp in enumerate(packets):
        ordering_engine.process_packet(i, tlp)

    result.ordering_violations = ordering_engine.get_all_violations()

    return result
