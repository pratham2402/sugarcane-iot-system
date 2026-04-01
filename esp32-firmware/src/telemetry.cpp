#include "telemetry.h"

TelemetryBuilder::TelemetryBuilder() {}

size_t TelemetryBuilder::buildPayload(ISensor** sensors, size_t sensorCount,
                                       float batteryVoltage,
                                       char* output, size_t outputSize) {
    // Allocate JSON document — 512 bytes is sufficient for our payload
    JsonDocument doc;

    // Top-level fields (compact keys)
    doc["n"] = NODE_ID;
    doc["t"] = (unsigned long)(millis() / 1000);  // Uptime in seconds (no RTC)
    doc["fw"] = FIRMWARE_VERSION;

    // Battery voltage (if available)
    if (batteryVoltage >= 0) {
        doc["bv"] = serialized(String(batteryVoltage, 2));
    }

    // Determine and set status
    doc["s"] = determineStatus(sensors, sensorCount);

    // Build readings object
    JsonObject readings = doc["r"].to<JsonObject>();

    int enabledCount = 0;
    int validCount = 0;

    for (size_t i = 0; i < sensorCount; i++) {
        if (sensors[i] == nullptr || !sensors[i]->isEnabled()) {
            continue;
        }

        enabledCount++;
        const char* compactKey = getCompactKey(sensors[i]->getType());

        // Create [value, valid] array for each reading
        JsonArray reading = readings[compactKey].to<JsonArray>();
        reading.add(serialized(String(sensors[i]->getValue(), 1)));
        reading.add(sensors[i]->isValid());

        if (sensors[i]->isValid()) {
            validCount++;
        }
    }

    // Serialize to output buffer
    size_t written = serializeJson(doc, output, outputSize);

    if (written == 0) {
        Serial.println("[TELEMETRY] ERROR: Failed to serialize payload");
        return 0;
    }

    Serial.printf("[TELEMETRY] Built payload: %u bytes, %d/%d sensors valid\n",
                  written, validCount, enabledCount);

    return written;
}

const char* TelemetryBuilder::determineStatus(ISensor** sensors, size_t sensorCount) {
    int enabledCount = 0;
    int validCount = 0;

    for (size_t i = 0; i < sensorCount; i++) {
        if (sensors[i] == nullptr || !sensors[i]->isEnabled()) {
            continue;
        }
        enabledCount++;
        if (sensors[i]->isValid()) {
            validCount++;
        }
    }

    if (enabledCount == 0) return "error";
    if (validCount == enabledCount) return "ok";
    if (validCount > 0) return "degraded";
    return "error";
}

const char* TelemetryBuilder::getCompactKey(const char* sensorType) {
    if (strcmp(sensorType, "soil_moisture") == 0)     return "sm";
    if (strcmp(sensorType, "soil_temperature") == 0)   return "st";
    if (strcmp(sensorType, "air_temperature") == 0)    return "at";
    if (strcmp(sensorType, "humidity") == 0)            return "hu";
    if (strcmp(sensorType, "rainfall_pulses") == 0)     return "rp";
    if (strcmp(sensorType, "flow_pulses") == 0)         return "fp";
    return sensorType;  // Fallback to full name
}
