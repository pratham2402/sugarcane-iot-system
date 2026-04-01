#ifndef VALIDATORS_H
#define VALIDATORS_H

/**
 * Validation utilities for sensor readings and telemetry data.
 */
class Validators {
public:
    /// Check if a float value is within [min, max] inclusive
    static bool isInRange(float value, float min, float max) {
        return (value >= min && value <= max);
    }

    /// Check if an integer value is within [min, max] inclusive
    static bool isInRange(int value, int min, int max) {
        return (value >= min && value <= max);
    }

    /// Check if a float value is not NaN and not infinite
    static bool isFinite(float value) {
        return !isnan(value) && !isinf(value);
    }
};

#endif // VALIDATORS_H
