#ifndef LORA_TRANSPORT_H
#define LORA_TRANSPORT_H

#include "transport.h"
#include "../config.h"
#include <RadioLib.h>

/**
 * LoRa transport implementation using RadioLib (SX1276/SX1278).
 *
 * Sends JSON telemetry packets via LoRa to the Raspberry Pi gateway.
 * Configured for point-to-point transmission in the selected frequency band.
 */
class LoRaTransport : public ITransport {
public:
    LoRaTransport();

    bool begin() override;
    bool send(const uint8_t* data, size_t len) override;
    size_t getMaxPayloadSize() const override;
    const char* getType() const override;
    bool isReady() const override;

private:
    SX1278 _radio;
    Module _module;
    bool _initialized;
};

#endif // LORA_TRANSPORT_H
