// api/chat.js
// Gemini proxy with three modes:
//   "chat"     — farmer asks a question (default)
//   "digest"   — proactive morning report
//   "diagnose" — image analysis (Gemini Vision)

export default async function handler(req, res) {
  if (req.method !== "POST") {
    res.statusCode = 405;
    res.setHeader("Content-Type", "application/json");
    res.end(JSON.stringify({ error: "Method not allowed" }));
    return;
  }

  // Read body
  let body = "";
  try {
    if (req.body) body = typeof req.body === "string" ? req.body : JSON.stringify(req.body);
    else body = await new Promise((resolve, reject) => {
      let data = "";
      req.on("data", (c) => (data += c));
      req.on("end", () => resolve(data));
      req.on("error", reject);
    });
  } catch {
    res.statusCode = 400;
    res.setHeader("Content-Type", "application/json");
    res.end(JSON.stringify({ error: "Could not read body" }));
    return;
  }

  let payload;
  try { payload = typeof body === "string" ? JSON.parse(body) : body; }
  catch {
    res.statusCode = 400;
    res.setHeader("Content-Type", "application/json");
    res.end(JSON.stringify({ error: "Invalid JSON" }));
    return;
  }

  const userMessage = payload.message;
  const farm = payload.farm || {};
  const sensor = payload.sensor || null;
  const mode = payload.mode || "chat";
  const yieldData = payload.yield || null;
  const imageBase64 = payload.image_base64 || null;
  const imageMime = payload.image_mime || "image/jpeg";

  // Validation per mode
  if (mode === "chat" && (!userMessage || typeof userMessage !== "string")) {
    res.statusCode = 400;
    res.setHeader("Content-Type", "application/json");
    res.end(JSON.stringify({ error: "Missing 'message'" }));
    return;
  }
  if (mode === "diagnose" && !imageBase64) {
    res.statusCode = 400;
    res.setHeader("Content-Type", "application/json");
    res.end(JSON.stringify({ error: "Missing 'image_base64' for diagnose mode" }));
    return;
  }

  // Detect language (chat mode only)
  function detectUserLang(text) {
    if (!text) return "marathi";
    const dev = (text.match(/[\u0900-\u097F]/g) || []).length;
    const lat = (text.match(/[a-zA-Z]/g) || []).length;
    if (lat > dev * 2) return "english";
    const hi = ["है", "हैं", "क्या", "कैसे", "मुझे", "आपकी", "आपको", "मेरी", "मेरा", "नहीं", "रहा", "रही"];
    const mr = ["आहे", "आहेत", "कसे", "काय", "मला", "तुमच्या", "तुम्ही", "माझे", "माझा", "नाही", "होत"];
    let h = 0, m = 0;
    hi.forEach((w) => { if (text.includes(w)) h++; });
    mr.forEach((w) => { if (text.includes(w)) m++; });
    return h > m ? "hindi" : "marathi";
  }
  const userLang = mode === "chat" ? detectUserLang(userMessage) : "marathi";

  const apiKey = process.env.GEMINI_API_KEY;
  if (!apiKey) {
    res.statusCode = 500;
    res.setHeader("Content-Type", "application/json");
    res.end(JSON.stringify({ error: "Missing API key" }));
    return;
  }

  // Use full Flash for vision (Lite may not support images), Lite for text
  const visionModel = "gemini-2.5-flash";
  const textModel = "gemini-2.5-flash-lite";
  const modelToUse = mode === "diagnose" ? visionModel : textModel;
  const geminiUrl = `https://generativelanguage.googleapis.com/v1beta/models/${modelToUse}:generateContent?key=${apiKey}`;

  // Build context (farm + sensor)
  const farmLines = [];
  if (farm.acres != null) farmLines.push(`- शेताचे क्षेत्रफळ: ${farm.acres} एकर`);
  if (farm.soil_type) {
    const soilNames = {
      black_cotton: "काळी माती (Black cotton)", red: "तांबडी माती", loamy: "पोयट्याची माती",
      sandy: "वालुकामय", alluvial: "गाळाची माती", other: "इतर",
    };
    farmLines.push(`- मातीचा प्रकार: ${soilNames[farm.soil_type] || farm.soil_type}`);
  }
  if (farm.irrigation) {
    const irrNames = { drip: "ठिबक", flood: "पाट", sprinkler: "तुषार", canal: "कालवा", rainfed: "पावसावर" };
    farmLines.push(`- सिंचन: ${irrNames[farm.irrigation] || farm.irrigation}`);
  }
  if (farm.variety) farmLines.push(`- वाण: ${farm.variety}`);
  if (farm.planting_date) {
    farmLines.push(`- लागवडीची तारीख: ${farm.planting_date}`);
    const plantedMs = new Date(farm.planting_date).getTime();
    if (!isNaN(plantedMs) && plantedMs <= Date.now()) {
      const days = Math.floor((Date.now() - plantedMs) / 86400000);
      farmLines.push(`- लागवडीनंतरचे दिवस: ${days} दिवस (~${Math.floor(days / 30)} महिने)`);
    }
  }
  if (farm.fertilizer_per_acre_kg != null) farmLines.push(`- खत: ${farm.fertilizer_per_acre_kg} किलो/एकर`);
  if (farm.pesticide_per_acre_kg != null) farmLines.push(`- औषध: ${farm.pesticide_per_acre_kg} किलो/एकर`);

  const sensorLines = [];
  if (sensor) {
    const ageMin = Math.floor((Date.now() / 1000 - sensor.timestamp) / 60);
    const ageDesc = ageMin < 60 ? `${ageMin} मिनिटांपूर्वीचे` : ageMin < 1440 ? `${Math.floor(ageMin / 60)} तासांपूर्वीचे` : `${Math.floor(ageMin / 1440)} दिवसांपूर्वीचे`;
    if (sensor.soil_moisture != null) sensorLines.push(`- जमिनीतील ओलावा: ${sensor.soil_moisture}% (VWC)`);
    if (sensor.soil_temperature != null) sensorLines.push(`- जमिनीचे तापमान: ${sensor.soil_temperature}°C`);
    if (sensor.air_temperature != null) sensorLines.push(`- हवेचे तापमान: ${sensor.air_temperature}°C`);
    if (sensor.humidity != null) sensorLines.push(`- आर्द्रता: ${sensor.humidity}%`);
    sensorLines.unshift(`थेट सेन्सर डेटा (${ageDesc}):`);
    const isHistorical = (sensor.firmware_version || "").includes("historical");
    if (isHistorical || ageMin > 60) sensorLines.push(`(टीप: डेटा थोडा जुना आहे)`);
  }

  const todayStr = new Date().toLocaleDateString("en-CA");
  let contextBlock = `\n\n=== आजची तारीख: ${todayStr} ===\n`;
  if (farmLines.length || sensorLines.length) {
    contextBlock += `\n=== शेताची माहिती ===\n`;
    if (farmLines.length) contextBlock += `\n${farmLines.join("\n")}\n`;
    if (sensorLines.length) contextBlock += `\n${sensorLines.join("\n")}\n`;
    contextBlock += `\nया डेटाच्या आधारे विशिष्ट सल्ला द्या.\n=== माहिती संपली ===\n`;
  }

  // ============================================
  // PROMPTS PER MODE
  // ============================================
  const chatSystemPrompt = `तुम्ही "शेतकरी मित्र" आहात — महाराष्ट्रातील ऊस शेतकऱ्यांचे साथीदार.

कठोर नियम:
1. उत्तर 3-5 वाक्ये max. शेतकरी फोनवर ऐकतो आहे.
2. साधी मराठी. इंग्रजी कंस लावू नका.
3. Markdown नको — फक्त साधा मजकूर.
4. प्रश्नाचे थेट उत्तर द्या.
5. भाषेचा नियम: Devanagari script (मराठी/हिंदी) → reply in same. Latin script (English) → reply in English.
6. सेन्सर डेटा असेल तर त्याचा वापर करून विशिष्ट सल्ला द्या.

उदाहरणे:
प्रश्न: "ऊसाची पाने पिवळी होत आहेत."
उत्तर: "नायट्रोजनची कमतरता वाटते. एकरी 50 किलो युरिया द्या आणि पाणी भरा."

प्रश्न: "Should I water today?" (soil moisture 22%)
उत्तर: "Soil moisture is only 22% — that's low. Water today. Run drip 4-5 hours."

${contextBlock}`;

  const digestSystemPrompt = `तुम्ही "शेतकरी मित्र" आहात.
तुमचे कार्य: सकाळी एक लहान "आजचा अहवाल" द्या.

नियम:
1. फक्त 3-4 वाक्ये, 50 शब्दांपेक्षा कमी.
2. साधी मराठी. Markdown नको.
3. क्रम: नमस्कार + आजची स्थिती (ओलावा, हवामान) → आज पाणी द्यायचे का? → पुढच्या 2-3 दिवसांचा सल्ला.
4. "नमस्कार!" ने सुरुवात करा.

उदाहरण: "नमस्कार! आज तुमच्या शेताची स्थिती चांगली आहे. जमिनीत 38% ओलावा आहे. आज पाणी देण्याची गरज नाही. 2-3 दिवसांत हवामान कोरडे राहील — सोमवारी पाणी देण्याची तयारी ठेवा."

${contextBlock}
${yieldData?.predicted_yield_tons_per_hectare ? `अंदाजित उत्पादन: ${yieldData.predicted_yield_tons_per_hectare} टन/हेक्टर` : ""}

आता वरील डेटा वापरून आजचा अहवाल तयार करा.`;

  const diagnoseSystemPrompt = `तुम्ही "शेतकरी मित्र" आहात — ऊस पिकाचे डॉक्टर.

शेतकऱ्याने तुम्हाला त्यांच्या ऊस शेताचा फोटो पाठवला आहे. तुमचे कार्य:
1. फोटो काळजीपूर्वक पहा.
2. ऊस पिक निरोगी आहे की काही समस्या आहे ते सांगा.
3. समस्या असेल तर: कोणती समस्या (रोग, कीड, कमतरता)? आणि उपाय काय? (specific कृती).
4. निरोगी असेल तर: सकारात्मक सांगा आणि पुढची काळजी.

कठोर नियम:
- फक्त 4-5 वाक्ये, साधी मराठी.
- Markdown नको.
- "मला फोटोत दिसत आहे..." अशी सुरुवात करा.
- फोटो ऊस नसेल तर: "हा ऊसाचा फोटो वाटत नाही — कृपया ऊसाच्या पानांचा किंवा शेताचा फोटो पाठवा" असे सांगा.

${contextBlock}`;

  // ============================================
  // BUILD GEMINI REQUEST
  // ============================================
  let finalSystemPrompt;
  let userParts;

  if (mode === "diagnose") {
    finalSystemPrompt = diagnoseSystemPrompt;
    userParts = [
      { inline_data: { mime_type: imageMime, data: imageBase64 } },
      { text: "हा माझ्या ऊस शेताचा फोटो आहे. कृपया तपासून सांगा — पीक निरोगी आहे का? काही समस्या आहे का? उपाय काय?" },
    ];
  } else if (mode === "digest") {
    finalSystemPrompt = digestSystemPrompt;
    userParts = [{ text: "आजचा शेतीचा अहवाल द्या." }];
  } else {
    finalSystemPrompt = chatSystemPrompt;
    let langDirective;
    if (userLang === "english") langDirective = "Reply ONLY in English. 3-5 sentences.\n\nFarmer's question: ";
    else if (userLang === "hindi") langDirective = "केवल हिंदी में उत्तर दें। 3-5 वाक्य।\n\nप्रश्न: ";
    else langDirective = "फक्त मराठीत उत्तर द्या. 3-5 वाक्ये.\n\nप्रश्न: ";
    userParts = [{ text: langDirective + userMessage }];
  }

  try {
    const geminiRes = await fetch(geminiUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        contents: [{ role: "user", parts: userParts }],
        systemInstruction: { parts: [{ text: finalSystemPrompt }] },
        generationConfig: {
          temperature: mode === "digest" ? 0.5 : 0.7,
          maxOutputTokens: mode === "digest" ? 600 : mode === "diagnose" ? 1500 : 2000,
        },
      }),
    });

    const geminiData = await geminiRes.json();
    if (!geminiRes.ok) {
      console.error("Gemini error:", geminiData);
      res.statusCode = geminiRes.status;
      res.setHeader("Content-Type", "application/json");
      res.end(JSON.stringify({ error: "Gemini API error", details: geminiData }));
      return;
    }
    const reply = geminiData?.candidates?.[0]?.content?.parts?.[0]?.text || "(empty)";
    res.statusCode = 200;
    res.setHeader("Content-Type", "application/json");
    res.end(JSON.stringify({ reply }));
  } catch (err) {
    console.error("Proxy error:", err);
    res.statusCode = 500;
    res.setHeader("Content-Type", "application/json");
    res.end(JSON.stringify({ error: "Proxy error", message: err.message }));
  }
}