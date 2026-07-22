// Perlin Noise helper class
class PerlinNoise {
  constructor() {
    this.p = new Uint8Array(512);
    const permutation = new Uint8Array(256);
    for (let i = 0; i < 256; i++) permutation[i] = i;
    
    // Fisher-Yates shuffle
    for (let i = 255; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      const tmp = permutation[i];
      permutation[i] = permutation[j];
      permutation[j] = tmp;
    }
    
    for (let i = 0; i < 512; i++) {
      this.p[i] = permutation[i & 255];
    }
  }

  fade(t) { return t * t * t * (t * (t * 6 - 15) + 10); }
  lerp(t, a, b) { return a + t * (b - a); }
  grad(hash, x, y) {
    const h = hash & 7;
    const u = h < 4 ? x : y;
    const v = h < 4 ? y : x;
    return ((h & 1) ? -u : u) + ((h & 2) ? -2.0 * v : 2.0 * v);
  }

  noise(x, y) {
    const X = Math.floor(x) & 255;
    const Y = Math.floor(y) & 255;
    x -= Math.floor(x);
    y -= Math.floor(y);
    const u = this.fade(x);
    const v = this.fade(y);
    const A = this.p[X] + Y;
    const B = this.p[X + 1] + Y;
    
    return this.lerp(v,
      this.lerp(u, this.grad(this.p[A & 255], x, y), this.grad(this.p[B & 255], x - 1, y)),
      this.lerp(u, this.grad(this.p[A + 1 & 255], x, y - 1), this.grad(this.p[B + 1 & 255], x - 1, y - 1))
    );
  }
}

export default class ASCIIBackground {
  constructor(canvas) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    
    // Set canvas dimensions
    this.width = window.innerWidth;
    this.height = window.innerHeight;
    this.canvas.width = this.width;
    this.canvas.height = this.height;
    
    this.noiseGen = new PerlinNoise();
    this.time = 0;
    
    // Mouse coordinates (normalized and pixels)
    this.mouseX = this.width / 2;
    this.mouseY = this.height / 2;
    
    // Load config matching the requested spec
    this.config = {
      pfx: {
        bloom: { enabled: false, intensity: 25 },
        glitch: { enabled: false, intensity: 20 },
        filmDust: { enabled: false, intensity: 20 },
        halftone: { enabled: true, intensity: 30 },
        pixelate: { enabled: false, intensity: 15 },
        vignette: { enabled: false, intensity: 38 },
        chromatic: { enabled: false, intensity: 15 },
        filmGrain: { enabled: false, intensity: 30 },
        scanLines: { enabled: false, intensity: 40 }
      },
      mask: { enabled: false },
      tint: "#3ca6ff",
      bgBlur: 12,
      bgMode: "none",
      invert: false,
      lights: { points: [], enabled: false },
      charSet: "standard",
      density: 0,
      animated: true,
      blurType: "off",
      cellSize: 8,
      contrast: 150,
      coverage: 100,
      animSpeed: { enabled: true, intensity: 100 },
      animStyle: "shimmer",
      bgOpacity: 90,
      grayscale: 100,
      blurAmount: 35,
      brightness: 0,
      renderMode: "hatch",
      saturation: 0,
      styleBlend: "source-over",
      customChars: "",
      tintOpacity: 0,
      edgeEmphasis: 0,
      overlayBlend: "multiply",
      shaderSource: {
        hue: 0,
        blur: 0,
        seed: 1,
        warp: 37,
        zoom: 100,
        drift: 0,
        grain: 12,
        oklab: false,
        speed: 40,
        colors: [
          "#03120E",
          "#0E7C5A",
          "#7CE577",
          "#F4FFC7"
        ],
        detail: 50,
        paramA: 50,
        preset: "smoke",
        rotate: 0,
        offsetX: 0,
        offsetY: 0,
        animated: true,
        contrast: 53,
        vignette: 0,
        intensity: 47,
        brightness: 50,
        customCode: null,
        saturation: 50,
        cursorEffect: "spotlight",
        cursorRadius: 80, // slightly larger for nicer UI interaction
        motionReverse: false,
        mouseReactive: true,
        cursorStrength: 65
      },
      animIntensity: { enabled: true, intensity: 60 }
    };
    
    // Parse color hex codes to RGB
    this.colorsRgb = this.config.shaderSource.colors.map(hex => this.hexToRgb(hex));
    
    // Start animation loop
    this.isActive = true;
    this.animate = this.animate.bind(this);
    requestAnimationFrame(this.animate);
    
