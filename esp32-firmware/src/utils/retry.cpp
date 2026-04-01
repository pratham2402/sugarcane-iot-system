#include "retry.h"

RetryHandler::RetryHandler(int maxRetries, unsigned long baseDelayMs)
    : _maxRetries(maxRetries)
    , _baseDelayMs(baseDelayMs)
    , _lastAttempts(0) {}

bool RetryHandler::sendWithRetry(bool (*sendFunc)(const uint8_t* data, size_t len),
                                  const uint8_t* data, size_t len) {
    _lastAttempts = 0;

    for (int attempt = 0; attempt <= _maxRetries; attempt++) {
        _lastAttempts = attempt + 1;

        if (attempt > 0) {
            unsigned long delayMs = _baseDelayMs * attempt;  // Linear backoff
            Serial.printf("[RETRY] Attempt %d/%d after %lums delay\n",
                          attempt + 1, _maxRetries + 1, delayMs);
            delay(delayMs);
        }

        if (sendFunc(data, len)) {
            if (attempt > 0) {
                Serial.printf("[RETRY] Succeeded on attempt %d\n", attempt + 1);
            }
            return true;
        }

        Serial.printf("[RETRY] Attempt %d failed\n", attempt + 1);
    }

    Serial.printf("[RETRY] All %d attempts failed\n", _maxRetries + 1);
    return false;
}
