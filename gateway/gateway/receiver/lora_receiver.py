"""
LoRa receiver implementation for Raspberry Pi.

Uses SPI to communicate with an SX1276/SX1278 LoRa module connected
to the Raspberry Pi's GPIO header. Requires spidev and RPi.GPIO packages.

This receiver runs on the actual Raspberry Pi hardware. For development
and testing without hardware, use MockReceiver instead.
"""

import time
import logging
from typing import Optional

from .base_receiver import BaseReceiver, RawPacket

logger = logging.getLogger(__name__)


class LoRaReceiver(BaseReceiver):
    """
    LoRa packet receiver using SX1276/SX1278 via SPI.

    This implementation provides a hardware-oriented receiver that
    interfaces with a LoRa transceiver module. It handles:
    - SPI initialization and configuration
    - LoRa radio parameter setup (frequency, SF, BW, etc.)
    - Continuous receive mode
    - Packet reception with RSSI/SNR metadata
    """

    def __init__(self, config: dict):
        """
        Initialize LoRa receiver with configuration.

        Args:
            config: LoRa configuration dict from gateway_config.yaml
        """
        self.config = config
        self._active = False
        self._spi = None
        self._last_error = None

        # Radio parameters from config
        self.frequency = config.get("frequency", 433.0)
        self.bandwidth = config.get("bandwidth", 125.0)
        self.spreading_factor = config.get("spreading_factor", 9)
        self.coding_rate = config.get("coding_rate", 7)
        self.sync_word = config.get("sync_word", 0x12)

        # Pin assignments
        self.pin_cs = config.get("pin_cs", 8)
        self.pin_reset = config.get("pin_reset", 25)
        self.pin_dio0 = config.get("pin_dio0", 24)

    def start(self) -> None:
        """Initialize LoRa hardware and enter receive mode."""
        try:
            import spidev
            import RPi.GPIO as GPIO

            logger.info("Initializing LoRa receiver...")

            # Setup GPIO
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
            GPIO.setup(self.pin_reset, GPIO.OUT)
            GPIO.setup(self.pin_dio0, GPIO.IN)

            # Reset the module
            GPIO.output(self.pin_reset, GPIO.LOW)
            time.sleep(0.01)
            GPIO.output(self.pin_reset, GPIO.HIGH)
            time.sleep(0.01)

            # Initialize SPI
            self._spi = spidev.SpiDev()
            self._spi.open(
                self.config.get("spi_bus", 0),
                self.config.get("spi_device", 0)
            )
            self._spi.max_speed_hz = 5000000

            # Configure LoRa registers
            self._configure_radio()

            # Enter continuous receive mode
            self._set_rx_mode()

            self._active = True
            logger.info(
                f"LoRa receiver started: {self.frequency}MHz, "
                f"SF{self.spreading_factor}, BW{self.bandwidth}kHz"
            )

        except ImportError:
            logger.error(
                "LoRa dependencies not available. "
                "Install spidev and RPi.GPIO on Raspberry Pi."
            )
            raise
        except Exception as e:
            self._last_error = str(e)
            logger.error(f"LoRa initialization failed: {e}")
            raise

    def receive(self) -> Optional[RawPacket]:
        """
        Check for and receive a LoRa packet.

        Returns RawPacket if a packet is available, None otherwise.
        Non-blocking — checks DIO0 interrupt pin.
        """
        if not self._active:
            return None

        try:
            import RPi.GPIO as GPIO

            # Check if DIO0 indicates a received packet
            if not GPIO.input(self.pin_dio0):
                return None

            # Read the packet from the FIFO
            payload, rssi, snr = self._read_packet()

            if payload:
                packet = RawPacket(
                    data=payload,
                    received_at=time.time(),
                    rssi=rssi,
                    snr=snr,
                    source="lora"
                )
                logger.debug(
                    f"Received LoRa packet: {len(payload)} bytes, "
                    f"RSSI={rssi}dBm, SNR={snr}dB"
                )

                # Re-enter receive mode for next packet
                self._set_rx_mode()

                return packet

        except Exception as e:
            logger.error(f"LoRa receive error: {e}")
            self._last_error = str(e)

        return None

    def stop(self) -> None:
        """Stop LoRa receiver and release hardware resources."""
        self._active = False
        if self._spi:
            self._spi.close()
            self._spi = None
        try:
            import RPi.GPIO as GPIO
            GPIO.cleanup()
        except ImportError:
            pass
        logger.info("LoRa receiver stopped")

    def is_active(self) -> bool:
        return self._active

    # ─── Private Hardware Methods ─────────────────────────────────────────────

    def _write_register(self, address: int, value: int) -> None:
        """Write a single byte to a LoRa register."""
        self._spi.xfer2([address | 0x80, value])

    def _read_register(self, address: int) -> int:
        """Read a single byte from a LoRa register."""
        response = self._spi.xfer2([address & 0x7F, 0x00])
        return response[1]

    def _configure_radio(self) -> None:
        """Configure the SX1276/SX1278 registers for LoRa mode."""
        # Set sleep mode
        self._write_register(0x01, 0x00)
        time.sleep(0.01)

        # Set LoRa mode
        self._write_register(0x01, 0x80)
        time.sleep(0.01)

        # Set frequency
        frf = int((self.frequency * (2**19)) / 32.0)
        self._write_register(0x06, (frf >> 16) & 0xFF)
        self._write_register(0x07, (frf >> 8) & 0xFF)
        self._write_register(0x08, frf & 0xFF)

        # Set bandwidth, coding rate, and implicit/explicit header
        bw_map = {
            7.8: 0, 10.4: 1, 15.6: 2, 20.8: 3,
            31.25: 4, 41.7: 5, 62.5: 6, 125.0: 7,
            250.0: 8, 500.0: 9
        }
        bw_val = bw_map.get(self.bandwidth, 7)
        cr_val = self.coding_rate - 4
        self._write_register(0x1D, (bw_val << 4) | (cr_val << 1) | 0x00)

        # Set spreading factor
        self._write_register(0x1E, (self.spreading_factor << 4) | 0x04)

        # Set sync word
        self._write_register(0x39, self.sync_word)

        # Set max payload length
        self._write_register(0x23, 255)

        logger.debug("LoRa radio configured")

    def _set_rx_mode(self) -> None:
        """Put the radio into continuous receive mode."""
        # Set DIO0 to RxDone
        self._write_register(0x40, 0x00)
        # Clear IRQ flags
        self._write_register(0x12, 0xFF)
        # Set FIFO address
        self._write_register(0x0F, 0x00)
        # Enter RX continuous mode
        self._write_register(0x01, 0x85)

    def _read_packet(self) -> tuple:
        """
        Read a received packet from the FIFO.

        Returns (payload_str, rssi, snr) or (None, None, None) on failure.
        """
        # Clear IRQ flags
        irq_flags = self._read_register(0x12)
        self._write_register(0x12, irq_flags)

        # Check for CRC error
        if irq_flags & 0x20:
            logger.warning("LoRa packet CRC error")
            return None, None, None

        # Get packet length
        packet_len = self._read_register(0x13)

        # Set FIFO address to last packet
        current_addr = self._read_register(0x10)
        self._write_register(0x0D, current_addr)

        # Read FIFO
        payload_bytes = []
        for _ in range(packet_len):
            payload_bytes.append(self._read_register(0x00))

        # Get RSSI and SNR
        rssi = -157 + self._read_register(0x1A)
        snr = self._read_register(0x19)
        if snr > 127:
            snr = (snr - 256) / 4.0
        else:
            snr = snr / 4.0

        try:
            payload_str = bytes(payload_bytes).decode("utf-8")
            return payload_str, rssi, snr
        except UnicodeDecodeError:
            logger.warning("Failed to decode LoRa packet as UTF-8")
            return None, None, None
