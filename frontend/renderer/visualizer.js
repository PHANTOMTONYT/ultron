import * as THREE from 'https://esm.sh/three@0.160.0';
import ParticleSystem from '../particles/particle_system.js';

async function loadShader(relativePath) {
  const response = await fetch(new URL(relativePath, import.meta.url));
  return response.text();
}

class CompanionVisualizer {
  constructor(canvasElement) {
    this.canvas = canvasElement;
    this.width = canvasElement.clientWidth;
    this.height = canvasElement.clientHeight;
    
    // Core parameters for state machine
    this.currentState = 'idle';
    this.emotionIntensity = 0.5;
    this.speechAmplitude = 0.0;
    this.time = 0;
    
    // Theme Colors
    this.themes = {
      idle: {
        color1: new THREE.Color('#00f2fe'),
        color2: new THREE.Color('#4facfe'),
        glow: new THREE.Color('#00f2fe'),
        glowIntensity: 1.2,
        noiseStrength: 0.15,
        noiseFreq: 1.5
      },
      listening: {
        color1: new THREE.Color('#7f00ff'),
        color2: new THREE.Color('#e100ff'),
        glow: new THREE.Color('#e100ff'),
        glowIntensity: 2.0,
        noiseStrength: 0.22,
        noiseFreq: 2.0
      },
      thinking: {
        color1: new THREE.Color('#ff0844'),
        color2: new THREE.Color('#ffb199'),
        glow: new THREE.Color('#ff0844'),
        glowIntensity: 1.5,
        noiseStrength: 0.35, // large slow deformation
        noiseFreq: 0.8
      },
      speaking: {
        color1: new THREE.Color('#00c6ff'),
        color2: new THREE.Color('#0072ff'),
        glow: new THREE.Color('#00c6ff'),
        glowIntensity: 2.5,
        noiseStrength: 0.2,
        noiseFreq: 2.5
      },
      happy: {
        color1: new THREE.Color('#f6d365'),
        color2: new THREE.Color('#fda085'),
        glow: new THREE.Color('#f6d365'),
        glowIntensity: 2.2,
        noiseStrength: 0.3,
        noiseFreq: 3.0
      },
      celebrating: {
        color1: new THREE.Color('#ff0844'),
        color2: new THREE.Color('#fda085'),
        glow: new THREE.Color('#f6d365'),
        glowIntensity: 3.0,
        noiseStrength: 0.45,
        noiseFreq: 4.0
      },
      confused: {
        color1: new THREE.Color('#96fbc4'),
        color2: new THREE.Color('#f9f586'),
        glow: new THREE.Color('#96fbc4'),
        glowIntensity: 1.8,
        noiseStrength: 0.4,
        noiseFreq: 5.0 // Glitchy, highly frequent distortion
      },
      sleeping: {
        color1: new THREE.Color('#30cfd0'),
        color2: new THREE.Color('#330867'),
        glow: new THREE.Color('#330867'),
        glowIntensity: 0.4,
        noiseStrength: 0.05, // very minimal breathing
        noiseFreq: 0.5
      }
    };
    
    this.activeColors = {
      color1: this.themes.idle.color1.clone(),
      color2: this.themes.idle.color2.clone(),
      glow: this.themes.idle.glow.clone(),
      glowIntensity: this.themes.idle.glowIntensity,
      noiseStrength: this.themes.idle.noiseStrength,
      noiseFreq: this.themes.idle.noiseFreq
    };
    
    this.ready = this.init();
  }

  async init() {
    this.initScene();
    await this.initObjects();
    this.animate();
  }

  initScene() {
    this.scene = new THREE.Scene();
    
    // Camera settings
    this.camera = new THREE.PerspectiveCamera(45, this.width / this.height, 0.1, 100);
    this.camera.position.z = 4.5;
    
    // Renderer settings
    this.renderer = new THREE.WebGLRenderer({
      canvas: this.canvas,
      alpha: true,
      antialias: true,
      powerPreference: "high-performance"
    });
    this.renderer.setSize(this.width, this.height);
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    
    // Lights (Additive glow)
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.4);
    this.scene.add(ambientLight);
    
