#include "ds18b20.h"
#include "../utils/validators.h"

DS18B20Sensor::DS18B20Sensor(uint8_t pin)
    : _pin(pin)
    , _oneWire(pin)
    , _dallas(&_oneWire)
    , _value(0.0)
    , _valid(false)
    , _initialized(false) {}

bool DS18B20Sensor::begin() {
    _dallas.begin();

    int deviceCount = _dallas.getDeviceCount();
    if (deviceCount == 0) {
        Serial.println("[DS18B20] ERROR: No devices found on pin " + String(_pin));
        _initialized = false;
        return false;
    }

    // Set resolution to 12-bit for best accuracy (750ms conversion)
    _dallas.setResolution(12);
    _dallas.setWaitForConversion(true);

    Serial.printf("[DS18B20] Initialized on pin %d, found %d device(s)\n",
                  _pin, deviceCount);
    _initialized = true;
    return true;
}

bool DS18B20Sensor::read() {
    if (!_initialized) {
        _valid = false;
        return false;
    }

    _dallas.requestTemperatures();
    float temp = _dallas.getTempCByIndex(0);

    // DallasTemperature returns DEVICE_DISCONNECTED_C (-127) on failure
    if (temp == DEVICE_DISCONNECTED_C) {
        Serial.println("[DS18B20] ERROR: Device disconnected or read failure");
        _valid = false;
        return false;
    }

    _value = temp;
    _valid = Validators::isInRange(_value,
                                   VALID_SOIL_TEMP_MIN,
                                   VALID_SOIL_TEMP_MAX);

    Serial.printf("[DS18B20] Temperature: %.2f°C, Valid: %s\n",
                  _value, _valid ? "yes" : "no");

    return _valid;
}

float DS18B20Sensor::getValue() const {
    return _value;
}

bool DS18B20Sensor::isValid() const {
    return _valid;
}

const char* DS18B20Sensor::getType() const {
    return "soil_temperature";
}

const char* DS18B20Sensor::getUnit() const {
    return "°C";
}

bool DS18B20Sensor::isEnabled() const {
    return SENSOR_DS18B20_ENABLED;
}
