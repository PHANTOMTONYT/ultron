import * as THREE from 'https://esm.sh/three@0.160.0';

class ParticleSystem {
  constructor(scene, count = 500) {
    this.scene = scene;
    this.count = count;
    this.particles = [];
    this.geometry = new THREE.BufferGeometry();
    
    // Create random orbit parameters for each particle
    const positions = new Float32Array(count * 3);
    const colors = new Float32Array(count * 3);
    
    for (let i = 0; i < count; i++) {
      // Random orbit radius, angle, speed
      const radius = 1.0 + Math.random() * 0.8;
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos((Math.random() * 2) - 1); // spherical coordinates
      const speed = 0.5 + Math.random() * 1.5;
      const size = 0.01 + Math.random() * 0.03;
      
      this.particles.push({
        radius,
        theta,
        phi,
        speed,
        size,
        baseRadius: radius,
        wobbleSpeed: 1 + Math.random() * 3,
        wobbleAmount: 0.1 + Math.random() * 0.1
      });
      
      // Initial positions
      const x = radius * Math.sin(phi) * Math.cos(theta);
      const y = radius * Math.sin(phi) * Math.sin(theta);
      const z = radius * Math.cos(phi);
      
      positions[i * 3] = x;
      positions[i * 3 + 1] = y;
      positions[i * 3 + 2] = z;
      
      // Colors (default to cyan/teal energy colors)
      colors[i * 3] = 0.0;
      colors[i * 3 + 1] = 0.95;
      colors[i * 3 + 2] = 1.0;
    }
    
    this.geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    this.geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
    
    // Use a basic points material with vertex colors and a circular texture
    // Create a procedural circle texture to make particles look soft and glowing
    const canvas = document.createElement('canvas');
    canvas.width = 16;
    canvas.height = 16;
    const ctx = canvas.getContext('2d');
    const grad = ctx.createRadialGradient(8, 8, 0, 8, 8, 8);
    grad.addColorStop(0, 'rgba(255, 255, 255, 1)');
    grad.addColorStop(1, 'rgba(255, 255, 255, 0)');
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, 16, 16);
    
    const texture = new THREE.CanvasTexture(canvas);
    
    this.material = new THREE.PointsMaterial({
      size: 0.06,
      map: texture,
      vertexColors: true,
      transparent: true,
      blending: THREE.AdditiveBlending,
      depthWrite: false
    });
    
    this.points = new THREE.Points(this.geometry, this.material);
    scene.add(this.points);
  }
  
  update(time, state, emotionIntensity = 0.5) {
    const positionAttr = this.geometry.attributes.position;
    const colorAttr = this.geometry.attributes.color;
    
    // Dynamic physics based on visual state
    let speedMult = 1.0;
    let radiusMult = 1.0;
    let colorTheme = { r: 0.0, g: 0.9, b: 1.0 }; // Default teal/cyan
    
    switch (state) {
      case 'listening':
        speedMult = 0.8;
        radiusMult = 0.7; // particles orbit tighter
        colorTheme = { r: 0.5, g: 0.0, b: 1.0 }; // purple
        break;
      case 'thinking':
        speedMult = 0.4;
        radiusMult = 0.6; // orbit very tight and slow
        colorTheme = { r: 1.0, g: 0.3, b: 0.1 }; // orange/amber
        break;
      case 'speaking':
        speedMult = 2.0; // accelerate
        radiusMult = 1.0 + 0.2 * Math.sin(time * 10); // expand and contract in waves
        colorTheme = { r: 0.0, g: 0.6, b: 1.0 }; // bright electric blue
        break;
      case 'happy':
      case 'celebrating':
        speedMult = 3.0; // super fast
        radiusMult = 1.2 + 0.4 * Math.sin(time * 15); // expand out
        colorTheme = { r: 1.0, g: 0.8, b: 0.2 }; // golden/yellow
        break;
      case 'confused':
        speedMult = 1.5;
        radiusMult = 1.0;
        colorTheme = { r: 0.5, g: 1.0, b: 0.2 }; // acid green
        break;
      case 'sleeping':
        speedMult = 0.1; // barely moving
        radiusMult = 0.9;
        colorTheme = { r: 0.2, g: 0.2, b: 0.6 }; // dim dark blue
        break;
      default: // idle
        speedMult = 1.0;
        radiusMult = 1.0;
        colorTheme = { r: 0.0, g: 0.95, b: 1.0 }; // teal/cyan
    }
    
    for (let i = 0; i < this.count; i++) {
      const p = this.particles[i];
      
      // Update the orbit angle
      p.theta += p.speed * 0.01 * speedMult;
      
      // In confused state, add some noise to phi (irregular paths)
      if (state === 'confused') {
        p.phi += (Math.random() - 0.5) * 0.05;
      }
      
      // Calculate active radius with sinusoidal wobble
      const wobble = Math.sin(time * p.wobbleSpeed) * p.wobbleAmount;
      const currentRadius = (p.baseRadius * radiusMult) + wobble;
      
      // Convert spherical back to cartesian positions
      const x = currentRadius * Math.sin(p.phi) * Math.cos(p.theta);
      const y = currentRadius * Math.sin(p.phi) * Math.sin(p.theta);
      const z = currentRadius * Math.cos(p.phi);
      
      positionAttr.setXYZ(i, x, y, z);
      
      // Smoothly transition colors
      const r = colorAttr.getX(i);
      const g = colorAttr.getY(i);
      const b = colorAttr.getZ(i);
      
      const lerpSpeed = 0.05;
      colorAttr.setXYZ(
        i, 
        r + (colorTheme.r - r) * lerpSpeed,
        g + (colorTheme.g - g) * lerpSpeed,
        b + (colorTheme.b - b) * lerpSpeed
      );
    }
    
    positionAttr.needsUpdate = true;
    colorAttr.needsUpdate = true;
  }
}

export default ParticleSystem;
