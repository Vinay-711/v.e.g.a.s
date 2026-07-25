/**
 * V.E.G.A.S. Living AI Core Engine — 60fps HTML5 Canvas Engine
 * Renders animated J.A.R.V.I.S. concentric HUD rings, particle energy vortex,
 * orbital connection lines, gear-teeth arcs, audio waveform visualizer,
 * and Memory Knowledge Graph node canvas.
 */

class AICoreRenderer {
  constructor(canvasId) {
    this.canvas = document.getElementById(canvasId);
    if (!this.canvas) return;
    this.ctx = this.canvas.getContext('2d');
    
    // Core states: 'idle', 'listening', 'thinking', 'executing', 'alert'
    this.state = 'idle';
    this.audioLevel = 0.0;
    
    // Animation metrics
    this.angle1 = 0;
    this.angle2 = 0;
    this.angle3 = 0;
    this.particles = [];
    this.particleCount = 90;
    
    this.initCanvas();
    this.initParticles();
    window.addEventListener('resize', () => this.initCanvas());
    
    // Start 60fps render loop
    requestAnimationFrame((t) => this.render(t));
  }

  initCanvas() {
    const parent = this.canvas.parentElement;
    this.width = this.canvas.width = parent.clientWidth || 600;
    this.height = this.canvas.height = parent.clientHeight || 500;
    this.cx = this.width / 2;
    this.cy = this.height / 2;
    this.radius = Math.min(this.width, this.height) * 0.28;
  }

  initParticles() {
    this.particles = [];
    for (let i = 0; i < this.particleCount; i++) {
      this.particles.push({
        angle: Math.random() * Math.PI * 2,
        dist: Math.random() * 90 + 35,
        speed: (Math.random() * 0.02 + 0.005) * (Math.random() < 0.5 ? 1 : -1),
        size: Math.random() * 2.5 + 1,
        alpha: Math.random() * 0.8 + 0.2
      });
    }
  }

  setState(newState, audioLevel = 0.0) {
    this.state = newState.toLowerCase();
    this.audioLevel = audioLevel;
  }

  getStateColor() {
    switch (this.state) {
      case 'listening': return { primary: '#ffb700', secondary: 'rgba(255, 183, 0, 0.2)', text: 'LISTENING' };
      case 'thinking': return { primary: '#a855f7', secondary: 'rgba(168, 85, 247, 0.2)', text: 'THINKING' };
      case 'executing': return { primary: '#00f3ff', secondary: 'rgba(0, 243, 255, 0.25)', text: 'EXECUTING' };
      case 'alert': return { primary: '#ff6b00', secondary: 'rgba(255, 107, 0, 0.3)', text: 'CONFIRMATION REQUIRED' };
      default: return { primary: '#00f3ff', secondary: 'rgba(0, 243, 255, 0.15)', text: 'AI CORE ONLINE' };
    }
  }

  render(timestamp) {
    if (!this.ctx) return;
    if (document.hidden) {
      // Pause canvas rendering when tab is hidden to save GPU/CPU cycles
      requestAnimationFrame((t) => this.render(t));
      return;
    }
    this.ctx.clearRect(0, 0, this.width, this.height);

    const color = this.getStateColor();
    const speedMult = this.state === 'thinking' ? 2.5 : this.state === 'executing' ? 3.2 : 1.0;
    
    // Rotate ring angles
    this.angle1 += 0.008 * speedMult;
    this.angle2 -= 0.012 * speedMult;
    this.angle3 += 0.015 * speedMult;

    // Draw central energy glow
    this.drawCentralGlow(color);

    // Draw Gear-Teeth Arc Ring
    this.drawGearTeethRing(this.radius * 1.4, this.angle1, color.primary);

    // Draw Outer Concentric HUD Rings
    this.drawHudRing(this.radius * 1.25, this.angle1, color.primary, [0, Math.PI * 0.7, Math.PI * 1.2, Math.PI * 1.8]);
    this.drawHudRing(this.radius * 1.08, this.angle2, color.primary, [Math.PI * 0.3, Math.PI * 0.9, Math.PI * 1.5]);
    this.drawDottedRing(this.radius * 0.85, this.angle3, color.primary);

    // Draw Dynamic Particle Vortex & Connecting Lines
    this.drawParticles(color.primary, speedMult);

    // Draw Audio Waveform if active or listening
    if (this.state === 'listening' || this.audioLevel > 0) {
      this.drawAudioWave(color.primary);
    }

    // Draw HUD Crosshairs
    this.drawCrosshairs(color.primary);

    requestAnimationFrame((t) => this.render(t));
  }

