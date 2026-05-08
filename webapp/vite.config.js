// vite.config.js
// Wires up our /api/chat.js file as a dev-time proxy endpoint.
// In production (Vercel), the same file in /api/ is auto-detected as a serverless function.

import { defineConfig } from "vite";
import { readFileSync } from "fs";
import { resolve } from "path";

export default defineConfig({
  server: {
    host: true, // expose on local network too
  },
  plugins: [
    {
      name: "dev-api-proxy",
      configureServer(server) {
        // Load .env.local manually so process.env has GEMINI_API_KEY
        try {
          const envPath = resolve(process.cwd(), ".env.local");
          const envContent = readFileSync(envPath, "utf-8");
          envContent.split("\n").forEach((line) => {
            const trimmed = line.trim();
            if (!trimmed || trimmed.startsWith("#")) return;
            const eqIdx = trimmed.indexOf("=");
            if (eqIdx === -1) return;
            const key = trimmed.slice(0, eqIdx).trim();
            const value = trimmed.slice(eqIdx + 1).trim();
            if (!process.env[key]) {
              process.env[key] = value;
            }
          });
          console.log("[dev-api-proxy] Loaded .env.local");
        } catch (e) {
          console.warn("[dev-api-proxy] Could not load .env.local:", e.message);
        }

        // Intercept /api/chat requests
        server.middlewares.use(async (req, res, next) => {
          if (req.url === "/api/chat" || req.url.startsWith("/api/chat?")) {
            try {
              const handlerModule = await server.ssrLoadModule("/api/chat.js");
              await handlerModule.default(req, res);
            } catch (err) {
              console.error("[dev-api-proxy] Handler error:", err);
              res.statusCode = 500;
              res.setHeader("Content-Type", "application/json");
              res.end(JSON.stringify({ error: "Handler crashed", message: err.message }));
            }
          } else {
            next();
          }
        });
      },
    },
  ],
});