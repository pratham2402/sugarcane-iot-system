"""
Abstract base receiver for telemetry packet reception.

All receiver implementations (LoRa, mock, serial, etc.) inherit from
this base class to provide a uniform interface for the gateway.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
import time


@dataclass
class RawPacket:
    """A raw received packet before parsing."""
    data: str                    # Raw payload string
    received_at: float           # Unix timestamp of reception
    rssi: Optional[float] = None  # Signal strength (dBm), if available
    snr: Optional[float] = None   # Signal-to-noise ratio, if available
    source: str = "unknown"       # Receiver type identifier

    def __post_init__(self):
        if self.received_at is None:
            self.received_at = time.time()


class BaseReceiver(ABC):
    """Abstract base class for telemetry receivers."""

    @abstractmethod
    def start(self) -> None:
        """Initialize and start the receiver."""
        pass

    @abstractmethod
    def receive(self) -> Optional[RawPacket]:
        """
        Attempt to receive a packet.

        Returns a RawPacket if data is available, or None if no packet
        is ready. This should be non-blocking or have a short timeout.
        """
        pass

    @abstractmethod
    def stop(self) -> None:
        """Stop the receiver and release resources."""
        pass

    @abstractmethod
    def is_active(self) -> bool:
        """Check if the receiver is running."""
        pass