    const pointLight = new THREE.PointLight(0x00f2fe, 2, 10);
    pointLight.position.set(0, 0, 0);
    this.scene.add(pointLight);
    this.pointLight = pointLight;
  }
  
  async initObjects() {
    const [vertexShaderCode, fragmentShaderCode] = await Promise.all([
      loadShader('../shaders/sphere.vertex.glsl'),
      loadShader('../shaders/sphere.fragment.glsl')
    ]);

    // 1. Core Sphere (deformed via simplex noise shader)
    this.sphereGeometry = new THREE.IcosahedronGeometry(0.85, 32); // High resolution for smooth noise

    this.sphereUniforms = {
      uTime: { value: 0 },
      uNoiseStrength: { value: this.activeColors.noiseStrength },
      uNoiseFrequency: { value: this.activeColors.noiseFreq },
      uAmplitude: { value: 0.0 },
      uColor1: { value: this.activeColors.color1 },
      uColor2: { value: this.activeColors.color2 },
      uGlowColor: { value: this.activeColors.glow },
      uGlowIntensity: { value: this.activeColors.glowIntensity }
    };
    
    this.sphereMaterial = new THREE.ShaderMaterial({
      vertexShader: vertexShaderCode,
      fragmentShader: fragmentShaderCode,
      uniforms: this.sphereUniforms,
      transparent: true,
      blending: THREE.NormalBlending,
      side: THREE.DoubleSide,
      depthWrite: true
    });
    
    this.sphereMesh = new THREE.Mesh(this.sphereGeometry, this.sphereMaterial);
    this.scene.add(this.sphereMesh);
    
    // 2. Concentric Orbiting Rings
    this.rings = [];
    const ringCount = 3;
    const ringMaterials = [
      new THREE.LineBasicMaterial({ color: 0x00f2fe, transparent: true, opacity: 0.6, blending: THREE.AdditiveBlending }),
      new THREE.LineBasicMaterial({ color: 0xe100ff, transparent: true, opacity: 0.4, blending: THREE.AdditiveBlending }),
      new THREE.LineBasicMaterial({ color: 0x4facfe, transparent: true, opacity: 0.5, blending: THREE.AdditiveBlending })
    ];
    
    for (let i = 0; i < ringCount; i++) {
      const radius = 1.2 + i * 0.25;
      const ringGeom = new THREE.BufferGeometry();
      const points = [];
      const segmentCount = 64;
      
      for (let j = 0; j <= segmentCount; j++) {
        const theta = (j / segmentCount) * Math.PI * 2;
        points.push(new THREE.Vector3(Math.cos(theta) * radius, Math.sin(theta) * radius, 0));
      }
      ringGeom.setFromPoints(points);
      
      const line = new THREE.Line(ringGeom, ringMaterials[i]);
      // Give random starting rotations
      line.rotation.x = Math.random() * Math.PI;
      line.rotation.y = Math.random() * Math.PI;
      this.scene.add(line);
      
      this.rings.push({
        mesh: line,
        rotSpeedX: (Math.random() - 0.5) * 0.02,
        rotSpeedY: (Math.random() - 0.5) * 0.02,
        rotSpeedZ: (Math.random() - 0.5) * 0.02,
        baseOpacity: ringMaterials[i].opacity
      });
    }
    
    // 3. Orbiting Particles
    this.particles = new ParticleSystem(this.scene, 400);
  }
  
  setState(state) {
    if (!this.themes[state]) return;
    this.currentState = state;
  }
  
  setSpeechAmplitude(amp) {
    this.speechAmplitude = amp;
  }
  
  updateColors(delta) {
    const targetTheme = this.themes[this.currentState];
    const lerpSpeed = 0.05; // Smooth transition
    
    // Lerp colors
    this.activeColors.color1.lerp(targetTheme.color1, lerpSpeed);
    this.activeColors.color2.lerp(targetTheme.color2, lerpSpeed);
    this.activeColors.glow.lerp(targetTheme.glow, lerpSpeed);
    
    // Lerp parameters
    this.activeColors.glowIntensity += (targetTheme.glowIntensity - this.activeColors.glowIntensity) * lerpSpeed;
    this.activeColors.noiseStrength += (targetTheme.noiseStrength - this.activeColors.noiseStrength) * lerpSpeed;
    this.activeColors.noiseFreq += (targetTheme.noiseFreq - this.activeColors.noiseFreq) * lerpSpeed;
    
    // In speaking mode, scale colors/intensities based on voice volume amplitude
    let currentGlow = this.activeColors.glowIntensity;
    let currentStrength = this.activeColors.noiseStrength;
    if (this.currentState === 'speaking') {
      currentGlow += this.speechAmplitude * 3.0;
      currentStrength += this.speechAmplitude * 0.4;
    }
    
    // Update shader uniforms
    this.sphereUniforms.uColor1.value = this.activeColors.color1;
    this.sphereUniforms.uColor2.value = this.activeColors.color2;
    this.sphereUniforms.uGlowColor.value = this.activeColors.glow;
    this.sphereUniforms.uGlowIntensity.value = currentGlow;
    this.sphereUniforms.uNoiseStrength.value = currentStrength;
    this.sphereUniforms.uNoiseFrequency.value = this.activeColors.noiseFreq;
    
    // Update point light color and intensity
    this.pointLight.color.copy(this.activeColors.glow);
    this.pointLight.intensity = currentGlow * 2.0;
  }
  
  animate() {
    requestAnimationFrame(() => this.animate());
    
    this.time += 0.01;
    this.sphereUniforms.uTime.value = this.time;
    
    // Handle voice volume pulse
    if (this.currentState === 'speaking') {
      this.sphereUniforms.uAmplitude.value = this.speechAmplitude;
    } else {
      this.sphereUniforms.uAmplitude.value = 0.05 * Math.sin(this.time * 5); // slow breathe
    }
    
    // Transition themes smoothly
    this.updateColors();
    
    // Rotate sphere subtly
    let baseRotationSpeed = 0.005;
    if (this.currentState === 'thinking') baseRotationSpeed = 0.001;
    if (this.currentState === 'celebrating') baseRotationSpeed = 0.03;
    if (this.currentState === 'sleeping') baseRotationSpeed = 0.0005;
    
    this.sphereMesh.rotation.y += baseRotationSpeed;
    this.sphereMesh.rotation.x += baseRotationSpeed * 0.5;
    
    // Rotate rings
    this.rings.forEach((ring, index) => {
      let rSpeedMult = 1.0;
      if (this.currentState === 'thinking') rSpeedMult = 0.2;
      if (this.currentState === 'celebrating') rSpeedMult = 4.0;
      if (this.currentState === 'sleeping') rSpeedMult = 0.05;
      
      ring.mesh.rotation.x += ring.rotSpeedX * rSpeedMult;
      ring.mesh.rotation.y += ring.rotSpeedY * rSpeedMult;
      ring.mesh.rotation.z += ring.rotSpeedZ * rSpeedMult;
      
      // Ring pulse visual effect
      let pulseAmp = 0;
      if (this.currentState === 'listening') {
        pulseAmp = 0.3 * Math.sin(this.time * 10 + index);
      } else if (this.currentState === 'speaking') {
        pulseAmp = this.speechAmplitude * 0.5 * Math.sin(this.time * 15 + index);
      }
      
      const scale = 1.0 + pulseAmp;
      ring.mesh.scale.set(scale, scale, scale);
      
      // Update ring color to match glow
      ring.mesh.material.color.copy(this.activeColors.glow);
      ring.mesh.material.opacity = ring.baseOpacity * (this.currentState === 'sleeping' ? 0.3 : 1.0);
    });
    
    // Update particles
    this.particles.update(this.time, this.currentState, this.emotionIntensity);
    
    this.renderer.render(this.scene, this.camera);
  }
  
  resize(width, height) {
    this.width = width;
    this.height = height;
    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(width, height);
  }
}

export default CompanionVisualizer;
