// Farmer App — Main JavaScript
// Phases 2–7: hero, lucide icons, sparkline, weather, yield breakdown,
//             crop selection, splash, image diagnosis (Gemini Vision)

// ============================================
// CONFIG
// ============================================
const SPEECH_LANG = "mr-IN";
const DEFAULT_PI_URL = "http://sugarcanepi.local:8000";
const DASHBOARD_POLL_MS = 10000;
const STALE_THRESHOLD_SEC = 600;
const MAHARASHTRA_AVG_TPH = 91;
const HA_PER_ACRE = 0.4047;
const NOTIF_POLL_MS = 30000;
const SPLASH_DURATION_MS = 1200;
const MOISTURE_HISTORY_HOURS = 24;
const MAX_IMAGE_DIM = 800;
const MAX_IMAGE_BYTES = 4 * 1024 * 1024;

// ============================================
// SAFE LUCIDE INIT
// ============================================
function refreshIcons() {
  if (window.lucide && typeof window.lucide.createIcons === "function") {
    try {
      window.lucide.createIcons();
    } catch (e) {
      console.warn("Lucide error:", e);
    }
  }
}

// ============================================
// THEME
// ============================================
function getTheme() {
  return localStorage.getItem("theme") || "light";
}

function setTheme(theme) {
  localStorage.setItem("theme", theme);
  document.documentElement.setAttribute("data-theme", theme);
  const icon = document.getElementById("theme-toggle-icon");
  if (icon) {
    icon.setAttribute("data-lucide", theme === "dark" ? "sun" : "moon");
    refreshIcons();
  }
}

function toggleTheme() {
  setTheme(getTheme() === "dark" ? "light" : "dark");
}

// ============================================
// CROP SELECTION
// ============================================
function getSelectedCrop() {
  return localStorage.getItem("selectedCrop");
}

function setSelectedCrop(crop) {
  localStorage.setItem("selectedCrop", crop);
}

// ============================================
// NOTIFICATION PREFS
// ============================================
function getNotifEnabled() {
  const v = localStorage.getItem("notifEnabled");
  return v === null ? true : v === "true";
}
function setNotifEnabled(v) {
  localStorage.setItem("notifEnabled", String(v));
}
function getLastSeenActionId() {
  const v = localStorage.getItem("lastSeenActionId");
  return v ? parseInt(v, 10) : null;
}
function setLastSeenActionId(id) {
  localStorage.setItem("lastSeenActionId", String(id));
}

// ============================================
// PI URL + TOKEN + FARM
// ============================================
function getPiUrl() {
  return localStorage.getItem("piUrl") || DEFAULT_PI_URL;
}
function setPiUrl(url) {
  localStorage.setItem("piUrl", url);
}
function getPiToken() {
  return localStorage.getItem("piToken") || "";
}
function setPiToken(token) {
  localStorage.setItem("piToken", token);
}
function authHeaders(extra = {}) {
  const token = getPiToken();
  const headers = { ...extra };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  return headers;
}

const FARM_DEFAULTS = {
  acres: null,
  fertilizer_per_acre_kg: null,
  pesticide_per_acre_kg: null,
  soil_type: "",
  irrigation: "flood",
  variety: "",
  planting_date: "",
};

function getFarm() {
  try {
    const raw = localStorage.getItem("farm");
    if (!raw) return { ...FARM_DEFAULTS };
    const parsed = JSON.parse(raw);
    return { ...FARM_DEFAULTS, ...parsed };
  } catch {
    return { ...FARM_DEFAULTS };
  }
}
function setFarm(farm) {
  localStorage.setItem("farm", JSON.stringify(farm));
}

let dashboardPollTimer = null;
let activeTab = "chat";
let lastYieldData = null;
let notifPollTimer = null;
let digestShown = false;

// ============================================
// DOM REFERENCES
// ============================================
const splashScreen = document.getElementById("splash-screen");
const cropSelection = document.getElementById("crop-selection");
const cropContinueBtn = document.getElementById("crop-continue-btn");
const cropCards = document.querySelectorAll(".crop-card");
const changeCropBtn = document.getElementById("change-crop-btn");
const appRoot = document.getElementById("app");

const chatArea = document.getElementById("chat-area");
const textInput = document.getElementById("text-input");
const sendBtn = document.getElementById("send-btn");
const micBtn = document.getElementById("mic-btn");
const cameraBtn = document.getElementById("camera-btn");
const cameraInput = document.getElementById("camera-input");

const navButtons = document.querySelectorAll(".nav-btn");
const tabContents = document.querySelectorAll(".tab-content");
const connectionDot = document.getElementById("connection-dot");
const themeToggleBtn = document.getElementById("theme-toggle");

// Settings — Pi
const piUrlInput = document.getElementById("pi-url-input");
const savePiBtn = document.getElementById("save-pi-btn");
const testPiBtn = document.getElementById("test-pi-btn");
const piStatus = document.getElementById("pi-status");
const piTokenInput = document.getElementById("pi-token-input");
const saveTokenBtn = document.getElementById("save-token-btn");
const tokenStatus = document.getElementById("token-status");

// Settings — Farm
const farmAcresInput = document.getElementById("farm-acres");
const farmFertilizerInput = document.getElementById("farm-fertilizer");
const farmPesticideInput = document.getElementById("farm-pesticide");
const farmSoilTypeSelect = document.getElementById("farm-soil-type");
const farmIrrigationSelect = document.getElementById("farm-irrigation");
const farmVarietyInput = document.getElementById("farm-variety");
const farmPlantingDateInput = document.getElementById("farm-planting-date");
const saveFarmBtn = document.getElementById("save-farm-btn");
const farmStatus = document.getElementById("farm-status");

// Dashboard
const refreshDashBtn = document.getElementById("refresh-dashboard-btn");
const dashStatus = document.getElementById("dashboard-status");
const dashUpdatedText = document.getElementById("dashboard-updated-text");
const dashLiveDot = document.querySelector(".live-dot");
const valSoilMoisture = document.getElementById("val-soil-moisture");
const valSoilTemp = document.getElementById("val-soil-temp");
const valAirTemp = document.getElementById("val-air-temp");
const valHumidity = document.getElementById("val-humidity");
const moistureBadge = document.getElementById("moisture-status-badge");
const moistureSparkline = document.getElementById("moisture-sparkline");
const nodeIdEl = document.getElementById("node-id");
const batteryEl = document.getElementById("battery-voltage");
const nodeStatusEl = document.getElementById("node-status");
const firmwareWarning = document.getElementById("firmware-warning");

// Weather
const weatherTemp = document.getElementById("weather-temp");
const weatherConditions = document.getElementById("weather-conditions");
const weatherHumidity = document.getElementById("weather-humidity");
const weatherWind = document.getElementById("weather-wind");
const weatherLocation = document.getElementById("weather-location");
const weatherForecast = document.getElementById("weather-forecast");
const refreshWeatherBtn = document.getElementById("refresh-weather-btn");

// Valve
const openValveBtn = document.getElementById("open-valve-btn");
const closeValveBtn = document.getElementById("close-valve-btn");
const valveDurationInput = document.getElementById("valve-duration");
const valveStatusEl = document.getElementById("valve-status");
const refreshHistoryBtn = document.getElementById("refresh-history-btn");
const valveHistoryList = document.getElementById("valve-history-list");

