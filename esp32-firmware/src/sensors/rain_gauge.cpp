#include "rain_gauge.h"
#include "../utils/validators.h"

// Static member initialization
volatile uint32_t RainGaugeSensor::_pulseCount = 0;
volatile unsigned long RainGaugeSensor::_lastPulseTime = 0;
unsigned long RainGaugeSensor::_debounceInterval = RAIN_DEBOUNCE_MS;

RainGaugeSensor::RainGaugeSensor(uint8_t pin, unsigned long debounceMs)
    : _pin(pin)
    , _debounceMs(debounceMs)
    , _value(0)
    , _valid(false)
    , _initialized(false) {
    _debounceInterval = debounceMs;
}

bool RainGaugeSensor::begin() {
    pinMode(_pin, INPUT_PULLUP);
    attachInterrupt(digitalPinToInterrupt(_pin), handleInterrupt, FALLING);
    _pulseCount = 0;
    _lastPulseTime = 0;
    _initialized = true;
    Serial.println("[RAIN_GAUGE] Initialized on pin " + String(_pin));
    return true;
}

void IRAM_ATTR RainGaugeSensor::handleInterrupt() {
    unsigned long now = millis();
    if ((now - _lastPulseTime) > _debounceInterval) {
        _pulseCount++;
        _lastPulseTime = now;
    }
}

bool RainGaugeSensor::read() {
    if (!_initialized) {
        _valid = false;
        return false;
    }

    // Atomically read the count
    noInterrupts();
    uint32_t count = _pulseCount;
    interrupts();

    _value = (float)count;
    _valid = Validators::isInRange((int)count, VALID_PULSE_MIN, VALID_PULSE_MAX);

    Serial.printf("[RAIN_GAUGE] Pulses: %u, Valid: %s\n",
                  count, _valid ? "yes" : "no");

    return _valid;
}

void RainGaugeSensor::resetCount() {
    noInterrupts();
    _pulseCount = 0;
    interrupts();
    Serial.println("[RAIN_GAUGE] Counter reset");
}

float RainGaugeSensor::getValue() const {
    return _value;
}

bool RainGaugeSensor::isValid() const {
    return _valid;
}

const char* RainGaugeSensor::getType() const {
    return "rainfall_pulses";
}

const char* RainGaugeSensor::getUnit() const {
    return "pulses";
}

bool RainGaugeSensor::isEnabled() const {
    return SENSOR_RAIN_GAUGE_ENABLED;
}
