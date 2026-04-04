import sharp from "sharp";
import { resolve, dirname } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const outPath = resolve(__dirname, "../public/og-image.png");

const svg = `
<svg width="1200" height="630" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#050509"/>
      <stop offset="50%" stop-color="#0a0a1a"/>
      <stop offset="100%" stop-color="#050509"/>
    </linearGradient>
    <linearGradient id="brand" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#7c3aed"/>
      <stop offset="100%" stop-color="#3b82f6"/>
    </linearGradient>
    <linearGradient id="glow" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#7c3aed" stop-opacity="0.15"/>
      <stop offset="100%" stop-color="#3b82f6" stop-opacity="0.05"/>
    </linearGradient>
  </defs>

  <!-- Background -->
  <rect width="1200" height="630" fill="url(#bg)"/>

  <!-- Ambient glow -->
  <ellipse cx="600" cy="315" rx="500" ry="300" fill="url(#glow)"/>

  <!-- Logo icon (scaled up) -->
  <g transform="translate(490, 140) scale(3)">
    <rect x="2" y="2" width="28" height="28" rx="6" fill="none" stroke="url(#brand)" stroke-width="2.5"/>
    <polygon points="12,8 12,24 24,16" fill="url(#brand)"/>
  </g>

  <!-- Brand name -->
  <text x="600" y="380" text-anchor="middle" font-family="Inter, system-ui, sans-serif" font-size="72" font-weight="700" fill="#f1f5f9">
    Clip<tspan fill="url(#brand)">IA</tspan>
  </text>

  <!-- Tagline -->
  <text x="600" y="440" text-anchor="middle" font-family="Inter, system-ui, sans-serif" font-size="28" font-weight="400" fill="#94a3b8">
    Crie videos curtos com IA
  </text>

  <!-- Subtle border -->
  <rect x="0" y="0" width="1200" height="630" fill="none" stroke="#7c3aed" stroke-opacity="0.2" stroke-width="1"/>
</svg>`;

await sharp(Buffer.from(svg))
  .resize(1200, 630)
  .png({ quality: 90 })
  .toFile(outPath);

console.log("✓ og-image.png (1200x630)");