const toastContainer = document.getElementById("toast-container");
const notifEnabledToggle = document.getElementById("notif-enabled-toggle");

// Yield
const yieldStatus = document.getElementById("yield-status");
const yieldTotalRow = document.getElementById("yield-total-row");
const yieldTotalTons = document.getElementById("yield-total-tons");
const yieldPerAcre = document.getElementById("yield-per-acre");
const yieldPerHectare = document.getElementById("yield-per-hectare");
const yieldComparison = document.getElementById("yield-comparison");
const yieldConfidence = document.getElementById("yield-confidence");
const yieldInputsSource = document.getElementById("yield-inputs-source");
const yieldInputsList = document.getElementById("yield-inputs-list");
const yieldNote = document.getElementById("yield-note");
const refreshYieldBtn = document.getElementById("refresh-yield-btn");
const factorRainfallBar = document.getElementById("factor-rainfall-bar");
const factorRainfallVal = document.getElementById("factor-rainfall-val");
const factorFertBar = document.getElementById("factor-fert-bar");
const factorFertVal = document.getElementById("factor-fert-val");
const factorPestBar = document.getElementById("factor-pest-bar");
const factorPestVal = document.getElementById("factor-pest-val");

const chipButtons = document.querySelectorAll(".chip");

// ============================================
// TAB SWITCHING
// ============================================
function switchTab(tabName) {
  activeTab = tabName;
  navButtons.forEach((btn) =>
    btn.classList.toggle("active", btn.dataset.tab === tabName),
  );
  tabContents.forEach((tab) =>
    tab.classList.toggle("hidden", tab.id !== `tab-${tabName}`),
  );

  if (tabName === "dashboard") {
    startDashboardPolling();
    fetchAndRenderHistory();
    fetchAndRenderWeather();
    fetchAndRenderMoistureHistory();
  } else {
    stopDashboardPolling();
  }
  if (tabName === "yield" && !lastYieldData) {
    fetchAndRenderYield();
  }
}

navButtons.forEach((btn) => {
  btn.addEventListener("click", () => switchTab(btn.dataset.tab));
});

// ============================================
// CHAT HELPERS
// ============================================
function addMessage(text, sender) {
  const div = document.createElement("div");
  div.className =
    sender === "user" ? "message message-user" : "message message-bot";
  const p = document.createElement("p");
  p.textContent = text;
  div.appendChild(p);
  chatArea.appendChild(div);
  chatArea.scrollTop = chatArea.scrollHeight;
  return div;
}

function addImageMessage(dataUrl, sender) {
  const div = document.createElement("div");
  div.className =
    sender === "user"
      ? "message message-user message-photo"
      : "message message-bot message-photo";
  const img = document.createElement("img");
  img.src = dataUrl;
  img.alt = "Uploaded photo";
  div.appendChild(img);
  chatArea.appendChild(div);
  chatArea.scrollTop = chatArea.scrollHeight;
  return div;
}

// ============================================
// SPEECH-TO-TEXT (unchanged from before)
// ============================================
let recognition = null;
let isListening = false;

function setupSpeechRecognition() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) {
    micBtn.disabled = true;
    return;
  }
  recognition = new SR();
  recognition.lang = SPEECH_LANG;
  recognition.continuous = false;
  recognition.interimResults = true;
  recognition.maxAlternatives = 1;

  recognition.onstart = () => {
    isListening = true;
    const icon = micBtn.querySelector("[data-lucide]");
    if (icon) icon.setAttribute("data-lucide", "mic-off");
    refreshIcons();
    textInput.placeholder = "बोला... (Speak now)";
  };
  recognition.onresult = (event) => {
    let transcript = "";
    for (let i = 0; i < event.results.length; i++) {
      transcript += event.results[i][0].transcript;
    }
    textInput.value = transcript;
  };
  recognition.onend = () => {
    isListening = false;
    const icon = micBtn.querySelector("[data-lucide]");
    if (icon) icon.setAttribute("data-lucide", "mic");
    refreshIcons();
    textInput.placeholder = "तुमचा प्रश्न लिहा...";
    if (textInput.value.trim()) handleSend();
  };
  recognition.onerror = (event) => {
    isListening = false;
    const icon = micBtn.querySelector("[data-lucide]");
    if (icon) icon.setAttribute("data-lucide", "mic");
    refreshIcons();
    textInput.placeholder = "तुमचा प्रश्न लिहा...";
    if (event.error === "not-allowed")
      addMessage("⚠️ माइकची परवानगी द्या", "bot");
    else if (event.error === "no-speech")
      addMessage("⚠️ काहीच ऐकू आले नाही", "bot");
    else if (event.error === "network") addMessage("⚠️ इंटरनेट तपासा", "bot");
  };
  micBtn.disabled = false;
}

function toggleMic() {
  if (!recognition) return;
  if (isListening) recognition.stop();
  else {
    textInput.value = "";
    try {
      recognition.start();
    } catch (e) {
      console.error(e);
    }
  }
}

// ============================================
// TEXT-TO-SPEECH
// ============================================
function detectLang(text) {
  const dev = (text.match(/[\u0900-\u097F]/g) || []).length;
  const lat = (text.match(/[a-zA-Z]/g) || []).length;
  if (lat > dev * 2) return "en-IN";
  const hi = [
    "है",
    "हैं",
    "क्या",
    "कैसे",
    "मुझे",
    "आपकी",
    "आपको",
    "मेरी",
    "मेरा",
  ];
  const mr = [
    "आहे",
    "आहेत",
    "कसे",
    "काय",
    "मला",
    "तुमच्या",
    "तुम्ही",
    "माझे",
    "माझा",
  ];
  let h = 0,
    m = 0;
  hi.forEach((w) => {
    if (text.includes(w)) h++;
  });
  mr.forEach((w) => {
    if (text.includes(w)) m++;
  });
  return h > m ? "hi-IN" : "mr-IN";
}

function speak(text, langOverride = null) {
  if (!window.speechSynthesis) return;
  window.speechSynthesis.cancel();
  const lang = langOverride || detectLang(text);
  const u = new SpeechSynthesisUtterance(text);
  u.lang = lang;
  u.rate = 0.9;
  const voices = window.speechSynthesis.getVoices();
  const v =
    voices.find((x) => x.lang === lang) ||
    voices.find((x) => x.lang.startsWith(lang.split("-")[0]));
  if (v) u.voice = v;
  window.speechSynthesis.speak(u);
}

function preloadVoices() {
  if (!window.speechSynthesis) return;
  let voices = window.speechSynthesis.getVoices();
  if (voices.length === 0) {
    window.speechSynthesis.onvoiceschanged = () => {
      voices = window.speechSynthesis.getVoices();
    };
  }
}

// ============================================
// CHAT — text + sensor + farm context
// ============================================
async function fetchSensorContextForChat() {
  const url = getPiUrl();
  try {
    const ctrl = new AbortController();
    const id = setTimeout(() => ctrl.abort(), 3000);
    const r = await fetch(`${url}/latest-readings`, {
      headers: authHeaders(),
      signal: ctrl.signal,
    });
    clearTimeout(id);
    if (!r.ok) return null;
    const data = await r.json();
    return data.nodes?.length ? data.nodes[0] : null;
  } catch {
    return null;
  }
}

