#include "sht31.h"
#include "../utils/validators.h"

SHT31Driver::SHT31Driver()
    : _temperature(0.0)
    , _humidity(0.0)
    , _tempValid(false)
    , _humValid(false)
    , _initialized(false)
    , _readThisCycle(false) {}

bool SHT31Driver::begin() {
    if (_initialized) return true;

    if (!_sht.begin(SHT31_I2C_ADDR)) {
        Serial.println("[SHT31] ERROR: Could not find sensor at address 0x"
                       + String(SHT31_I2C_ADDR, HEX));
        return false;
    }

    // Enable the built-in heater briefly to clear condensation on startup
    _sht.heater(true);
    delay(1000);
    _sht.heater(false);

    _initialized = true;
    Serial.println("[SHT31] Initialized at address 0x" + String(SHT31_I2C_ADDR, HEX));
    return true;
}

bool SHT31Driver::read() {
    if (!_initialized) {
        _tempValid = false;
        _humValid = false;
        return false;
    }

    // Avoid reading the hardware twice in the same sensor cycle.
    // Reset this flag externally before each sensor read cycle.
    if (_readThisCycle) return (_tempValid || _humValid);
    _readThisCycle = true;

    _temperature = _sht.readTemperature();
    _humidity = _sht.readHumidity();

    // SHT31 returns NaN on communication failure
    if (isnan(_temperature)) {
        Serial.println("[SHT31] ERROR: Temperature read failed");
        _tempValid = false;
    } else {
        _tempValid = Validators::isInRange(_temperature,
                                           VALID_AIR_TEMP_MIN,
                                           VALID_AIR_TEMP_MAX);
    }

    if (isnan(_humidity)) {
        Serial.println("[SHT31] ERROR: Humidity read failed");
        _humValid = false;
    } else {
        _humValid = Validators::isInRange(_humidity,
                                          VALID_HUMIDITY_MIN,
                                          VALID_HUMIDITY_MAX);
    }

    Serial.printf("[SHT31] Temp: %.1f°C (%s), Humidity: %.1f%% (%s)\n",
                  _temperature, _tempValid ? "valid" : "INVALID",
                  _humidity, _humValid ? "valid" : "INVALID");

    return (_tempValid || _humValid);
}
