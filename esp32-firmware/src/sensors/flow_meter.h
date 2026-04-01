#ifndef FLOW_METER_H
#define FLOW_METER_H

#include "sensor_interface.h"
#include "../config.h"

/**
 * Pulse-output water flow meter driver.
 *
 * Counts pulses from a Hall-effect flow sensor via hardware interrupt.
 * Pulse frequency is proportional to flow rate.
 * The count is reset after each read cycle.
 */
class FlowMeterSensor : public ISensor {
public:
    explicit FlowMeterSensor(uint8_t pin, unsigned long debounceMs);

    bool begin() override;
    bool read() override;
    float getValue() const override;
    bool isValid() const override;
    const char* getType() const override;
    const char* getUnit() const override;
    bool isEnabled() const override;

    /// Reset the pulse counter (called after reading)
    void resetCount();

    /// ISR-safe pulse counter
    static void IRAM_ATTR handleInterrupt();

private:
    uint8_t _pin;
    unsigned long _debounceMs;
    float _value;
    bool _valid;
    bool _initialized;

    static volatile uint32_t _pulseCount;
    static volatile unsigned long _lastPulseTime;
    static unsigned long _debounceInterval;
};

#endif // FLOW_METER_H
