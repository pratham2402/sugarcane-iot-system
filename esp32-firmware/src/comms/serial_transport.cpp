#include "serial_transport.h"

// Packet delimiter for parsing serial stream
static const char* PACKET_START = "<<PKT>>";
static const char* PACKET_END   = "<</PKT>>";

SerialTransport::SerialTransport(unsigned long baudRate)
    : _baudRate(baudRate)
    , _initialized(false) {}

bool SerialTransport::begin() {
    // Serial is typically already initialized in setup(), so just mark ready
    _initialized = true;
    Serial.println("[SERIAL_TX] Serial transport initialized (debug mode)");
    return true;
}

bool SerialTransport::send(const uint8_t* data, size_t len) {
    if (!_initialized) {
        return false;
    }

    // Write delimited packet to serial
    Serial.println(PACKET_START);
    Serial.write(data, len);
    Serial.println();
    Serial.println(PACKET_END);
    Serial.flush();

    Serial.printf("[SERIAL_TX] Sent %u bytes via serial\n", len);
    return true;
}

size_t SerialTransport::getMaxPayloadSize() const {
    return 1024;  // No real limit on serial
}

const char* SerialTransport::getType() const {
    return "serial";
}

bool SerialTransport::isReady() const {
    return _initialized;
}
