// =====================================================================
// main_wifi.cpp — v0.4.5-best
//
// Stable field firmware:
//   - DS18B20 GPIO4   → soil temperature
//   - DHT11   GPIO19  → air temperature + humidity
//   - RS485   UART2   → soil moisture register 0x0000 ÷ 10
//
// MAX485:
//   RO = GPIO16
//   DI = GPIO17
//   DE+RE = GPIO14
//
// Soil sensor confirmed:
//   Slave ID = 0x01
//   Baud = 4800
// =====================================================================

#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <DHT.h>
#include <ModbusMaster.h>

// -------------------- CONFIG --------------------
const char* WIFI_SSID = "YOUR_WIFI_SSID";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";

const char* BACKEND_URL = "http://sugarcanepi.local:8000/telemetry/ingest";
const char* NODE_ID = "node-01";
const char* FIRMWARE_VERSION = "0.4.5-best";

const unsigned long SEND_INTERVAL_MS = 10000;

// Pins
#define DS18B20_PIN   4
#define DHT11_PIN     19
#define DHT_TYPE      DHT11

#define MAX485_DE_RE  14
#define UART2_RX      16
#define UART2_TX      17

// Modbus
#define MODBUS_SLAVE_ID   0x01
#define MODBUS_BAUD       4800
#define REG_SOIL_MOISTURE 0x0000

// -------------------- GLOBALS --------------------
unsigned long lastSendTime = 0;

OneWire oneWire(DS18B20_PIN);
DallasTemperature soilTempSensor(&oneWire);
DHT dht(DHT11_PIN, DHT_TYPE);
ModbusMaster modbus;

// -------------------- MAX485 CONTROL --------------------
void preTransmission() {
    digitalWrite(MAX485_DE_RE, HIGH);
    delayMicroseconds(500);
}

void postTransmission() {
    delayMicroseconds(1500);
    digitalWrite(MAX485_DE_RE, LOW);
}

// -------------------- WIFI --------------------
void connectToWiFi() {
    Serial.print("Connecting to WiFi: ");
    Serial.println(WIFI_SSID);

    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

    int attempts = 0;
    while (WiFi.status() != WL_CONNECTED && attempts < 30) {
        delay(500);
        Serial.print(".");
        attempts++;
    }

    if (WiFi.status() == WL_CONNECTED) {
        Serial.println();
        Serial.print("Connected. IP: ");
        Serial.println(WiFi.localIP());
    } else {
        Serial.println();
        Serial.println("WiFi failed — retry later");
    }
}

// -------------------- RS485 --------------------
bool readSoilMoisture(float &moisture) {
    delay(100);

    uint8_t result = modbus.readHoldingRegisters(REG_SOIL_MOISTURE, 1);

    if (result == modbus.ku8MBSuccess) {
        uint16_t raw = modbus.getResponseBuffer(0);

        moisture = raw / 10.0;
        moisture = constrain(moisture, 0, 100);

        Serial.printf("[RS485] raw=%u -> %.1f %%\n", raw, moisture);
        return true;
    } else {
        Serial.printf("[RS485] read failed: 0x%02X\n", result);
        return false;
    }
}

