#ifndef CONFIG_H
#define CONFIG_H

/**
 * Sugarcane Field Monitor — ESP32 Node Configuration
 *
 * Adjust these values per-node before flashing.
 * Each field node may have a different subset of sensors.
 */

// ─── Node Identity ───────────────────────────────────────────────────────────

#define NODE_ID             "node-01"
#define FIRMWARE_VERSION    "1.0.0"

// ─── Timing ──────────────────────────────────────────────────────────────────

#define READ_INTERVAL_MS    60000    // Sensor read interval (60 seconds)
#define DEEP_SLEEP_ENABLED  false    // Enable deep sleep between reads
#define DEEP_SLEEP_US       60000000 // Deep sleep duration (60 seconds in µs)

// ─── Sensor Enable Flags ─────────────────────────────────────────────────────
// Set to true for sensors physically connected to this node

#define SENSOR_SOIL_MOISTURE_ENABLED   true
#define SENSOR_DS18B20_ENABLED         true
#define SENSOR_SHT31_ENABLED           true
#define SENSOR_RAIN_GAUGE_ENABLED      false  // Typically only on one node
#define SENSOR_FLOW_METER_ENABLED      false  // Typically only on one node

// ─── Pin Assignments ─────────────────────────────────────────────────────────

// Soil Moisture (Analog)
#define PIN_SOIL_MOISTURE       34     // ADC1 channel — GPIO34
#define SOIL_MOISTURE_AIR       3800   // ADC value in dry air (calibrate per sensor)
#define SOIL_MOISTURE_WATER     1400   // ADC value in water (calibrate per sensor)

// DS18B20 Temperature Probe (OneWire)
#define PIN_DS18B20             4      // GPIO4

// SHT31 (I2C — uses default SDA/SCL)
#define SHT31_I2C_ADDR          0x44   // Default SHT31 address

// Rain Gauge (Pulse input)
#define PIN_RAIN_GAUGE          16     // GPIO16 — interrupt-capable
#define RAIN_DEBOUNCE_MS        200    // Debounce interval for tipping bucket

// Flow Meter (Pulse input)
#define PIN_FLOW_METER          17     // GPIO17 — interrupt-capable
#define FLOW_DEBOUNCE_MS        50     // Debounce interval for flow pulses

// Battery Voltage (Analog, via voltage divider)
#define PIN_BATTERY_VOLTAGE     35     // ADC1 channel — GPIO35
#define BATTERY_DIVIDER_RATIO   2.0    // Voltage divider ratio
#define BATTERY_READ_ENABLED    false  // Set true if voltage divider is connected

// ─── LoRa Configuration ─────────────────────────────────────────────────────

#define LORA_FREQUENCY      433.0    // MHz (433.0, 868.0, or 915.0)
#define LORA_BANDWIDTH      125.0    // kHz
#define LORA_SPREADING_FACTOR 9      // 7–12 (higher = longer range, slower)
#define LORA_CODING_RATE    7        // 5–8
#define LORA_SYNC_WORD      0x12     // Network sync word
#define LORA_TX_POWER       17       // dBm (2–20)

// LoRa SPI Pins (typical for common ESP32+SX1278 modules)
#define LORA_PIN_CS         5        // NSS/CS
#define LORA_PIN_DIO0       2        // DIO0 / IRQ
#define LORA_PIN_RST        14       // Reset
#define LORA_PIN_DIO1       -1       // DIO1 (unused for TX-only)

// ─── Communication Settings ─────────────────────────────────────────────────

// Set the active transport: "lora" or "serial"
#define TRANSPORT_MODE      "lora"

#define TX_RETRY_COUNT      3        // Number of transmission retries
#define TX_RETRY_DELAY_MS   500      // Base delay between retries (ms)

// ─── Validation Ranges ──────────────────────────────────────────────────────

#define VALID_SOIL_MOISTURE_MIN     0.0
#define VALID_SOIL_MOISTURE_MAX     100.0
#define VALID_SOIL_TEMP_MIN         -10.0
#define VALID_SOIL_TEMP_MAX         80.0
#define VALID_AIR_TEMP_MIN          -40.0
#define VALID_AIR_TEMP_MAX          85.0
#define VALID_HUMIDITY_MIN          0.0
#define VALID_HUMIDITY_MAX          100.0
#define VALID_PULSE_MIN             0
#define VALID_PULSE_MAX             65535
#define VALID_BATTERY_MIN           0.0
#define VALID_BATTERY_MAX           5.0

#endif // CONFIG_H
