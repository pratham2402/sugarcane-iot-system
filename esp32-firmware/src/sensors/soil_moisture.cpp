#include "soil_moisture.h"
#include "../utils/validators.h"

SoilMoistureSensor::SoilMoistureSensor(uint8_t pin, int airValue, int waterValue)
    : _pin(pin)
    , _airValue(airValue)
    , _waterValue(waterValue)
    , _value(0.0)
    , _valid(false)
    , _initialized(false) {}

bool SoilMoistureSensor::begin() {
    pinMode(_pin, INPUT);
    // ESP32 ADC1 channels don't need special setup beyond pinMode
    _initialized = true;
    Serial.println("[SOIL_MOISTURE] Initialized on pin " + String(_pin));
    return true;
}

bool SoilMoistureSensor::read() {
    if (!_initialized) {
        _valid = false;
        return false;
    }

    // Take multiple readings and average for stability
    const int NUM_SAMPLES = 10;
    const int SAMPLE_DELAY_MS = 10;
    long total = 0;

    for (int i = 0; i < NUM_SAMPLES; i++) {
        total += analogRead(_pin);
        delay(SAMPLE_DELAY_MS);
    }

    int rawValue = total / NUM_SAMPLES;

    // Map ADC value to 0-100% moisture
    // Note: Higher capacitance (more moisture) = lower ADC value
    _value = map(rawValue, _airValue, _waterValue, 0, 10000) / 100.0;

    // Clamp to valid range
    _value = constrain(_value, 0.0, 100.0);

    // Validate the reading
    _valid = Validators::isInRange(_value,
                                   VALID_SOIL_MOISTURE_MIN,
                                   VALID_SOIL_MOISTURE_MAX);

    Serial.printf("[SOIL_MOISTURE] Raw: %d, Mapped: %.1f%%, Valid: %s\n",
                  rawValue, _value, _valid ? "yes" : "no");

    return _valid;
}

float SoilMoistureSensor::getValue() const {
    return _value;
}

bool SoilMoistureSensor::isValid() const {
    return _valid;
}

const char* SoilMoistureSensor::getType() const {
    return "soil_moisture";
}

const char* SoilMoistureSensor::getUnit() const {
    return "%";
}

bool SoilMoistureSensor::isEnabled() const {
    return SENSOR_SOIL_MOISTURE_ENABLED;
}
