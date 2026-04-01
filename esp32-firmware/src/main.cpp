/**
 * Sugarcane Field Monitor — ESP32 Edge Node Firmware
 *
 * Main entry point. Initializes sensors and transport, then enters a
 * read → build → transmit loop at the configured interval.
 *
 * Configuration: see config.h for node identity, pin assignments,
 * sensor enable flags, LoRa parameters, and timing.
 */

#include <Arduino.h>
#include "config.h"
#include "telemetry.h"
#include "sensors/sensor_interface.h"
#include "sensors/soil_moisture.h"
#include "sensors/ds18b20.h"
#include "sensors/sht31.h"
#include "sensors/rain_gauge.h"
#include "sensors/flow_meter.h"
#include "comms/transport.h"
#include "comms/lora_transport.h"
#include "comms/serial_transport.h"
#include "utils/retry.h"

// ─── Global Instances ────────────────────────────────────────────────────────

// Sensors
SoilMoistureSensor soilMoisture(PIN_SOIL_MOISTURE, SOIL_MOISTURE_AIR, SOIL_MOISTURE_WATER);
DS18B20Sensor ds18b20(PIN_DS18B20);
SHT31Driver sht31Driver;
SHT31Driver::AirTemperature airTemp(sht31Driver);
SHT31Driver::Humidity humidity(sht31Driver);
RainGaugeSensor rainGauge(PIN_RAIN_GAUGE, RAIN_DEBOUNCE_MS);
FlowMeterSensor flowMeter(PIN_FLOW_METER, FLOW_DEBOUNCE_MS);

// Sensor array for iteration
static const size_t MAX_SENSORS = 6;
ISensor* sensors[MAX_SENSORS] = {
    &soilMoisture,
    &ds18b20,
    &airTemp,
    &humidity,
    &rainGauge,
    &flowMeter
};

// Transport
LoRaTransport loraTransport;
SerialTransport serialTransport;
ITransport* transport = nullptr;

// Telemetry
TelemetryBuilder telemetryBuilder;
RetryHandler retryHandler;

// Payload buffer
static const size_t PAYLOAD_BUFFER_SIZE = 300;
char payloadBuffer[PAYLOAD_BUFFER_SIZE];

// Timing
unsigned long lastReadTime = 0;

// ─── Static wrapper for retry handler ────────────────────────────────────────
// (RetryHandler needs a function pointer, so we use a static wrapper)

static ITransport* _activeTransport = nullptr;

static bool sendViaTransport(const uint8_t* data, size_t len) {
    if (_activeTransport == nullptr) return false;
    return _activeTransport->send(data, len);
}

// ─── Battery Voltage Reader ─────────────────────────────────────────────────

float readBatteryVoltage() {
    if (!BATTERY_READ_ENABLED) return -1.0;

    int raw = analogRead(PIN_BATTERY_VOLTAGE);
    float voltage = (raw / 4095.0) * 3.3 * BATTERY_DIVIDER_RATIO;
    return voltage;
}

// ─── Setup ───────────────────────────────────────────────────────────────────

void setup() {
    Serial.begin(115200);
    delay(1000);  // Allow serial to stabilize

    Serial.println("========================================");
    Serial.printf("  Sugarcane Field Monitor v%s\n", FIRMWARE_VERSION);
    Serial.printf("  Node: %s\n", NODE_ID);
    Serial.println("========================================");

    // Initialize enabled sensors
    int initOk = 0;
    int initFail = 0;

    for (size_t i = 0; i < MAX_SENSORS; i++) {
        if (sensors[i] != nullptr && sensors[i]->isEnabled()) {
            Serial.printf("[INIT] Starting sensor: %s\n", sensors[i]->getType());
            if (sensors[i]->begin()) {
                initOk++;
            } else {
                Serial.printf("[INIT] WARNING: %s failed to initialize\n",
                              sensors[i]->getType());
                initFail++;
            }
        }
    }
    Serial.printf("[INIT] Sensors: %d OK, %d failed\n", initOk, initFail);

    // Initialize transport
    if (String(TRANSPORT_MODE) == "lora") {
        Serial.println("[INIT] Using LoRa transport");
        transport = &loraTransport;
    } else {
        Serial.println("[INIT] Using Serial transport (debug mode)");
        transport = &serialTransport;
    }

    if (!transport->begin()) {
        Serial.println("[INIT] CRITICAL: Transport init failed!");
        Serial.println("[INIT] Falling back to Serial transport");
        transport = &serialTransport;
        transport->begin();
    }

    _activeTransport = transport;

    Serial.printf("[INIT] Transport: %s (max payload: %u bytes)\n",
                  transport->getType(), transport->getMaxPayloadSize());
    Serial.printf("[INIT] Read interval: %d ms\n", READ_INTERVAL_MS);
    Serial.println("[INIT] Setup complete. Entering main loop.");
    Serial.println("========================================");
}

// ─── Main Loop ───────────────────────────────────────────────────────────────

void loop() {
    unsigned long now = millis();

    // Check if it's time for a read cycle
    if (now - lastReadTime < READ_INTERVAL_MS && lastReadTime != 0) {
        delay(100);  // Small delay to avoid busy-waiting
        return;
    }
    lastReadTime = now;

    Serial.println("\n--- Read Cycle ---");

    // Read all enabled sensors
    for (size_t i = 0; i < MAX_SENSORS; i++) {
        if (sensors[i] != nullptr && sensors[i]->isEnabled()) {
            sensors[i]->read();
        }
    }

    // Read battery voltage
    float batteryV = readBatteryVoltage();
    if (batteryV >= 0) {
        Serial.printf("[BATTERY] Voltage: %.2fV\n", batteryV);
    }

    // Build telemetry payload
    size_t payloadLen = telemetryBuilder.buildPayload(
        sensors, MAX_SENSORS, batteryV,
        payloadBuffer, PAYLOAD_BUFFER_SIZE
    );

    if (payloadLen == 0) {
        Serial.println("[MAIN] ERROR: Failed to build payload, skipping");
        return;
    }

    // Debug: print payload
    Serial.printf("[MAIN] Payload (%u bytes): %s\n", payloadLen, payloadBuffer);

    // Transmit with retry
    bool sent = retryHandler.sendWithRetry(
        sendViaTransport,
        (const uint8_t*)payloadBuffer,
        payloadLen
    );

    if (sent) {
        Serial.printf("[MAIN] Transmitted OK (attempt %d)\n",
                      retryHandler.getLastAttemptCount());
    } else {
        Serial.println("[MAIN] WARNING: Transmission failed after all retries");
        // TODO: Store locally on SPIFFS/SD for later retry
    }

    // Reset pulse counters after successful read
    if (SENSOR_RAIN_GAUGE_ENABLED) {
        rainGauge.resetCount();
    }
    if (SENSOR_FLOW_METER_ENABLED) {
        flowMeter.resetCount();
    }

    Serial.println("--- End Cycle ---");

    // Deep sleep handling
    if (DEEP_SLEEP_ENABLED) {
        Serial.println("[MAIN] Entering deep sleep...");
        Serial.flush();
        esp_deep_sleep_start();
    }
}
