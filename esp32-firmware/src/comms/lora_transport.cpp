#include "lora_transport.h"

LoRaTransport::LoRaTransport()
    : _module(LORA_PIN_CS, LORA_PIN_DIO0, LORA_PIN_RST, LORA_PIN_DIO1)
    , _radio(&_module)
    , _initialized(false) {}

bool LoRaTransport::begin() {
    Serial.print("[LORA] Initializing SX1278 at ");
    Serial.print(LORA_FREQUENCY);
    Serial.println(" MHz...");

    int state = _radio.begin(
        LORA_FREQUENCY,
        LORA_BANDWIDTH,
        LORA_SPREADING_FACTOR,
        LORA_CODING_RATE,
        LORA_SYNC_WORD,
        LORA_TX_POWER
    );

    if (state != RADIOLIB_ERR_NONE) {
        Serial.print("[LORA] ERROR: Init failed with code ");
        Serial.println(state);
        _initialized = false;
        return false;
    }

    // Disable CRC for slightly faster transmission; gateway validates via JSON parsing
    _radio.setCRC(false);

    _initialized = true;
    Serial.println("[LORA] Initialized successfully");
    Serial.printf("[LORA] SF=%d, BW=%.0fkHz, Power=%ddBm\n",
                  LORA_SPREADING_FACTOR, LORA_BANDWIDTH, LORA_TX_POWER);

    return true;
}

bool LoRaTransport::send(const uint8_t* data, size_t len) {
    if (!_initialized) {
        Serial.println("[LORA] ERROR: Not initialized");
        return false;
    }

    if (len > getMaxPayloadSize()) {
        Serial.printf("[LORA] ERROR: Payload too large (%u > %u bytes)\n",
                      len, getMaxPayloadSize());
        return false;
    }

    Serial.printf("[LORA] Sending %u bytes...\n", len);

    int state = _radio.transmit(data, len);

    if (state == RADIOLIB_ERR_NONE) {
        Serial.printf("[LORA] Sent OK (%.1f dBm, %u bytes)\n",
                      _radio.getDataRate(), len);
        return true;
    }

    Serial.printf("[LORA] Send failed with code %d\n", state);
    return false;
}

size_t LoRaTransport::getMaxPayloadSize() const {
    // LoRa max payload varies by SF/BW; 255 bytes is the protocol max
    return 255;
}

const char* LoRaTransport::getType() const {
    return "lora";
}

bool LoRaTransport::isReady() const {
    return _initialized;
}
