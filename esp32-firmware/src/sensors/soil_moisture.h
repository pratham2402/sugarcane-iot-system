#ifndef SOIL_MOISTURE_H
#define SOIL_MOISTURE_H

#include "sensor_interface.h"
#include "../config.h"

/**
 * Capacitive soil moisture sensor driver.
 *
 * Reads an analog voltage from a capacitive soil moisture probe and maps
 * it to a 0-100% scale based on calibration values in config.h.
 *
 * Higher capacitance (wetter soil) produces a lower ADC value.
 */
class SoilMoistureSensor : public ISensor {
public:
    SoilMoistureSensor(uint8_t pin, int airValue, int waterValue);

    bool begin() override;
    bool read() override;
    float getValue() const override;
    bool isValid() const override;
    const char* getType() const override;
    const char* getUnit() const override;
    bool isEnabled() const override;

private:
    uint8_t _pin;
    int _airValue;      // ADC reading in dry air (0% moisture)
    int _waterValue;    // ADC reading in water (100% moisture)
    float _value;
    bool _valid;
    bool _initialized;
};

#endif // SOIL_MOISTURE_H
