#ifndef SENSOR_INTERFACE_H
#define SENSOR_INTERFACE_H

#include <Arduino.h>

/**
 * Abstract sensor interface.
 *
 * All field sensors implement this interface, providing a uniform
 * API for initialization, reading, and status checking.
 */
class ISensor {
public:
    virtual ~ISensor() = default;

    /**
     * Initialize the sensor hardware.
     * @return true if initialization succeeded
     */
    virtual bool begin() = 0;

    /**
     * Perform a sensor reading and store the result internally.
     * @return true if the reading was successful and valid
     */
    virtual bool read() = 0;

    /**
     * Get the last reading value.
     * @return the sensor reading as a float
     */
    virtual float getValue() const = 0;

    /**
     * Check if the last reading is valid.
     * @return true if the last reading passed validation
     */
    virtual bool isValid() const = 0;

    /**
     * Get the sensor type name for payload construction.
     * @return sensor type string (e.g., "soil_moisture")
     */
    virtual const char* getType() const = 0;

    /**
     * Get the measurement unit.
     * @return unit string (e.g., "%", "°C")
     */
    virtual const char* getUnit() const = 0;

    /**
     * Check if the sensor is enabled in the configuration.
     * @return true if sensor should be read
     */
    virtual bool isEnabled() const = 0;
};

#endif // SENSOR_INTERFACE_H
