// generate-icons.js
// One-time script to generate PNG icons for the PWA from inline SVG.

import sharp from "sharp";
import { mkdirSync, writeFileSync } from "fs";

const OUT_DIR = "./public/icons";
mkdirSync(OUT_DIR, { recursive: true });

// Standard rounded-corner icon (used by Chrome, iOS, etc.)
const standardSvg = `
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#2d6a4f"/>
      <stop offset="100%" stop-color="#40916c"/>
    </linearGradient>
  </defs>
  <rect width="512" height="512" rx="96" fill="url(#bg)"/>
  <text x="256" y="340" font-size="280" text-anchor="middle"
        font-family="Apple Color Emoji, Segoe UI Emoji, Noto Color Emoji, sans-serif">🌾</text>
</svg>
`;

// Maskable icon — full-bleed, smaller emoji (Android adds its own mask)
const maskableSvg = `
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#2d6a4f"/>
      <stop offset="100%" stop-color="#40916c"/>
    </linearGradient>
  </defs>
  <rect width="512" height="512" fill="url(#bg)"/>
  <text x="256" y="350" font-size="220" text-anchor="middle"
        font-family="Apple Color Emoji, Segoe UI Emoji, Noto Color Emoji, sans-serif">🌾</text>
</svg>
`;

async function makeIcon(svg, filename, size) {
  await sharp(Buffer.from(svg))
    .resize(size, size)
    .png()
    .toFile(`${OUT_DIR}/${filename}`);
  console.log(`✓ ${filename}`);
}

console.log("Generating PNG icons...\n");

await makeIcon(standardSvg, "icon-192.png", 192);
await makeIcon(standardSvg, "icon-512.png", 512);
await makeIcon(maskableSvg, "icon-maskable-512.png", 512);

console.log("\nDone. Icons saved to public/icons/");