#ifndef RETRY_H
#define RETRY_H

#include <Arduino.h>
#include "../config.h"

/**
 * Transmission retry handler.
 *
 * Wraps a send operation with configurable retry count and
 * linear backoff delay.
 */
class RetryHandler {
public:
    RetryHandler(int maxRetries = TX_RETRY_COUNT,
                 unsigned long baseDelayMs = TX_RETRY_DELAY_MS);

    /**
     * Attempt to send data with retries.
     *
     * @param sendFunc A function that attempts to send and returns true on success
     * @return true if any attempt succeeded
     */
    bool sendWithRetry(bool (*sendFunc)(const uint8_t* data, size_t len),
                       const uint8_t* data, size_t len);

    /// Get the number of attempts made in the last sendWithRetry call
    int getLastAttemptCount() const { return _lastAttempts; }

private:
    int _maxRetries;
    unsigned long _baseDelayMs;
    int _lastAttempts;
};

#endif // RETRY_H