async function handleSend() {
  const text = textInput.value.trim();
  if (!text) return;
  addMessage(text, "user");
  textInput.value = "";
  sendBtn.disabled = true;
  micBtn.disabled = true;

  const thinkingMsg = addMessage("विचार करत आहे... 🤔", "bot");

  try {
    const farm = getFarm();
    const sensor = await fetchSensorContextForChat();
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text, farm, sensor }),
    });
    const data = await response.json();
    thinkingMsg.remove();

    if (!response.ok) {
      if (response.status === 429) {
        addMessage("थोडं थांबा... पुन्हा प्रयत्न करत आहे 🔄", "bot");
        await new Promise((r) => setTimeout(r, 4000));
        try {
          const retry = await fetch("/api/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message: text, farm, sensor }),
          });
          const rd = await retry.json();
          if (retry.ok && rd.reply) {
            addMessage(rd.reply, "bot");
            speak(rd.reply);
            return;
          }
        } catch {}
      }
      addMessage("⚠️ चूक झाली: " + (data.error || "Unknown error"), "bot");
      return;
    }
    const reply = data.reply || "(रिकामं उत्तर मिळालं)";
    addMessage(reply, "bot");
    speak(reply);
  } catch {
    thinkingMsg.remove();
    addMessage("⚠️ इंटरनेट तपासा (Network error)", "bot");
  } finally {
    sendBtn.disabled = false;
    micBtn.disabled = false;
  }
}

// ============================================
// IMAGE DIAGNOSIS — Phase 6 (Gemini Vision)
// ============================================
function resizeImageToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error("Could not read file"));
    reader.onload = () => {
      const img = new Image();
      img.onerror = () => reject(new Error("Invalid image"));
      img.onload = () => {
        let { width, height } = img;
        if (width > MAX_IMAGE_DIM || height > MAX_IMAGE_DIM) {
          if (width > height) {
            height = Math.round((height / width) * MAX_IMAGE_DIM);
            width = MAX_IMAGE_DIM;
          } else {
            width = Math.round((width / height) * MAX_IMAGE_DIM);
            height = MAX_IMAGE_DIM;
          }
        }
        const canvas = document.createElement("canvas");
        canvas.width = width;
        canvas.height = height;
        const ctx = canvas.getContext("2d");
        ctx.drawImage(img, 0, 0, width, height);
        const dataUrl = canvas.toDataURL("image/jpeg", 0.85);
        resolve(dataUrl);
      };
      img.src = reader.result;
    };
    reader.readAsDataURL(file);
  });
}

async function handleImageUpload(event) {
  const file = event.target.files?.[0];
  event.target.value = ""; // allow re-upload of same file
  if (!file) return;

  if (file.size > MAX_IMAGE_BYTES) {
    addMessage("⚠️ फोटो खूप मोठा आहे (max 4MB)", "bot");
    return;
  }

  let dataUrl;
  try {
    dataUrl = await resizeImageToBase64(file);
  } catch (e) {
    addMessage("⚠️ फोटो वाचता आला नाही", "bot");
    return;
  }

  addImageMessage(dataUrl, "user");
  sendBtn.disabled = true;
  cameraBtn.disabled = true;
  micBtn.disabled = true;

  const thinking = addMessage("फोटो तपासत आहे... 🔍", "bot");

  try {
    const farm = getFarm();
    const sensor = await fetchSensorContextForChat();
    const base64Only = dataUrl.split(",")[1];

    const r = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        mode: "diagnose",
        farm,
        sensor,
        image_base64: base64Only,
        image_mime: "image/jpeg",
      }),
    });
    const data = await r.json();
    thinking.remove();

    if (!r.ok) {
      addMessage("⚠️ चूक: " + (data.error || "Could not analyze image"), "bot");
      return;
    }
    const reply = data.reply || "(empty response)";
    addMessage(reply, "bot");
    speak(reply);
  } catch (err) {
    thinking.remove();
    addMessage("⚠️ इंटरनेट तपासा (Network error)", "bot");
  } finally {
    sendBtn.disabled = false;
    cameraBtn.disabled = false;
    micBtn.disabled = false;
  }
}

// ============================================
// SETTINGS — Pi URL save & test
// ============================================
function showPiStatus(message, type) {
  piStatus.textContent = message;
  piStatus.className = `status-box ${type}`;
}

function loadSettingsUI() {
  piUrlInput.value = getPiUrl();
  piTokenInput.value = getPiToken();
  const farm = getFarm();
  if (farm.acres != null) farmAcresInput.value = farm.acres;
  if (farm.fertilizer_per_acre_kg != null)
    farmFertilizerInput.value = farm.fertilizer_per_acre_kg;
  if (farm.pesticide_per_acre_kg != null)
    farmPesticideInput.value = farm.pesticide_per_acre_kg;
  farmSoilTypeSelect.value = farm.soil_type || "";
  farmIrrigationSelect.value = farm.irrigation || "flood";
  farmVarietyInput.value = farm.variety || "";
  farmPlantingDateInput.value = farm.planting_date || "";
}

function showTokenStatus(message, type) {
  tokenStatus.textContent = message;
  tokenStatus.className = `status-box ${type}`;
}

function handleSaveToken() {
  const token = piTokenInput.value.trim();
  if (!token) {
    showTokenStatus("⚠️ Token cannot be empty", "error");
    return;
  }
  if (token.length < 16) {
    showTokenStatus("⚠️ Token looks too short", "error");
    return;
  }
  setPiToken(token);
  showTokenStatus("✓ Token saved", "success");
}

function handleSavePi() {
  const url = piUrlInput.value.trim();
  if (!url) {
    showPiStatus("⚠️ URL cannot be empty", "error");
    return;
  }
  if (!url.startsWith("http://") && !url.startsWith("https://")) {
    showPiStatus("⚠️ URL must start with http:// or https://", "error");
    return;
  }
  setPiUrl(url);
  showPiStatus("✓ Saved", "success");
}

async function handleTestPi() {
  const url = piUrlInput.value.trim();
  if (!url) {
    showPiStatus("⚠️ URL cannot be empty", "error");
    return;
  }
  testPiBtn.disabled = true;
  savePiBtn.disabled = true;
  showPiStatus("⏳ Testing connection...", "loading");

  try {
    const ctrl = new AbortController();
    const id = setTimeout(() => ctrl.abort(), 5000);
    const r = await fetch(`${url}/health`, { signal: ctrl.signal });
    clearTimeout(id);
    if (!r.ok) {
      showPiStatus(
        `✗ Server reachable but /health returned HTTP ${r.status}`,
        "error",
      );
      testPiBtn.disabled = false;
      savePiBtn.disabled = false;
      return;
    }
  } catch (err) {
    if (err.name === "AbortError")
      showPiStatus("✗ Timeout — Pi did not respond.", "error");
    else if (err.message.includes("Failed to fetch"))
      showPiStatus(`✗ Could not reach ${url}`, "error");
    else showPiStatus(`✗ ${err.message}`, "error");
    testPiBtn.disabled = false;
    savePiBtn.disabled = false;
    return;
  }

  try {
    const ctrl = new AbortController();
    const id = setTimeout(() => ctrl.abort(), 5000);
    const r = await fetch(`${url}/latest-readings`, {
      headers: authHeaders(),
      signal: ctrl.signal,
    });
    clearTimeout(id);
    if (r.status === 401) {
      const errBody = await r.json().catch(() => ({}));
      showPiStatus(
        `✗ Token rejected: ${errBody.detail || "Authorization failed"}`,
        "error",
      );
      return;
    }
    if (!r.ok) {
      showPiStatus(`✗ HTTP ${r.status}`, "error");
      return;
    }
    const data = await r.json();
    if (!data.nodes?.length) {
      showPiStatus("⚠️ Connected but no sensor data", "error");
      return;
    }
    const reading = data.nodes[0];
    const ageMin = Math.floor((Date.now() / 1000 - reading.timestamp) / 60);
    showPiStatus(
      `✓ Connected & authenticated\n${reading.node_id} · Soil: ${reading.soil_moisture}% · ${ageMin}min ago`,
      "success",
    );
    setPiUrl(url);
    setConnectionDot("online");
  } catch (err) {
    showPiStatus(`✗ ${err.message}`, "error");
  } finally {
    testPiBtn.disabled = false;
    savePiBtn.disabled = false;
  }
}

