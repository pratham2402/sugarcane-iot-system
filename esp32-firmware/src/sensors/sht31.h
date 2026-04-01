#ifndef SHT31_SENSOR_H
#define SHT31_SENSOR_H

#include "sensor_interface.h"
#include "../config.h"
#include <Adafruit_SHT31.h>

/**
 * SHT31 air temperature and humidity sensor driver.
 *
 * Communicates via I2C. This sensor provides two readings — this
 * class exposes them as two separate ISensor instances via the
 * inner AirTemperature and Humidity classes.
 *
 * Usage:
 *   SHT31Driver driver;
 *   SHT31Driver::AirTemperature airTemp(driver);
 *   SHT31Driver::Humidity humidity(driver);
 */
class SHT31Driver {
public:
    SHT31Driver();

    bool begin();
    bool read();

    float getTemperature() const { return _temperature; }
    float getHumidity() const { return _humidity; }
    bool isTempValid() const { return _tempValid; }
    bool isHumidityValid() const { return _humValid; }
    bool isInitialized() const { return _initialized; }

    // ─── Air Temperature Adapter ─────────────────────────────────────────────

    class AirTemperature : public ISensor {
    public:
        explicit AirTemperature(SHT31Driver& driver) : _driver(driver) {}

        bool begin() override { return _driver.begin(); }
        bool read() override { return _driver.read() && _driver.isTempValid(); }
        float getValue() const override { return _driver.getTemperature(); }
        bool isValid() const override { return _driver.isTempValid(); }
        const char* getType() const override { return "air_temperature"; }
        const char* getUnit() const override { return "°C"; }
        bool isEnabled() const override { return SENSOR_SHT31_ENABLED; }

    private:
        SHT31Driver& _driver;
    };

    // ─── Humidity Adapter ────────────────────────────────────────────────────

    class Humidity : public ISensor {
    public:
        explicit Humidity(SHT31Driver& driver) : _driver(driver) {}

        bool begin() override { return _driver.begin(); }
        bool read() override { return _driver.read() && _driver.isHumidityValid(); }
        float getValue() const override { return _driver.getHumidity(); }
        bool isValid() const override { return _driver.isHumidityValid(); }
        const char* getType() const override { return "humidity"; }
        const char* getUnit() const override { return "%"; }
        bool isEnabled() const override { return SENSOR_SHT31_ENABLED; }

    private:
        SHT31Driver& _driver;
    };

private:
    Adafruit_SHT31 _sht;
    float _temperature;
    float _humidity;
    bool _tempValid;
    bool _humValid;
    bool _initialized;
    bool _readThisCycle;  // Avoid redundant reads in same cycle
};

#endif // SHT31_SENSOR_H
