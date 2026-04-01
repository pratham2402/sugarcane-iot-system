#ifndef RAIN_GAUGE_H
#define RAIN_GAUGE_H

#include "sensor_interface.h"
#include "../config.h"

/**
 * Tipping-bucket rain gauge driver.
 *
 * Counts pulses from a tipping bucket rain gauge via hardware interrupt.
 * Each tip represents a fixed volume of rainfall (typically 0.2794mm).
 * The count is reset after each read cycle.
 */
class RainGaugeSensor : public ISensor {
public:
    explicit RainGaugeSensor(uint8_t pin, unsigned long debounceMs);

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
    float _value;  // Pulse count as float for ISensor interface
    bool _valid;
    bool _initialized;

    static volatile uint32_t _pulseCount;
    static volatile unsigned long _lastPulseTime;
    static unsigned long _debounceInterval;
};

#endif // RAIN_GAUGE_H