// ============================================
// FARM SAVE
// ============================================
function showFarmStatus(message, type) {
  farmStatus.textContent = message;
  farmStatus.className = `status-box ${type}`;
}

function handleSaveFarm() {
  const acresStr = farmAcresInput.value.trim();
  const fertStr = farmFertilizerInput.value.trim();
  const pestStr = farmPesticideInput.value.trim();
  const acres = acresStr === "" ? null : parseFloat(acresStr);
  const fertilizer = fertStr === "" ? null : parseFloat(fertStr);
  const pesticide = pestStr === "" ? null : parseFloat(pestStr);

  if (acres !== null && (isNaN(acres) || acres <= 0)) {
    showFarmStatus("⚠️ Land size must be > 0", "error");
    return;
  }
  if (fertilizer !== null && (isNaN(fertilizer) || fertilizer < 0)) {
    showFarmStatus("⚠️ Fertilizer must be >= 0", "error");
    return;
  }
  if (pesticide !== null && (isNaN(pesticide) || pesticide < 0)) {
    showFarmStatus("⚠️ Pesticide must be >= 0", "error");
    return;
  }

  setFarm({
    acres,
    fertilizer_per_acre_kg: fertilizer,
    pesticide_per_acre_kg: pesticide,
    soil_type: farmSoilTypeSelect.value,
    irrigation: farmIrrigationSelect.value,
    variety: farmVarietyInput.value,
    planting_date: farmPlantingDateInput.value,
  });
  lastYieldData = null;
  showFarmStatus("✓ Saved. Open Yield tab for updated prediction.", "success");
}

// ============================================
// CONNECTION DOT
// ============================================
function setConnectionDot(state) {
  if (!connectionDot) return;
  connectionDot.classList.remove("online", "offline");
  connectionDot.classList.add(state);
}

