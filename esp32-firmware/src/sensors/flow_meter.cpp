#include "flow_meter.h"
#include "../utils/validators.h"

// Static member initialization
volatile uint32_t FlowMeterSensor::_pulseCount = 0;
volatile unsigned long FlowMeterSensor::_lastPulseTime = 0;
unsigned long FlowMeterSensor::_debounceInterval = FLOW_DEBOUNCE_MS;

FlowMeterSensor::FlowMeterSensor(uint8_t pin, unsigned long debounceMs)
    : _pin(pin)
    , _debounceMs(debounceMs)
    , _value(0)
    , _valid(false)
    , _initialized(false) {
    _debounceInterval = debounceMs;
}

bool FlowMeterSensor::begin() {
    pinMode(_pin, INPUT_PULLUP);
    attachInterrupt(digitalPinToInterrupt(_pin), handleInterrupt, FALLING);
    _pulseCount = 0;
    _lastPulseTime = 0;
    _initialized = true;
    Serial.println("[FLOW_METER] Initialized on pin " + String(_pin));
    return true;
}

void IRAM_ATTR FlowMeterSensor::handleInterrupt() {
    unsigned long now = millis();
    if ((now - _lastPulseTime) > _debounceInterval) {
        _pulseCount++;
        _lastPulseTime = now;
    }
}

bool FlowMeterSensor::read() {
    if (!_initialized) {
        _valid = false;
        return false;
    }

    noInterrupts();
    uint32_t count = _pulseCount;
    interrupts();

    _value = (float)count;
    _valid = Validators::isInRange((int)count, VALID_PULSE_MIN, VALID_PULSE_MAX);

    Serial.printf("[FLOW_METER] Pulses: %u, Valid: %s\n",
                  count, _valid ? "yes" : "no");

    return _valid;
}

void FlowMeterSensor::resetCount() {
    noInterrupts();
    _pulseCount = 0;
    interrupts();
    Serial.println("[FLOW_METER] Counter reset");
}

float FlowMeterSensor::getValue() const {
    return _value;
}

bool FlowMeterSensor::isValid() const {
    return _valid;
}

const char* FlowMeterSensor::getType() const {
    return "flow_pulses";
}

const char* FlowMeterSensor::getUnit() const {
    return "pulses";
}

bool FlowMeterSensor::isEnabled() const {
    return SENSOR_FLOW_METER_ENABLED;
}
