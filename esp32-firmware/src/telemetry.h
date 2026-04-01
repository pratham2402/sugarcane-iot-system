#ifndef TELEMETRY_H
#define TELEMETRY_H

#include <Arduino.h>
#include <ArduinoJson.h>
#include "config.h"
#include "sensors/sensor_interface.h"

/**
 * Telemetry payload builder.
 *
 * Constructs a compact JSON payload from sensor readings following
 * the shared data contract. Uses short keys for LoRa-optimized transmission.
 */
class TelemetryBuilder {
public:
    TelemetryBuilder();

    /**
     * Build a compact telemetry payload from sensor readings.
     *
     * @param sensors Array of ISensor pointers (nulls are skipped)
     * @param sensorCount Number of sensors in the array
     * @param batteryVoltage Battery voltage (negative if not available)
     * @param output Buffer to write the JSON string into
     * @param outputSize Size of the output buffer
     * @return Number of bytes written, or 0 on failure
     */
    size_t buildPayload(ISensor** sensors, size_t sensorCount,
                        float batteryVoltage,
                        char* output, size_t outputSize);

    /**
     * Determine the overall node status from sensor readings.
     *
     * @param sensors Array of ISensor pointers
     * @param sensorCount Number of sensors
     * @return "ok", "degraded", or "error"
     */
    static const char* determineStatus(ISensor** sensors, size_t sensorCount);

private:
    /**
     * Get the compact key for a sensor type.
     */
    static const char* getCompactKey(const char* sensorType);
};

#endif // TELEMETRY_H