// ============================================
// DASHBOARD — fetch + render
// ============================================
function timeAgoText(tsSeconds) {
  const diff = Math.floor(Date.now() / 1000 - tsSeconds);
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)} min ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)} hr ago`;
  return `${Math.floor(diff / 86400)} day(s) ago`;
}

function moistureStatusFor(value) {
  if (value == null) return { label: "—", className: "" };
  if (value >= 35) return { label: "Healthy", className: "healthy" };
  if (value >= 25) return { label: "Low", className: "low" };
  return { label: "Critical", className: "critical" };
}

function renderReading(reading) {
  valSoilMoisture.textContent =
    reading.soil_moisture != null ? reading.soil_moisture.toFixed(1) : "—";
  valSoilTemp.textContent =
    reading.soil_temperature != null
      ? reading.soil_temperature.toFixed(1)
      : "—";
  valAirTemp.textContent =
    reading.air_temperature != null ? reading.air_temperature.toFixed(1) : "—";
  valHumidity.textContent =
    reading.humidity != null ? reading.humidity.toFixed(1) : "—";
  nodeIdEl.textContent = reading.node_id || "—";
  batteryEl.textContent =
    reading.battery_voltage != null ? reading.battery_voltage.toFixed(2) : "—";
  nodeStatusEl.textContent = reading.status || "—";
  dashUpdatedText.textContent = `Last reading: ${timeAgoText(reading.timestamp)}`;

  const status = moistureStatusFor(reading.soil_moisture);
  moistureBadge.textContent = status.label;
  moistureBadge.className = `moisture-badge ${status.className}`;

  const ageSec = Date.now() / 1000 - reading.timestamp;
  const isStale = ageSec > STALE_THRESHOLD_SEC;
  const isHistorical = (reading.firmware_version || "").includes("historical");
  firmwareWarning.classList.toggle("hidden", !(isStale || isHistorical));

  if (dashLiveDot) {
    dashLiveDot.classList.remove("offline");
    dashLiveDot.classList.toggle("stale", isStale || isHistorical);
  }
}

function setDashStatus(state, text) {
  dashStatus.className = `status-pill ${state}`;
  dashStatus.textContent = text;
}

async function fetchAndRenderDashboard() {
  const url = getPiUrl();
  setDashStatus("loading", "Loading");
  try {
    const ctrl = new AbortController();
    const id = setTimeout(() => ctrl.abort(), 5000);
    const r = await fetch(`${url}/latest-readings`, {
      headers: authHeaders(),
      signal: ctrl.signal,
    });
    clearTimeout(id);
    if (r.status === 401) {
      setDashStatus("disconnected", "Token");
      setConnectionDot("offline");
      if (dashLiveDot) {
        dashLiveDot.classList.remove("stale");
        dashLiveDot.classList.add("offline");
      }
      return;
    }
    if (!r.ok) {
      setDashStatus("disconnected", `HTTP ${r.status}`);
      setConnectionDot("offline");
      if (dashLiveDot) {
        dashLiveDot.classList.remove("stale");
        dashLiveDot.classList.add("offline");
      }
      return;
    }
    const data = await r.json();
    if (!data.nodes?.length) {
      setDashStatus("disconnected", "No data");
      setConnectionDot("offline");
      return;
    }
    renderReading(data.nodes[0]);
    setDashStatus("connected", "Live");
    setConnectionDot("online");
  } catch (err) {
    if (err.name === "AbortError") setDashStatus("disconnected", "Timeout");
    else setDashStatus("disconnected", "Offline");
    setConnectionDot("offline");
    dashUpdatedText.textContent = "Check Pi connection";
    if (dashLiveDot) {
      dashLiveDot.classList.remove("stale");
      dashLiveDot.classList.add("offline");
    }
  }
}

function startDashboardPolling() {
  fetchAndRenderDashboard();
  if (dashboardPollTimer) clearInterval(dashboardPollTimer);
  dashboardPollTimer = setInterval(fetchAndRenderDashboard, DASHBOARD_POLL_MS);
}

function stopDashboardPolling() {
  if (dashboardPollTimer) {
    clearInterval(dashboardPollTimer);
    dashboardPollTimer = null;
  }
}

async function handleManualRefresh() {
  refreshDashBtn.classList.add("spinning");
  refreshDashBtn.disabled = true;
  await Promise.all([
    fetchAndRenderDashboard(),
    fetchAndRenderMoistureHistory(),
    fetchAndRenderWeather(),
  ]);
  setTimeout(() => {
    refreshDashBtn.classList.remove("spinning");
    refreshDashBtn.disabled = false;
  }, 400);
}

// ============================================
// MOISTURE SPARKLINE — Phase 3
// ============================================
async function fetchAndRenderMoistureHistory() {
  const url = getPiUrl();
  try {
    const ctrl = new AbortController();
    const id = setTimeout(() => ctrl.abort(), 6000);
    const r = await fetch(`${url}/readings?node_id=node-01&limit=500`, {
      headers: authHeaders(),
      signal: ctrl.signal,
    });
    clearTimeout(id);
    if (!r.ok) {
      renderSparkline([]);
      return;
    }
    const data = await r.json();
    const readings = data.readings || data || [];
    if (!readings.length) {
      renderSparkline([]);
      return;
    }

    // Sort all available readings by time
    const sorted = readings
      .filter((rd) => rd.soil_moisture != null)
      .sort((a, b) => a.timestamp - b.timestamp);
    if (!sorted.length) {
      renderSparkline([]);
      return;
    }

    // Use the latest reading's timestamp as "now" for the window
    // This way demo data from March still shows last 24h of available
    const newestT = sorted[sorted.length - 1].timestamp;
    const windowStart = newestT - MOISTURE_HISTORY_HOURS * 3600;
    const points = sorted
      .filter((rd) => rd.timestamp >= windowStart)
      .map((rd) => ({ t: rd.timestamp, v: rd.soil_moisture }));

    renderSparkline(points);
  } catch {
    renderSparkline([]);
  }
}

function renderSparkline(points) {
  if (!moistureSparkline) return;
  if (!points.length) {
    moistureSparkline.innerHTML = `<text x="50%" y="50%" text-anchor="middle" fill="currentColor" font-size="10" opacity="0.5">No history available</text>`;
    return;
  }
  const W = 300,
    H = 60,
    P = 4;
  const minV = Math.min(...points.map((p) => p.v));
  const maxV = Math.max(...points.map((p) => p.v));
  const range = Math.max(maxV - minV, 1);
  const minT = points[0].t;
  const maxT = points[points.length - 1].t;
  const tRange = Math.max(maxT - minT, 1);

  const xy = points.map((p) => {
    const x = P + ((p.t - minT) / tRange) * (W - 2 * P);
    const y = H - P - ((p.v - minV) / range) * (H - 2 * P);
    return [x, y];
  });
  const linePath =
    "M " + xy.map(([x, y]) => `${x.toFixed(1)} ${y.toFixed(1)}`).join(" L ");
  const areaPath = `${linePath} L ${xy[xy.length - 1][0].toFixed(1)} ${H - P} L ${xy[0][0].toFixed(1)} ${H - P} Z`;

  const stressLineY = H - P - ((30 - minV) / range) * (H - 2 * P);
  const showStress = stressLineY > 0 && stressLineY < H;

  moistureSparkline.innerHTML = `
    <defs>
      <linearGradient id="sparkGrad" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="var(--brand-default)" stop-opacity="0.35"/>
        <stop offset="100%" stop-color="var(--brand-default)" stop-opacity="0"/>
      </linearGradient>
    </defs>
    ${
      showStress
        ? `<line x1="0" y1="${stressLineY.toFixed(1)}" x2="${W}" y2="${stressLineY.toFixed(1)}"
      stroke="var(--accent-amber)" stroke-width="1" stroke-dasharray="3,3" opacity="0.6"/>
      <text x="${W - 4}" y="${(stressLineY - 2).toFixed(1)}" text-anchor="end" fill="var(--accent-amber)" font-size="9" opacity="0.75">stress 30%</text>`
        : ""
    }
    <path d="${areaPath}" fill="url(#sparkGrad)" />
    <path d="${linePath}" fill="none" stroke="var(--brand-default)" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
    <circle cx="${xy[xy.length - 1][0].toFixed(1)}" cy="${xy[xy.length - 1][1].toFixed(1)}" r="3" fill="var(--brand-default)"/>
  `;
}

// ============================================
// WEATHER — Phase 3
// ============================================
const weatherIconEmoji = {
  Clear: "☀️",
  Clouds: "⛅",
  Rain: "🌧️",
  Drizzle: "🌦️",
  Thunderstorm: "⛈️",
  Snow: "❄️",
  Mist: "🌫️",
  Haze: "🌫️",
  Fog: "🌫️",
  Smoke: "🌫️",
};

async function fetchAndRenderWeather() {
  const url = getPiUrl();
  try {
    const ctrl = new AbortController();
    const id = setTimeout(() => ctrl.abort(), 8000);
    const r = await fetch(`${url}/weather`, {
      headers: authHeaders(),
      signal: ctrl.signal,
    });
    clearTimeout(id);
    if (!r.ok) {
      if (weatherTemp) weatherTemp.textContent = "—";
      if (weatherConditions)
        weatherConditions.textContent = "Weather unavailable";
      return;
    }
    const data = await r.json();
    const cur = data.current;
    if (weatherLocation) weatherLocation.textContent = data.location_name || "";
    if (weatherTemp)
      weatherTemp.textContent =
        cur.temp_c != null ? Math.round(cur.temp_c) : "—";
    if (weatherConditions) weatherConditions.textContent = cur.conditions || "";
    if (weatherHumidity)
      weatherHumidity.textContent = Math.round(cur.humidity_percent ?? 0);
    if (weatherWind)
      weatherWind.textContent = (cur.wind_speed_ms ?? 0).toFixed(1);

    if (weatherForecast) {
      weatherForecast.innerHTML = "";
      (data.forecast || []).forEach((day) => {
        const card = document.createElement("div");
        card.className = "forecast-day";
        card.innerHTML = `
          <div class="forecast-day-label">${day.day_label}</div>
          <div class="forecast-day-icon">${weatherIconEmoji[day.main] || "☀️"}</div>
          <div class="forecast-day-temps">
            ${Math.round(day.temp_max_c)}° <span class="forecast-day-temp-min">${Math.round(day.temp_min_c)}°</span>
          </div>
          ${day.rain_mm > 0 ? `<div class="forecast-day-rain">💧 ${day.rain_mm.toFixed(1)}mm</div>` : ""}
        `;
        weatherForecast.appendChild(card);
      });
    }
  } catch {
    if (weatherConditions) weatherConditions.textContent = "Weather offline";
  }
}

// ============================================
// VALVE
// ============================================
function showValveStatus(message, type) {
  valveStatusEl.textContent = message;
  valveStatusEl.className = `status-box ${type}`;
}

async function actuateValve(action) {
  const url = getPiUrl();
  const duration = parseInt(valveDurationInput.value, 10) || 30;
  if (action === "open" && (duration < 5 || duration > 120)) {
    showValveStatus("⚠️ Duration must be 5-120 minutes", "error");
    return;
  }
  openValveBtn.disabled = true;
  closeValveBtn.disabled = true;
  showValveStatus(`⏳ Sending ${action}...`, "loading");

  try {
    const ctrl = new AbortController();
    const id = setTimeout(() => ctrl.abort(), 5000);
    const r = await fetch(`${url}/actuate/valve`, {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({
        node_id: "node-01",
        action,
        duration_min: action === "open" ? duration : null,
        requested_by: "user_manual",
        reasoning:
          action === "open"
            ? `Manual irrigation for ${duration} min`
            : "Manual close",
      }),
      signal: ctrl.signal,
    });
    clearTimeout(id);
    if (!r.ok) {
      showValveStatus(`✗ HTTP ${r.status}`, "error");
      return;
    }
    const data = await r.json();
    showValveStatus(`✓ ${data.message || "Valve command logged"}`, "success");
  } catch (err) {
    showValveStatus(
      err.name === "AbortError" ? "✗ Timeout" : "✗ Could not reach Pi",
      "error",
    );
  } finally {
    openValveBtn.disabled = false;
    closeValveBtn.disabled = false;
    fetchAndRenderHistory();
  }
}

// ============================================
// HISTORY
// ============================================
function formatHistoryTime(tsSeconds) {
  const d = new Date(tsSeconds * 1000);
  const diff = Math.floor(Date.now() / 1000 - tsSeconds);
  const dateStr = d.toLocaleString("en-IN", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  });
  let ago;
  if (diff < 60) ago = "just now";
  else if (diff < 3600) ago = `${Math.floor(diff / 60)}m`;
  else if (diff < 86400) ago = `${Math.floor(diff / 3600)}h`;
  else ago = `${Math.floor(diff / 86400)}d`;
  return `${dateStr} (${ago} ago)`;
}

function renderHistory(actions) {
  if (!actions?.length) {
    valveHistoryList.innerHTML = `<div class="history-empty">No irrigation events yet.</div>`;
    return;
  }
  valveHistoryList.innerHTML = "";
  actions.forEach((a) => {
    const isAgent = a.requested_by === "agent";
    const item = document.createElement("div");
    item.className = `history-item ${isAgent ? "agent" : "manual"}`;
    item.innerHTML = `
      <div class="history-row">
        <span class="history-action ${a.action === "close" ? "close" : ""}">${a.action === "open" ? "🟢 Valve OPEN" : "🔴 Valve CLOSE"}</span>
        <span class="history-source-badge ${isAgent ? "agent" : "manual"}">${isAgent ? "AI AGENT" : "MANUAL"}</span>
      </div>
      <div class="history-time">${formatHistoryTime(a.timestamp)}</div>
      ${a.duration_min || a.water_mm ? `<div class="history-meta">${a.duration_min ? "Duration: " + a.duration_min + " min" : ""}${a.duration_min && a.water_mm ? " · " : ""}${a.water_mm ? "Target: " + a.water_mm + " mm" : ""}</div>` : ""}
      ${a.reasoning ? `<div class="history-reasoning">"${a.reasoning}"</div>` : ""}
    `;
    valveHistoryList.appendChild(item);
  });
}

async function fetchAndRenderHistory() {
  const url = getPiUrl();
  valveHistoryList.innerHTML = `<div class="history-empty">Loading...</div>`;
  try {
    const ctrl = new AbortController();
    const id = setTimeout(() => ctrl.abort(), 5000);
    const r = await fetch(`${url}/valve-history?node_id=node-01&limit=10`, {
      headers: authHeaders(),
      signal: ctrl.signal,
    });
    clearTimeout(id);
    if (r.status === 401) {
      valveHistoryList.innerHTML = `<div class="history-empty">Token invalid.</div>`;
      return;
    }
    if (!r.ok) {
      valveHistoryList.innerHTML = `<div class="history-empty">HTTP ${r.status}</div>`;
      return;
    }
    const data = await r.json();
    renderHistory(data.actions || []);
  } catch {
    valveHistoryList.innerHTML = `<div class="history-empty">Could not reach Pi.</div>`;
  }
}

async function handleHistoryRefresh() {
  refreshHistoryBtn.classList.add("spinning");
  refreshHistoryBtn.disabled = true;
  await fetchAndRenderHistory();
  setTimeout(() => {
    refreshHistoryBtn.classList.remove("spinning");
    refreshHistoryBtn.disabled = false;
  }, 400);
}

async function handleClearHistory() {
  const confirmed = confirm(
    "Delete ALL irrigation history for this node?\n\n" +
      "This includes both AI agent decisions and manual actions. " +
      "This cannot be undone.",
  );
  if (!confirmed) return;

  const url = getPiUrl();
  const clearBtn = document.getElementById("clear-history-btn");
  if (clearBtn) clearBtn.disabled = true;
  valveHistoryList.innerHTML = `<div class="history-empty">Clearing...</div>`;

  try {
    const ctrl = new AbortController();
    const id = setTimeout(() => ctrl.abort(), 5000);
    const r = await fetch(`${url}/valve-history?node_id=node-01&confirm=true`, {
      method: "DELETE",
      headers: authHeaders(),
      signal: ctrl.signal,
    });
    clearTimeout(id);

    if (r.status === 401) {
      valveHistoryList.innerHTML = `<div class="history-empty">Token invalid.</div>`;
      return;
    }
    if (!r.ok) {
      valveHistoryList.innerHTML = `<div class="history-empty">Failed: HTTP ${r.status}</div>`;
      return;
    }
    const data = await r.json();
    valveHistoryList.innerHTML = `<div class="history-empty">Cleared ${data.deleted || 0} entries.</div>`;
    setLastSeenActionId(0);
    setTimeout(() => fetchAndRenderHistory(), 1500);
  } catch (err) {
    valveHistoryList.innerHTML = `<div class="history-empty">${
      err.name === "AbortError" ? "Timeout" : "Could not reach Pi"
    }</div>`;
  } finally {
    if (clearBtn) clearBtn.disabled = false;
  }
}

// ============================================
// IN-APP NOTIFICATIONS
// ============================================
function timeAgoShort(tsSeconds) {
  const diff = Math.floor(Date.now() / 1000 - tsSeconds);
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

function showToast(action) {
  const toast = document.createElement("div");
  toast.className = "toast";
  toast.innerHTML = `
    <div class="toast-header">
      <span class="toast-icon">🔔</span>
      <span class="toast-title">${action.action === "open" ? "AI Agent: Irrigate now" : "AI Agent: Stop irrigation"}</span>
      <span class="toast-time">${timeAgoShort(action.timestamp)}</span>
    </div>
    ${action.reasoning ? `<div class="toast-body">"${action.reasoning}"</div>` : ""}
    <div class="toast-actions">
      <button class="toast-btn toast-btn-primary" data-act="view">View</button>
      <button class="toast-btn toast-btn-secondary" data-act="dismiss">Dismiss</button>
    </div>
  `;
  toast.querySelector('[data-act="view"]').addEventListener("click", () => {
    switchTab("dashboard");
    dismissToast(toast);
  });
  toast
    .querySelector('[data-act="dismiss"]')
    .addEventListener("click", () => dismissToast(toast));
  toastContainer.appendChild(toast);
  setTimeout(() => dismissToast(toast), 15000);
  if (navigator.vibrate) navigator.vibrate([200, 100, 200]);
}

function dismissToast(toast) {
  if (!toast.parentNode) return;
  toast.classList.add("dismissing");
  setTimeout(() => {
    if (toast.parentNode) toast.parentNode.removeChild(toast);
  }, 300);
}

async function checkForNewAgentActions() {
  if (!getNotifEnabled()) return;
  const url = getPiUrl();
  try {
    const ctrl = new AbortController();
    const id = setTimeout(() => ctrl.abort(), 4000);
    const r = await fetch(`${url}/valve-history?node_id=node-01&limit=5`, {
      headers: authHeaders(),
      signal: ctrl.signal,
    });
    clearTimeout(id);
    if (!r.ok) return;
    const data = await r.json();
    const actions = data.actions || [];
    if (!actions.length) return;
    const lastSeen = getLastSeenActionId();
    const newActions = actions.filter(
      (a) =>
        a.requested_by === "agent" && (lastSeen === null || a.id > lastSeen),
    );
    if (!newActions.length) {
      const maxId = Math.max(...actions.map((a) => a.id));
      if (lastSeen === null || maxId > lastSeen) setLastSeenActionId(maxId);
      return;
    }
    if (lastSeen === null) {
      setLastSeenActionId(Math.max(...actions.map((a) => a.id)));
      return;
    }
    newActions.sort((a, b) => b.timestamp - a.timestamp).forEach(showToast);
    setLastSeenActionId(Math.max(...actions.map((a) => a.id)));
  } catch {}
}

function startNotifPolling() {
  if (notifPollTimer) clearInterval(notifPollTimer);
  checkForNewAgentActions();
  notifPollTimer = setInterval(checkForNewAgentActions, NOTIF_POLL_MS);
}
function stopNotifPolling() {
  if (notifPollTimer) {
    clearInterval(notifPollTimer);
    notifPollTimer = null;
  }
}
function loadNotifSettingsUI() {
  notifEnabledToggle.checked = getNotifEnabled();
}
function handleNotifEnabledToggle() {
  setNotifEnabled(notifEnabledToggle.checked);
  if (notifEnabledToggle.checked) startNotifPolling();
  else stopNotifPolling();
}

// ============================================
// YIELD — Phase 4 with breakdown
// ============================================
function setYieldStatus(state, text) {
  yieldStatus.className = `status-pill ${state}`;
  yieldStatus.textContent = text;
}

function formatInputKey(key) {
  return key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatInputValue(key, value) {
  // Friendly relabels for non-technical users
  if (key === "season" && String(value).toLowerCase() === "kharif") return "Monsoon (Kharif)";
  if (key === "season" && String(value).toLowerCase() === "rabi") return "Winter (Rabi)";
  return value;
}

function buildYieldOverrides(farm) {
  const overrides = {};
  if (farm.fertilizer_per_acre_kg != null)
    overrides.fertilizer_per_ha_kg = +(
      farm.fertilizer_per_acre_kg / HA_PER_ACRE
    ).toFixed(2);
  if (farm.pesticide_per_acre_kg != null)
    overrides.pesticide_per_ha_kg = +(
      farm.pesticide_per_acre_kg / HA_PER_ACRE
    ).toFixed(4);
  return Object.keys(overrides).length === 0 ? null : overrides;
}

function renderYieldFactors(inputs) {
  // Normalize each factor against a max to show contribution bars
  const rainfall = inputs.annual_rainfall_mm ?? 1100;
  const fert = inputs.fertilizer_per_ha_kg ?? 140;
  const pest = inputs.pesticide_per_ha_kg ?? 0.27;

  // Heuristic max values for bar fill (purely visual)
  const rainPct = Math.min(100, (rainfall / 2500) * 100);
  const fertPct = Math.min(100, (fert / 250) * 100);
  const pestPct = Math.min(100, (pest / 1.0) * 100);

  factorRainfallBar.style.width = `${rainPct}%`;
  factorRainfallVal.textContent = `${rainfall} mm`;
  factorFertBar.style.width = `${fertPct}%`;
  factorFertVal.textContent = `${fert} kg`;
  factorPestBar.style.width = `${pestPct}%`;
  factorPestVal.textContent = `${pest} kg`;
}

function renderYield(data, farm) {
  lastYieldData = data;
  const tph = data.predicted_yield_tons_per_hectare;
  if (tph == null) return;
  const tpa = tph * HA_PER_ACRE;
  yieldPerAcre.textContent = tpa.toFixed(1);
  yieldPerHectare.textContent = `${tph.toFixed(1)} tons/hectare`;

  if (farm.acres != null && farm.acres > 0) {
    yieldTotalTons.textContent = `~${(tpa * farm.acres).toFixed(1)}`;
    yieldTotalRow.classList.remove("hidden");
  } else {
    yieldTotalRow.classList.add("hidden");
  }

  const avgPerAcre = MAHARASHTRA_AVG_TPH * HA_PER_ACRE;
  const diffPct = ((tph - MAHARASHTRA_AVG_TPH) / MAHARASHTRA_AVG_TPH) * 100;
  let label =
    diffPct > 5
      ? "above average"
      : diffPct < -5
        ? "below average"
        : "near average";
  yieldComparison.textContent = `Maharashtra avg: ~${avgPerAcre.toFixed(1)} t/acre — your prediction is ${label}.`;

  const cvR2 = data.model_info?.cv_r2;
  yieldConfidence.textContent =
    cvR2 != null
      ? `Model accuracy: ~${Math.round(cvR2 * 100)}% (cross-validated)`
      : "";

  const usedFarm =
    data.inputs?.fertilizer_per_ha_kg !== 140 ||
    data.inputs?.pesticide_per_ha_kg !== 0.27;
  yieldInputsSource.textContent = usedFarm
    ? "Personalized for your farm:"
    : "Defaults used (set My Farm in Settings for personalized prediction):";

  yieldInputsList.innerHTML = "";
  Object.entries(data.inputs || {}).forEach(([key, value]) => {
  const li = document.createElement("li");
  li.innerHTML = `<span class="input-key">${formatInputKey(key)}</span><span class="input-val">${formatInputValue(key, value)}</span>`;
  yieldInputsList.appendChild(li);
});

  yieldNote.textContent = data.confidence_note || "";
  renderYieldFactors(data.inputs || {});
}

async function fetchAndRenderYield() {
  const url = getPiUrl();
  const farm = getFarm();
  setYieldStatus("loading", "Loading");
  const overrides = buildYieldOverrides(farm);

  try {
    const ctrl = new AbortController();
    const id = setTimeout(() => ctrl.abort(), 8000);
    const opts = overrides
      ? {
          method: "POST",
          headers: authHeaders({ "Content-Type": "application/json" }),
          body: JSON.stringify(overrides),
          signal: ctrl.signal,
        }
      : { headers: authHeaders(), signal: ctrl.signal };
    const r = await fetch(`${url}/predict-yield`, opts);
    clearTimeout(id);
    if (r.status === 401) {
      setYieldStatus("disconnected", "Token");
      return;
    }
    if (!r.ok) {
      setYieldStatus("disconnected", `HTTP ${r.status}`);
      return;
    }
    const data = await r.json();
    if (data.predicted_yield_tons_per_hectare == null) {
      setYieldStatus("disconnected", "Invalid");
      return;
    }
    renderYield(data, farm);
    setYieldStatus("connected", "Live");
  } catch (err) {
    setYieldStatus(
      "disconnected",
      err.name === "AbortError" ? "Timeout" : "Offline",
    );
  }
}

async function handleYieldRefresh() {
  refreshYieldBtn.classList.add("spinning");
  refreshYieldBtn.disabled = true;
  await fetchAndRenderYield();
  setTimeout(() => {
    refreshYieldBtn.classList.remove("spinning");
    refreshYieldBtn.disabled = false;
  }, 400);
}

// ============================================
// FARMER'S DIGEST
// ============================================
function getTodayDateKey() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function getCachedDigest() {
  return localStorage.getItem(`digest_${getTodayDateKey()}`) || null;
}

function saveDigestToCache(text) {
  const todayKey = `digest_${getTodayDateKey()}`;
  Object.keys(localStorage)
    .filter((k) => k.startsWith("digest_") && k !== todayKey)
    .forEach((k) => localStorage.removeItem(k));
  localStorage.setItem(todayKey, text);
}

async function fetchSensorForDigest() {
  const url = getPiUrl();
  try {
    const ctrl = new AbortController();
    const id = setTimeout(() => ctrl.abort(), 4000);
    const r = await fetch(`${url}/latest-readings`, {
      headers: authHeaders(),
      signal: ctrl.signal,
    });
    clearTimeout(id);
    if (!r.ok) return null;
    const d = await r.json();
    return d.nodes?.length ? d.nodes[0] : null;
  } catch {
    return null;
  }
}

async function fetchYieldForDigest() {
  const url = getPiUrl();
  const overrides = buildYieldOverrides(getFarm());
  try {
    const ctrl = new AbortController();
    const id = setTimeout(() => ctrl.abort(), 5000);
    const opts = overrides
      ? {
          method: "POST",
          headers: authHeaders({ "Content-Type": "application/json" }),
          body: JSON.stringify(overrides),
          signal: ctrl.signal,
        }
      : { headers: authHeaders(), signal: ctrl.signal };
    const r = await fetch(`${url}/predict-yield`, opts);
    clearTimeout(id);
    if (!r.ok) return null;
    return await r.json();
  } catch {
    return null;
  }
}

async function generateAndShowDigest() {
  if (digestShown) return;
  digestShown = true;

  const cached = getCachedDigest();
  if (cached) {
    addDigestMessage(cached);
    return;
  }

  const placeholder = addMessage("तुमचा दैनिक अहवाल तयार करत आहे... ⏳", "bot");
  placeholder.classList.add("digest-loading");

  try {
    const [sensor, yieldData] = await Promise.all([
      fetchSensorForDigest(),
      fetchYieldForDigest(),
    ]);

    const r = await fetch("/api/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        mode: "digest",
        farm: getFarm(),
        sensor,
        yield: yieldData,
      }),
    });

    if (!r.ok) {
      placeholder.remove();
      return;
    }

    const data = await r.json();

    if (!data.reply) {
      placeholder.remove();
      return;
    }

    placeholder.remove();
    saveDigestToCache(data.reply);
    addDigestMessage(data.reply);

  } catch {
    placeholder.remove();
  }
}

function addDigestMessage(text) {
  const div = document.createElement("div");
  div.className = "message message-bot message-digest";
  const header = document.createElement("div");
  header.className = "digest-header";
  header.textContent = "📋 आजचा अहवाल";
  const p = document.createElement("p");
  p.textContent = text;
  div.append(header, p);
  chatArea.appendChild(div);
  chatArea.scrollTop = chatArea.scrollHeight;
}

// ============================================
// CROP SELECTION FLOW
// ============================================
function showCropSelection() {
  cropSelection.classList.remove("hidden");
  appRoot.classList.add("hidden");
}

function hideCropSelectionAndShowApp() {
  cropSelection.classList.add("hidden");
  appRoot.classList.remove("hidden");
}

function setupCropSelection() {
  cropCards.forEach((card) => {
    card.addEventListener("click", () => {
      if (card.classList.contains("crop-card-soon")) {
        // Friendly explanation
        const name =
          card.querySelector(".crop-name-en")?.textContent || "this crop";
        alert(
          `${name} support is coming soon. The current demo focuses on Sugarcane only — but the architecture is designed to scale to any crop with crop-specific agronomy thresholds and ML training.`,
        );
        return;
      }
      cropCards.forEach((c) => c.classList.remove("crop-card-active"));
      card.classList.add("crop-card-active");
    });
  });

  cropContinueBtn.addEventListener("click", () => {
    setSelectedCrop("sugarcane");
    hideCropSelectionAndShowApp();
    bootMainApp();
  });

  if (changeCropBtn) {
    changeCropBtn.addEventListener("click", () => {
      showCropSelection();
    });
  }
}

// ============================================
// EVENT WIRING
// ============================================
if (themeToggleBtn) themeToggleBtn.addEventListener("click", toggleTheme);

sendBtn.addEventListener("click", handleSend);
textInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") handleSend();
});
micBtn.addEventListener("click", toggleMic);

if (cameraBtn) cameraBtn.addEventListener("click", () => cameraInput?.click());
if (cameraInput) cameraInput.addEventListener("change", handleImageUpload);

savePiBtn.addEventListener("click", handleSavePi);
testPiBtn.addEventListener("click", handleTestPi);
saveTokenBtn.addEventListener("click", handleSaveToken);
saveFarmBtn.addEventListener("click", handleSaveFarm);

refreshDashBtn.addEventListener("click", handleManualRefresh);
if (refreshWeatherBtn)
  refreshWeatherBtn.addEventListener("click", () => {
    refreshWeatherBtn.classList.add("spinning");
    refreshWeatherBtn.disabled = true;
    fetchAndRenderWeather().finally(() => {
      setTimeout(() => {
        refreshWeatherBtn.classList.remove("spinning");
        refreshWeatherBtn.disabled = false;
      }, 400);
    });
  });
refreshYieldBtn.addEventListener("click", handleYieldRefresh);

openValveBtn.addEventListener("click", () => actuateValve("open"));
closeValveBtn.addEventListener("click", () => actuateValve("close"));
refreshHistoryBtn.addEventListener("click", handleHistoryRefresh);
const clearHistoryBtn = document.getElementById("clear-history-btn");
if (clearHistoryBtn)
  clearHistoryBtn.addEventListener("click", handleClearHistory);
notifEnabledToggle.addEventListener("change", handleNotifEnabledToggle);

chipButtons.forEach((chip) => {
  chip.addEventListener("click", () => {
    const q = chip.dataset.question;
    if (!q) return;
    textInput.value = q;
    handleSend();
  });
});

// ============================================
// MAIN APP BOOT
// ============================================
function bootMainApp() {
  setupSpeechRecognition();
  preloadVoices();
  loadSettingsUI();
  loadNotifSettingsUI();
  generateAndShowDigest();
  if (getNotifEnabled()) startNotifPolling();
  fetchAndRenderDashboard().then(() => {
    // Set initial connection dot once we know
  });
  refreshIcons();
}

// ============================================
// INIT
// ============================================
setTheme(getTheme());
refreshIcons();
setupCropSelection();

// Splash for ~1.2s, then check if user has selected crop
setTimeout(() => {
  if (splashScreen) splashScreen.classList.add("fade-out");
  setTimeout(() => {
    if (splashScreen && splashScreen.parentNode)
      splashScreen.parentNode.removeChild(splashScreen);
    if (getSelectedCrop()) {
      hideCropSelectionAndShowApp();
      bootMainApp();
    } else {
      showCropSelection();
    }
    refreshIcons();
  }, 400);
}, SPLASH_DURATION_MS);

// Service worker
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker
      .register("/service-worker.js")
      .then((reg) => console.log("[SW] Registered:", reg.scope))
      .catch((err) => console.warn("[SW] Failed:", err));
  });
}

console.log("Farmer App v1.0 loaded ✓");
console.log("Pi URL:", getPiUrl());
console.log("Crop:", getSelectedCrop() || "(unselected)");