    // Listen to mousemove
    window.addEventListener('mousemove', (e) => {
      this.mouseX = e.clientX;
      this.mouseY = e.clientY;
    });
  }

  hexToRgb(hex) {
    const shorthandRegex = /^#?([a-f\d])([a-f\d])([a-f\d])$/i;
    const fullHex = hex.replace(shorthandRegex, (m, r, g, b) => r + r + g + g + b + b);
    const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(fullHex);
    return result ? {
      r: parseInt(result[1], 16),
      g: parseInt(result[2], 16),
      b: parseInt(result[3], 16)
    } : { r: 0, g: 0, b: 0 };
  }

  resize(width, height) {
    this.width = width;
    this.height = height;
    this.canvas.width = width;
    this.canvas.height = height;
  }

  getGradientColor(v) {
    const numColors = this.colorsRgb.length;
    if (numColors === 0) return { r: 0, g: 0, b: 0 };
    if (numColors === 1) return this.colorsRgb[0];
    
    const scaled = v * (numColors - 1);
    const index = Math.min(Math.floor(scaled), numColors - 2);
    const t = scaled - index;
    
    const cA = this.colorsRgb[index];
    const cB = this.colorsRgb[index + 1];
    
    return {
      r: cA.r + t * (cB.r - cA.r),
      g: cA.g + t * (cB.g - cA.g),
      b: cA.b + t * (cB.b - cA.b)
    };
  }

  adjustColor(color) {
    let { r, g, b } = color;
    const { brightness, contrast, saturation, grayscale } = this.config;
    
    // 1. Brightness (-100 to 100)
    const bOffset = (brightness / 100) * 255;
    r = Math.max(0, Math.min(255, r + bOffset));
    g = Math.max(0, Math.min(255, g + bOffset));
    b = Math.max(0, Math.min(255, b + bOffset));
    
    // 2. Contrast (factor: e.g. 150 -> 1.5)
    const cFactor = contrast / 100;
    r = Math.max(0, Math.min(255, (r - 128) * cFactor + 128));
    g = Math.max(0, Math.min(255, (g - 128) * cFactor + 128));
    b = Math.max(0, Math.min(255, (b - 128) * cFactor + 128));
    
    // 3. Luminance (Rec. 601 grayscale coefficients)
    const gray = 0.299 * r + 0.587 * g + 0.114 * b;
    
    // 4. Grayscale blend
    if (grayscale > 0) {
      const gFactor = grayscale / 100;
      r = r + (gray - r) * gFactor;
      g = g + (gray - g) * gFactor;
      b = b + (gray - b) * gFactor;
    }
    
    // 5. Saturation blend
    if (saturation !== 100) {
      const sFactor = saturation / 100;
      r = gray + (r - gray) * sFactor;
      g = gray + (g - gray) * sFactor;
      b = gray + (b - gray) * sFactor;
    }
    
    return {
      r: Math.round(r),
      g: Math.round(g),
      b: Math.round(b),
      luminance: Math.round(gray)
    };
  }

  animate() {
    if (!this.isActive) return;
    
    this.render();
    requestAnimationFrame(this.animate);
  }

  render() {
    const {
      cellSize,
      animated,
      animSpeed,
      animStyle,
      animIntensity,
      shaderSource,
      pfx,
      invert
    } = this.config;
    
    // Clear canvas
    this.ctx.fillStyle = '#05070f';
    this.ctx.fillRect(0, 0, this.width, this.height);
    
    // Calculate animation time step
    if (animated && animSpeed.enabled) {
      const speedMult = shaderSource.speed * 0.02 * (animSpeed.intensity / 100);
      this.time += 0.01 * speedMult;
    }
    
    const cellW = cellSize;
    const cellH = cellSize;
    const cols = Math.ceil(this.width / cellW);
    const rows = Math.ceil(this.height / cellH);
    
    const warp = shaderSource.warp * 0.01;
    const zoom = shaderSource.zoom * 0.005;
    const intensity = shaderSource.intensity * 0.02;
    
    // 1. Grid Sampling & Hatch rendering loop
    for (let y = 0; y < rows; y++) {
      for (let x = 0; x < cols; x++) {
        const px = x * cellW;
        const py = y * cellH;
        
        // Normalize coordinates for noise grid
        const nx = x * zoom;
        const ny = y * zoom;
        
        // Double domain warp formula for smoke-fluid pattern
        const qx = this.noiseGen.noise(nx + this.time * 0.15, ny + this.time * 0.1) * warp;
        const qy = this.noiseGen.noise(nx - this.time * 0.08, ny + this.time * 0.12) * warp;
        
        const rx = this.noiseGen.noise(nx + qx + this.time * 0.05, ny + qy) * warp;
        const ry = this.noiseGen.noise(nx + qx, ny + qy + this.time * 0.08) * warp;
        
        let val = this.noiseGen.noise(nx + rx, ny + ry);
        val = (val + 1) * 0.5 * intensity; // normalized 0..1 scale
        val = Math.max(0, Math.min(1.0, val));
        
        // Shimmer animation style adds localized sparkle variance
        if (animated && animIntensity.enabled && animStyle === 'shimmer') {
          const shim = Math.sin(this.time * 8 + x * 0.4 + y * 0.3) * 0.08 * (animIntensity.intensity / 100);
          val = Math.max(0, Math.min(1.0, val + shim));
        }
        
        // Mouse Reactive Spotlight Glow
        if (shaderSource.mouseReactive) {
          const cx = px + cellW / 2;
          const cy = py + cellH / 2;
          const dist = Math.hypot(cx - this.mouseX, cy - this.mouseY);
          const rad = shaderSource.cursorRadius * 2.2;
          if (dist < rad) {
            const factor = (1.0 - dist / rad) * (shaderSource.cursorStrength / 100);
            val = Math.min(1.0, val + factor * 0.45);
          }
        }
        
        // Retrieve and adjust gradient colors
        const rawColor = this.getGradientColor(val);
        const adjusted = this.adjustColor(rawColor);
        
        // Render cell using selected primitive mode
        const cellLuminance = invert ? 255 - adjusted.luminance : adjusted.luminance;
        
        if (this.config.renderMode === "hatch") {
          this.drawHatchCell(px, py, cellW, adjusted, cellLuminance);
        } else {
          // Fallback simple pixel solid render for none-hatch modes
          this.ctx.fillStyle = `rgb(${adjusted.r}, ${adjusted.g}, ${adjusted.b})`;
          this.ctx.fillRect(px, py, cellW, cellH);
        }
      }
    }
    
    // 2. Post-effects layer: Halftone
    if (pfx.halftone && pfx.halftone.enabled) {
      this.drawHalftoneOverlay(cols, rows, cellW, cellH, pfx.halftone.intensity / 100);
    }
  }

  drawHatchCell(x, y, size, rgb, luminance) {
    const L = luminance / 255;
    if (L < 0.12) return; // Dark threshold - draw nothing
    
    this.ctx.strokeStyle = `rgba(${rgb.r}, ${rgb.g}, ${rgb.b}, ${0.15 + L * 0.85})`;
    this.ctx.lineWidth = 0.9;
    
    // Hand-drawn organic line wobble jitter
    const j = () => (Math.random() - 0.5) * 0.65;
    
    // Diagonal 1: Top-Left to Bottom-Right
    if (L > 0.12) {
      this.ctx.beginPath();
      this.ctx.moveTo(x + j(), y + j());
      this.ctx.lineTo(x + size + j(), y + size + j());
      this.ctx.stroke();
    }
    
    // Diagonal 2: Top-Right to Bottom-Left
    if (L > 0.38) {
      this.ctx.beginPath();
      this.ctx.moveTo(x + size + j(), y + j());
      this.ctx.lineTo(x + j(), y + size + j());
      this.ctx.stroke();
    }
    
    // Horizontal Cross
    if (L > 0.65) {
      this.ctx.beginPath();
      this.ctx.moveTo(x + j(), y + size / 2 + j());
      this.ctx.lineTo(x + size + j(), y + size / 2 + j());
      this.ctx.stroke();
    }
    
    // Vertical Cross
    if (L > 0.82) {
      this.ctx.beginPath();
      this.ctx.moveTo(x + size / 2 + j(), y + j());
      this.ctx.lineTo(x + size / 2 + j(), y + size + j());
      this.ctx.stroke();
    }
  }

  drawHalftoneOverlay(cols, rows, cellW, cellH, intensity) {
    this.ctx.fillStyle = `rgba(255, 255, 255, ${intensity * 0.12})`; // theme white halftone glow
    
    for (let y = 0; y < rows; y += 2) {
      for (let x = 0; x < cols; x += 2) {
        const px = x * cellW + cellW / 2;
        const py = y * cellH + cellH / 2;
        
        // Draw halftone pattern dot grid
        this.ctx.beginPath();
        this.ctx.arc(px, py, cellW * 0.3, 0, Math.PI * 2);
        this.ctx.fill();
      }
    }
  }
}
