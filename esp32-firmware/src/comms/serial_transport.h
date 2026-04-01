#ifndef SERIAL_TRANSPORT_H
#define SERIAL_TRANSPORT_H

#include "transport.h"

/**
 * Serial transport implementation for bench testing.
 *
 * Sends telemetry payloads over the USB serial connection.
 * Useful for development and debugging without LoRa hardware.
 * Prefixes packets with a delimiter for easy parsing.
 */
class SerialTransport : public ITransport {
public:
    explicit SerialTransport(unsigned long baudRate = 115200);

    bool begin() override;
    bool send(const uint8_t* data, size_t len) override;
    size_t getMaxPayloadSize() const override;
    const char* getType() const override;
    bool isReady() const override;

private:
    unsigned long _baudRate;
    bool _initialized;
};

#endif // SERIAL_TRANSPORT_H
