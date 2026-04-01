#ifndef DS18B20_H
#define DS18B20_H

#include "sensor_interface.h"
#include "../config.h"
#include <OneWire.h>
#include <DallasTemperature.h>

/**
 * DS18B20 waterproof soil temperature probe driver.
 *
 * Uses the OneWire protocol. Multiple probes can share a single bus,
 * but this implementation reads only the first device found.
 */
class DS18B20Sensor : public ISensor {
public:
    explicit DS18B20Sensor(uint8_t pin);

    bool begin() override;
    bool read() override;
    float getValue() const override;
    bool isValid() const override;
    const char* getType() const override;
    const char* getUnit() const override;
    bool isEnabled() const override;

private:
    uint8_t _pin;
    OneWire _oneWire;
    DallasTemperature _dallas;
    float _value;
    bool _valid;
    bool _initialized;
};

#endif // DS18B20_H
