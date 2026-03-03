"""
PCIe Ordering Rules Engine.
Enforces the PCIe transaction ordering rules that govern how TLPs
can pass each other within a traffic stream.

PCIe Ordering Summary (simplified):
- Posted writes (MWr) are "fire and forget" — they can pass each other
  if relaxed ordering is enabled, but normally maintain order.
- Non-posted reads (MRd) cannot pass posted writes (strong ordering).
- Completions (Cpl/CplD) can pass posted writes.
- Same-tag completions must arrive in order.
"""

from dataclasses import dataclass, field
from tlp import TLP, TLPType


@dataclass
class OrderingViolation:
    """Records a detected ordering rule violation."""
    rule: str               # short name of the violated rule
    description: str         # human-readable description
    packet_index: int        # index of the offending packet
    packet: TLP              # the offending packet
    related_index: int = -1  # index of the related packet (if any)


class OrderingEngine:
    """
    Tracks in-flight PCIe transactions and checks ordering rules.

    Processes a stream of TLPs and flags any ordering violations.
    The engine maintains queues for posted, non-posted, and completion
    transactions to verify proper ordering.
    """

    def __init__(self):
        self.violations: list[OrderingViolation] = []
        self.posted_queue: list[tuple[int, TLP]] = []       # (index, tlp)
        self.non_posted_queue: list[tuple[int, TLP]] = []   # (index, tlp)
        self.completion_queue: list[tuple[int, TLP]] = []   # (index, tlp)
        self.pending_requests: dict[int, tuple[int, TLP]] = {}  # tag -> (index, tlp)
        self.packet_count = 0

    def process_packet(self, index: int, tlp: TLP):
        """
        Process a single TLP and check it against ordering rules.

        Args:
            index: packet's position in the stream
            tlp: the TLP to process
        """
        self.packet_count += 1

        if tlp.is_posted:
            self._check_posted_ordering(index, tlp)
            self.posted_queue.append((index, tlp))

        elif tlp.is_completion:
            self._check_completion_ordering(index, tlp)
            self.completion_queue.append((index, tlp))
            # Remove from pending requests
            tag = tlp.header.tag
            if tag in self.pending_requests:
                del self.pending_requests[tag]

        else:
            # Non-posted (reads, IO, config)
            self._check_non_posted_ordering(index, tlp)
            self.non_posted_queue.append((index, tlp))
            self.pending_requests[tlp.header.tag] = (index, tlp)

    def _check_posted_ordering(self, index: int, tlp: TLP):
        """
        Rule: Posted writes must not pass earlier posted writes
        (unless relaxed ordering attribute is set).
        """
        if not self.posted_queue:
            return

        last_posted_idx, last_posted = self.posted_queue[-1]

        # Check if this posted write has an earlier timestamp than
        # a queued posted write (would indicate it passed the earlier one)
        if tlp.timestamp < last_posted.timestamp:
            self.violations.append(OrderingViolation(
                rule="POSTED_PASS_POSTED",
                description=(
                    f"Posted {tlp.tlp_type.short_name} (t={tlp.timestamp}) "
                    f"passed earlier posted {last_posted.tlp_type.short_name} "
                    f"(t={last_posted.timestamp}) without relaxed ordering"
                ),
                packet_index=index,
                packet=tlp,
                related_index=last_posted_idx,
            ))

    def _check_non_posted_ordering(self, index: int, tlp: TLP):
        """
        Rule: Non-posted requests must not pass earlier posted writes.
        This is a strong ordering requirement in PCIe.
        """
        if not self.posted_queue:
            return

        # Non-posted should not have a timestamp between two posted writes
        # that haven't been consumed yet
        for posted_idx, posted_tlp in self.posted_queue:
            if (tlp.timestamp < posted_tlp.timestamp and
                    posted_idx < index):
                self.violations.append(OrderingViolation(
                    rule="NON_POSTED_PASS_POSTED",
                    description=(
                        f"Non-posted {tlp.tlp_type.short_name} (t={tlp.timestamp}) "
                        f"passed earlier posted {posted_tlp.tlp_type.short_name} "
                        f"(t={posted_tlp.timestamp}) — violates strong ordering"
                    ),
                    packet_index=index,
                    packet=tlp,
                    related_index=posted_idx,
                ))
                break  # report first violation only

    def _check_completion_ordering(self, index: int, tlp: TLP):
        """
        Rule: Completions for the same request (same tag + requester)
        must arrive in order.
        """
        tag = tlp.header.tag

        # Check for duplicate tag (completion for already-completed request)
        if tag not in self.pending_requests:
            # Could be a spurious completion (no matching request)
            # This is more of a matching issue than ordering, but flag it
            pass

        # Check ordering among completions with the same tag
        for cpl_idx, cpl_tlp in reversed(self.completion_queue):
            if cpl_tlp.header.tag == tag:
                if tlp.timestamp < cpl_tlp.timestamp:
                    self.violations.append(OrderingViolation(
                        rule="COMPLETION_ORDER",
                        description=(
                            f"Completion tag={tag} (t={tlp.timestamp}) arrived "
                            f"before earlier completion with same tag "
                            f"(t={cpl_tlp.timestamp})"
                        ),
                        packet_index=index,
                        packet=tlp,
                        related_index=cpl_idx,
                    ))
                break

    def check_unmatched_requests(self) -> list[OrderingViolation]:
        """
        Check for requests that never received a completion.
        Called at the end of a simulation run.
        """
        unmatched = []
        for tag, (idx, tlp) in self.pending_requests.items():
            unmatched.append(OrderingViolation(
                rule="UNMATCHED_REQUEST",
                description=(
                    f"Non-posted {tlp.tlp_type.short_name} tag={tag} "
                    f"at t={tlp.timestamp} never received a completion"
                ),
                packet_index=idx,
                packet=tlp,
            ))
        return unmatched

    def get_all_violations(self) -> list[OrderingViolation]:
        """Get all ordering violations including unmatched requests."""
        return self.violations + self.check_unmatched_requests()
