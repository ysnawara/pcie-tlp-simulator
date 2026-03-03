"""
TLP Generator — creates valid and intentionally invalid PCIe TLPs.
Used to generate traffic for simulation and validation testing.
"""

import random
from tlp import TLP, TLPHeader, TLPType, DeviceID, CompletionStatus


def generate_memory_read(requester: DeviceID, address: int, length: int = 1,
                         tag: int = 0, timestamp: int = 0) -> TLP:
    """
    Generate a Memory Read TLP.

    Memory reads are non-posted — the requester expects a completion
    with the requested data. Uses 32-bit addressing if address fits
    in 32 bits, otherwise 64-bit.

    Args:
        requester: device issuing the read
        address: target memory address
        length: data length in doublewords (1-1024)
        tag: transaction tag for matching the completion
        timestamp: simulation time
    """
    tlp_type = TLPType.MRd64 if address > 0xFFFFFFFF else TLPType.MRd32

    header = TLPHeader(
        tlp_type=tlp_type,
        length=length,
        requester_id=requester,
        tag=tag,
        address=address,
    )
    return TLP(header=header, timestamp=timestamp)


def generate_memory_write(requester: DeviceID, address: int,
                          data: bytes, tag: int = 0,
                          timestamp: int = 0) -> TLP:
    """
    Generate a Memory Write TLP.

    Memory writes are posted — no completion is expected.
    Data length is derived from the payload size.
    """
    tlp_type = TLPType.MWr64 if address > 0xFFFFFFFF else TLPType.MWr32
    length_dw = (len(data) + 3) // 4  # round up to doublewords

    header = TLPHeader(
        tlp_type=tlp_type,
        length=length_dw,
        requester_id=requester,
        tag=tag,
        address=address,
    )
    return TLP(header=header, data=data, timestamp=timestamp)


def generate_completion(completer: DeviceID, requester: DeviceID,
                        tag: int, data: bytes = b"",
                        status: CompletionStatus = CompletionStatus.SC,
                        timestamp: int = 0) -> TLP:
    """
    Generate a Completion TLP.

    Completions are sent in response to non-posted requests (reads, IO, config).
    CplD carries data, Cpl is a status-only response.
    """
    tlp_type = TLPType.CplD if data else TLPType.Cpl
    length_dw = (len(data) + 3) // 4 if data else 0

    header = TLPHeader(
        tlp_type=tlp_type,
        length=length_dw,
        requester_id=requester,
        tag=tag,
        completer_id=completer,
        status=status,
        byte_count=len(data),
    )
    return TLP(header=header, data=data, timestamp=timestamp)


def generate_io_read(requester: DeviceID, address: int,
                     tag: int = 0, timestamp: int = 0) -> TLP:
    """Generate an IO Read TLP (always 1 DW, 32-bit address)."""
    header = TLPHeader(
        tlp_type=TLPType.IORd,
        length=1,
        requester_id=requester,
        tag=tag,
        address=address & 0xFFFFFFFF,
    )
    return TLP(header=header, timestamp=timestamp)


def generate_config_read(requester: DeviceID, target: DeviceID,
                         register: int, tag: int = 0,
                         timestamp: int = 0) -> TLP:
    """
    Generate a Configuration Read Type 0 TLP.
    Register address is in bytes (must be 4-byte aligned).
    """
    # Config space address encodes the target BDF and register offset
    address = (target.to_int() << 12) | (register & 0xFFC)

    header = TLPHeader(
        tlp_type=TLPType.CfgRd0,
        length=1,
        requester_id=requester,
        tag=tag,
        address=address,
    )
    return TLP(header=header, timestamp=timestamp)


def generate_random_traffic(num_packets: int = 20,
                            seed: int = 42) -> list[TLP]:
    """
    Generate a realistic random mix of PCIe traffic.

    Creates a sequence of reads, writes, and completions with
    proper request-completion pairing.

    Args:
        num_packets: total number of TLPs to generate
        seed: random seed for reproducibility
    """
    random.seed(seed)

    device_a = DeviceID(bus=0, device=1, function=0)   # CPU / Root Complex
    device_b = DeviceID(bus=1, device=0, function=0)   # PCIe endpoint

    packets = []
    pending_reads = []  # (requester, tag, timestamp) awaiting completion
    tag_counter = 0
    time = 0

    for _ in range(num_packets):
        time += random.randint(5, 20)

        # If there are pending reads, sometimes generate a completion
        if pending_reads and random.random() < 0.4:
            req_id, req_tag, _ = pending_reads.pop(0)
            data = bytes(random.randint(0, 255) for _ in range(4))
            pkt = generate_completion(
                completer=device_b, requester=req_id,
                tag=req_tag, data=data, timestamp=time,
            )
            packets.append(pkt)
            continue

        # Generate a random transaction
        choice = random.random()
        if choice < 0.35:
            # Memory Read
            addr = random.randint(0, 0xFFFFF) * 4  # aligned
            tag_counter = (tag_counter + 1) % 256
            pkt = generate_memory_read(
                requester=device_a, address=addr,
                length=random.choice([1, 2, 4]),
                tag=tag_counter, timestamp=time,
            )
            pending_reads.append((device_a, tag_counter, time))
        elif choice < 0.70:
            # Memory Write
            addr = random.randint(0, 0xFFFFF) * 4
            data_len = random.choice([4, 8, 16])
            data = bytes(random.randint(0, 255) for _ in range(data_len))
            pkt = generate_memory_write(
                requester=device_a, address=addr,
                data=data, timestamp=time,
            )
        elif choice < 0.85:
            # IO Read
            addr = random.randint(0, 0x3FF) * 4
            tag_counter = (tag_counter + 1) % 256
            pkt = generate_io_read(
                requester=device_a, address=addr,
                tag=tag_counter, timestamp=time,
            )
            pending_reads.append((device_a, tag_counter, time))
        else:
            # Config Read
            tag_counter = (tag_counter + 1) % 256
            pkt = generate_config_read(
                requester=device_a, target=device_b,
                register=random.choice([0x00, 0x04, 0x08, 0x10, 0x3C]),
                tag=tag_counter, timestamp=time,
            )
            pending_reads.append((device_a, tag_counter, time))

        packets.append(pkt)

    # Generate completions for any remaining pending reads
    for req_id, req_tag, _ in pending_reads:
        time += random.randint(5, 15)
        data = bytes(random.randint(0, 255) for _ in range(4))
        pkt = generate_completion(
            completer=device_b, requester=req_id,
            tag=req_tag, data=data, timestamp=time,
        )
        packets.append(pkt)

    return packets
