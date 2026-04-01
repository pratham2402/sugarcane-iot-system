#ifndef TRANSPORT_H
#define TRANSPORT_H

#include <Arduino.h>

/**
 * Abstract transport interface for sending telemetry packets.
 *
 * Implementations handle the physical layer (LoRa, Serial, etc.)
 * while the rest of the firmware works through this interface.
 */
class ITransport {
public:
    virtual ~ITransport() = default;

    /**
     * Initialize the transport hardware.
     * @return true if initialization succeeded
     */
    virtual bool begin() = 0;

    /**
     * Send a data packet.
     * @param data pointer to the data buffer
     * @param len length of the data in bytes
     * @return true if the packet was sent successfully
     */
    virtual bool send(const uint8_t* data, size_t len) = 0;

    /**
     * Get the maximum payload size supported by this transport.
     * @return maximum bytes per packet
     */
    virtual size_t getMaxPayloadSize() const = 0;

    /**
     * Get the transport type name.
     * @return transport type string (e.g., "lora", "serial")
     */
    virtual const char* getType() const = 0;

    /**
     * Check if the transport is ready to send.
     * @return true if transport is initialized and operational
     */
    virtual bool isReady() const = 0;
};

#endif // TRANSPORT_H