  drawCentralGlow(color) {
    const ctx = this.ctx;
    const pulse = Math.sin(Date.now() * 0.003) * 8 + (this.audioLevel * 22);
    const rad = this.radius * 0.45 + pulse;

    const grad = ctx.createRadialGradient(this.cx, this.cy, 5, this.cx, this.cy, rad * 1.8);
    grad.addColorStop(0, color.primary);
    grad.addColorStop(0.5, color.secondary);
    grad.addColorStop(1, 'transparent');

    ctx.save();
    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.arc(this.cx, this.cy, rad * 1.8, 0, Math.PI * 2);
    ctx.fill();

    // Solid core orb
    ctx.fillStyle = color.primary;
    ctx.shadowColor = color.primary;
    ctx.shadowBlur = 25;
    ctx.beginPath();
    ctx.arc(this.cx, this.cy, rad * 0.5, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
  }

  drawGearTeethRing(radius, angle, strokeColor) {
    const ctx = this.ctx;
    ctx.save();
    ctx.translate(this.cx, this.cy);
    ctx.rotate(angle);
    ctx.strokeStyle = strokeColor;
    ctx.globalAlpha = 0.4;
    ctx.lineWidth = 2;

    const teeth = 24;
    const step = (Math.PI * 2) / teeth;
    ctx.beginPath();
    for (let i = 0; i < teeth; i++) {
      const a = i * step;
      const rInner = radius - 5;
      const rOuter = radius + 5;
      ctx.moveTo(Math.cos(a) * rInner, Math.sin(a) * rInner);
      ctx.lineTo(Math.cos(a) * rOuter, Math.sin(a) * rOuter);
    }
    ctx.stroke();
    ctx.restore();
  }

  drawHudRing(radius, angle, strokeColor, arcOffsets) {
    const ctx = this.ctx;
    ctx.save();
    ctx.translate(this.cx, this.cy);
    ctx.rotate(angle);
    ctx.strokeStyle = strokeColor;
    ctx.shadowColor = strokeColor;
    ctx.shadowBlur = 10;
    ctx.lineWidth = 2;

    arcOffsets.forEach(offset => {
      ctx.beginPath();
      ctx.arc(0, 0, radius, offset, offset + Math.PI * 0.4);
      ctx.stroke();
    });

    ctx.restore();
  }

  drawDottedRing(radius, angle, strokeColor) {
    const ctx = this.ctx;
    ctx.save();
    ctx.translate(this.cx, this.cy);
    ctx.rotate(angle);
    ctx.strokeStyle = strokeColor;
    ctx.setLineDash([4, 8]);
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.arc(0, 0, radius, 0, Math.PI * 2);
    ctx.stroke();
    ctx.restore();
  }

  drawParticles(color, speedMult) {
    const ctx = this.ctx;
    ctx.save();
    ctx.fillStyle = color;
    ctx.strokeStyle = color;
    ctx.shadowColor = color;
    ctx.shadowBlur = 8;

    const coords = [];

    this.particles.forEach(p => {
      p.angle += p.speed * speedMult;
      const x = this.cx + Math.cos(p.angle) * (this.radius * 0.9 + p.dist);
      const y = this.cy + Math.sin(p.angle) * (this.radius * 0.9 + p.dist);
      coords.push({ x, y });

      ctx.globalAlpha = p.alpha;
      ctx.beginPath();
      ctx.arc(x, y, p.size, 0, Math.PI * 2);
      ctx.fill();
    });

    // Draw particle connecting lines for neighboring particles
    ctx.lineWidth = 0.5;
    ctx.globalAlpha = 0.15;
    for (let i = 0; i < coords.length; i += 3) {
      for (let j = i + 1; j < coords.length; j += 4) {
        const dx = coords[i].x - coords[j].x;
        const dy = coords[i].y - coords[j].y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < 45) {
          ctx.beginPath();
          ctx.moveTo(coords[i].x, coords[i].y);
          ctx.lineTo(coords[j].x, coords[j].y);
          ctx.stroke();
        }
      }
    }

    ctx.restore();
  }

  drawAudioWave(color) {
    const ctx = this.ctx;
    ctx.save();
    ctx.strokeStyle = color;
    ctx.lineWidth = 2.5;
    ctx.shadowColor = color;
    ctx.shadowBlur = 12;

    ctx.beginPath();
    const waveWidth = this.radius * 1.6;
    const startX = this.cx - waveWidth / 2;
    
    for (let x = 0; x < waveWidth; x += 4) {
      const freq = x * 0.05 + Date.now() * 0.01;
      const amp = (Math.sin(freq) * 15 + Math.cos(freq * 1.5) * 10) * (0.3 + this.audioLevel * 1.5);
      const y = this.cy + amp;
      if (x === 0) ctx.moveTo(startX + x, y);
      else ctx.lineTo(startX + x, y);
    }
    ctx.stroke();
    ctx.restore();
  }

  drawCrosshairs(color) {
    const ctx = this.ctx;
    ctx.save();
    ctx.strokeStyle = color;
    ctx.globalAlpha = 0.3;
    ctx.lineWidth = 1;

    const len = 25;
    const gap = this.radius * 1.4;

    ctx.beginPath();
    ctx.moveTo(this.cx, this.cy - gap); ctx.lineTo(this.cx, this.cy - gap - len);
    ctx.moveTo(this.cx, this.cy + gap); ctx.lineTo(this.cx, this.cy + gap + len);
    ctx.moveTo(this.cx - gap, this.cy); ctx.lineTo(this.cx - gap - len, this.cy);
    ctx.moveTo(this.cx + gap, this.cy); ctx.lineTo(this.cx + gap + len, this.cy);
    ctx.stroke();

    ctx.restore();
  }
}

// Global instance
window.AICoreEngine = AICoreRenderer;