// -------------------- TELEMETRY --------------------
void sendTelemetry() {
    if (WiFi.status() != WL_CONNECTED) {
        Serial.println("WiFi disconnected — reconnecting...");
        connectToWiFi();
        return;
    }

    // DS18B20
    soilTempSensor.requestTemperatures();
    float soilTempC = soilTempSensor.getTempCByIndex(0);
    bool soilTempValid =
        (soilTempC != DEVICE_DISCONNECTED_C &&
         soilTempC > -50 &&
         soilTempC < 80);

    // DHT11
    float airTempC = dht.readTemperature();
    float humidity = dht.readHumidity();
    bool dhtValid = !isnan(airTempC) && !isnan(humidity);

    // RS485
    float soilMoisture = 0.0;
    bool moistureValid = readSoilMoisture(soilMoisture);

    Serial.printf("DS18B20: %.2f C (%s)\n",
                  soilTempC,
                  soilTempValid ? "valid" : "invalid");

    Serial.printf("DHT11: %.1f C %.1f %% RH (%s)\n",
                  airTempC,
                  humidity,
                  dhtValid ? "valid" : "invalid");

    // ---------------- JSON ----------------
    JsonDocument doc;

    doc["node_id"] = NODE_ID;
    doc["timestamp"] = (uint32_t)(millis() / 1000);
    doc["firmware_version"] = FIRMWARE_VERSION;
    doc["battery_voltage"] = 3.75;
    doc["status"] =
        (soilTempValid && dhtValid && moistureValid)
            ? "ok"
            : "degraded";

    JsonObject readings = doc["readings"].to<JsonObject>();

    JsonObject st = readings["soil_temperature"].to<JsonObject>();
    st["value"] = soilTempValid ? soilTempC : 0.0;
    st["unit"] = "C";
    st["valid"] = soilTempValid;

    JsonObject at = readings["air_temperature"].to<JsonObject>();
    at["value"] = dhtValid ? airTempC : 0.0;
    at["unit"] = "C";
    at["valid"] = dhtValid;

    JsonObject hu = readings["humidity"].to<JsonObject>();
    hu["value"] = dhtValid ? humidity : 0.0;
    hu["unit"] = "%";
    hu["valid"] = dhtValid;

    JsonObject sm = readings["soil_moisture"].to<JsonObject>();
    sm["value"] = moistureValid ? soilMoisture : 0.0;
    sm["unit"] = "%";
    sm["valid"] = moistureValid;

    String payload;
    serializeJson(doc, payload);

    Serial.println("Sending payload:");
    Serial.println(payload);

    HTTPClient http;
    http.begin(BACKEND_URL);
    http.addHeader("Content-Type", "application/json");

    int code = http.POST(payload);

    if (code > 0) {
        Serial.printf("HTTP %d — %s\n",
                      code,
                      http.getString().c_str());
    } else {
        Serial.printf("HTTP error: %s\n",
                      http.errorToString(code).c_str());
    }

    http.end();
}

// -------------------- SETUP --------------------
void setup() {
    Serial.begin(115200);
    delay(1000);

    Serial.println();
    Serial.println("===================================================");
    Serial.println(" Sugarcane IoT — ESP32 Firmware v0.4.5-best");
    Serial.println("===================================================");

    // DS18B20
    soilTempSensor.begin();
    Serial.printf("DS18B20 devices found: %d\n",
                  soilTempSensor.getDeviceCount());

    // DHT11
    dht.begin();
    Serial.println("DHT11 initialized");

    // MAX485
    pinMode(MAX485_DE_RE, OUTPUT);
    digitalWrite(MAX485_DE_RE, LOW);

    Serial2.begin(MODBUS_BAUD, SERIAL_8N1, UART2_RX, UART2_TX);

    while (Serial2.available()) Serial2.read();

    modbus.begin(MODBUS_SLAVE_ID, Serial2);
    modbus.preTransmission(preTransmission);
    modbus.postTransmission(postTransmission);

    Serial.printf("Modbus started: slave=0x%02X baud=%d\n",
                  MODBUS_SLAVE_ID,
                  MODBUS_BAUD);

    delay(2500);

    // First DHT read
    float t = dht.readTemperature();
    float h = dht.readHumidity();

    if (isnan(t) || isnan(h)) {
        Serial.println("WARNING: DHT11 first read failed");
    } else {
        Serial.printf("DHT11 first read: %.1f C %.1f %% RH\n", t, h);
    }

    // First moisture read
    float m;
    if (readSoilMoisture(m)) {
        Serial.printf("First moisture read: %.1f %%\n", m);
    } else {
        Serial.println("RS485 first read failed");
    }

    connectToWiFi();
}

// -------------------- LOOP --------------------
void loop() {
    unsigned long now = millis();

    if (now - lastSendTime >= SEND_INTERVAL_MS || lastSendTime == 0) {
        sendTelemetry();
        lastSendTime = now;
    }
}