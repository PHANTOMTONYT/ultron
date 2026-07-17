import * as THREE from 'https://esm.sh/three@0.160.0';
import ParticleSystem from '../particles/particle_system.js';

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
    
    // Theme Colors for Orbiting Rings & Badge Glow
    this.themes = {
      idle: {
        glow: new THREE.Color('#00f2fe'),
        glowIntensity: 1.2
      },
      listening: {
        glow: new THREE.Color('#7f00ff'),
        glowIntensity: 1.8
      },
      thinking: {
        glow: new THREE.Color('#ffb199'),
        glowIntensity: 1.4
      },
      speaking: {
        glow: new THREE.Color('#00c6ff'),
        glowIntensity: 2.2
      },
      happy: {
        glow: new THREE.Color('#f6d365'),
        glowIntensity: 2.0
      },
      excited: {
        glow: new THREE.Color('#ff8a3d'),
        glowIntensity: 2.6
      },
      curious: {
        glow: new THREE.Color('#96fbc4'),
        glowIntensity: 1.7
      },
      celebrating: {
        glow: new THREE.Color('#ff0844'),
        glowIntensity: 2.8
      },
      confused: {
        glow: new THREE.Color('#96fbc4'),
        glowIntensity: 1.5
      },
      sleeping: {
        glow: new THREE.Color('#330867'),
        glowIntensity: 0.3
      }
    };
    
    this.activeColors = {
      glow: this.themes.idle.glow.clone(),
      glowIntensity: this.themes.idle.glowIntensity
    };
    
    this.ready = this.init();
  }

  async init() {
    this.initScene();
    this.initObjects();
    this.animate();
  }

  initScene() {
    this.scene = new THREE.Scene();
    
    // Camera settings
    this.camera = new THREE.PerspectiveCamera(45, this.width / this.height, 0.1, 100);
    this.camera.position.z = 4.2;
    
    // Renderer settings
    this.renderer = new THREE.WebGLRenderer({
      canvas: this.canvas,
      alpha: true,
      antialias: true,
      powerPreference: "high-performance"
    });
    this.renderer.setSize(this.width, this.height);
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    
    // Soft Ambient Light
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.55);
    this.scene.add(ambientLight);
    
    // Soft Point Light matching theme color
    const pointLight = new THREE.PointLight(0x00f2fe, 1.5, 8);
    pointLight.position.set(0, 0.2, 0.8);
    this.scene.add(pointLight);
    this.pointLight = pointLight;

    // Directional Light from front-right to shape Baymax's rounded features
    const dirLight = new THREE.DirectionalLight(0xffffff, 1.5);
    dirLight.position.set(2, 3, 4);
    this.scene.add(dirLight);
  }
  
  initObjects() {
    // Soft matte white material for Baymax body
    this.baymaxMaterial = new THREE.MeshStandardMaterial({
      color: 0xeeeeee,
      roughness: 0.85,
      metalness: 0.05,
      flatShading: false
    });

    // Dark grey/black for eyes/mouth line
    this.eyeMaterial = new THREE.MeshBasicMaterial({
      color: 0x1a1a1a
    });

    // Create a group to hold all Baymax body parts
    this.baymaxGroup = new THREE.Group();
    this.scene.add(this.baymaxGroup);

    // 1. Torso (Belly) - egg-like stretched sphere
    const torsoGeom = new THREE.SphereGeometry(0.52, 32, 32);
    torsoGeom.scale(1.0, 1.22, 0.94);
    this.torso = new THREE.Mesh(torsoGeom, this.baymaxMaterial);
    this.torso.position.set(0, -0.15, 0);
    this.baymaxGroup.add(this.torso);

    // 2. Head - squashed horizontal sphere
    const headGeom = new THREE.SphereGeometry(0.22, 32, 32);
    headGeom.scale(1.3, 0.85, 1.0);
    this.head = new THREE.Mesh(headGeom, this.baymaxMaterial);
    this.head.position.set(0, 0.65, 0);
    this.baymaxGroup.add(this.head);

    // 3. Eyes (left/right) - small black spheres
    // Left eye
    this.leftEye = new THREE.Mesh(new THREE.SphereGeometry(0.024, 16, 16), this.eyeMaterial);
    this.leftEye.position.set(-0.11, 0.05, 0.205);
    this.head.add(this.leftEye);

    // Right eye
    this.rightEye = new THREE.Mesh(new THREE.SphereGeometry(0.024, 16, 16), this.eyeMaterial);
    this.rightEye.position.set(0.11, 0.05, 0.205);
    this.head.add(this.rightEye);

    // 4. Eye Bridge Line (Audio Waveform Mouth!)
    // We'll create a dynamic line with 20 segments between the eyes
    this.bridgeSegments = 20;
    this.bridgeGeometry = new THREE.BufferGeometry();
    this.bridgePositions = new Float32Array((this.bridgeSegments + 1) * 3);
    
    for (let i = 0; i <= this.bridgeSegments; i++) {
      const t = i / this.bridgeSegments;
      const x = -0.11 + t * 0.22;
      const y = 0.05;
      const z = 0.208; // slightly in front of eyes to prevent z-fighting
      
      const idx = i * 3;
      this.bridgePositions[idx] = x;
      this.bridgePositions[idx + 1] = y;
      this.bridgePositions[idx + 2] = z;
    }
    
    this.bridgeGeometry.setAttribute('position', new THREE.BufferAttribute(this.bridgePositions, 3));
    this.eyeBridge = new THREE.Line(this.bridgeGeometry, this.eyeMaterial);
    this.head.add(this.eyeBridge);

    // 5. Arms
    // Left arm
    const leftArmGeom = new THREE.CylinderGeometry(0.065, 0.09, 0.52, 16);
    leftArmGeom.translate(0, -0.24, 0); // shift pivot to shoulder
    this.leftArm = new THREE.Mesh(leftArmGeom, this.baymaxMaterial);
    this.leftArm.position.set(-0.58, 0.24, 0);
    this.leftArm.rotation.z = 0.25; // natural sway outward
    this.baymaxGroup.add(this.leftArm);

    // Right arm
    const rightArmGeom = new THREE.CylinderGeometry(0.065, 0.09, 0.52, 16);
    rightArmGeom.translate(0, -0.24, 0); // shift pivot to shoulder
    this.rightArm = new THREE.Mesh(rightArmGeom, this.baymaxMaterial);
    this.rightArm.position.set(0.58, 0.24, 0);
    this.rightArm.rotation.z = -0.25; // natural sway outward
    this.baymaxGroup.add(this.rightArm);

    // 6. Legs
    // Left leg
    const leftLegGeom = new THREE.CylinderGeometry(0.095, 0.115, 0.32, 16);
    this.leftLeg = new THREE.Mesh(leftLegGeom, this.baymaxMaterial);
    this.leftLeg.position.set(-0.19, -0.82, 0);
    this.baymaxGroup.add(this.leftLeg);

    // Right leg
    const rightLegGeom = new THREE.CylinderGeometry(0.095, 0.115, 0.32, 16);
    this.rightLeg = new THREE.Mesh(rightLegGeom, this.baymaxMaterial);
    this.rightLeg.position.set(0.19, -0.82, 0);
    this.baymaxGroup.add(this.rightLeg);

    // 7. Circular Healthcare Chest Badge (with glowing status light)
    this.badgeMaterial = new THREE.MeshStandardMaterial({
      color: 0xcccccc,
      emissive: new THREE.Color(0x000000),
      roughness: 0.5
    });
    const badgeGeom = new THREE.CircleGeometry(0.04, 32);
    this.badge = new THREE.Mesh(badgeGeom, this.badgeMaterial);
    this.badge.position.set(0.16, 0.2, 0.4);
    this.badge.rotation.y = 0.15; // angle slightly to the right side contour
    this.baymaxGroup.add(this.badge);

    // 8. Concentric Orbiting Rings (Hologram Look)
    this.rings = [];
    const ringCount = 3;
    const ringMaterials = [
      new THREE.LineBasicMaterial({ color: 0x00f2fe, transparent: true, opacity: 0.4, blending: THREE.AdditiveBlending }),
      new THREE.LineBasicMaterial({ color: 0xe100ff, transparent: true, opacity: 0.15, blending: THREE.AdditiveBlending }),
      new THREE.LineBasicMaterial({ color: 0x4facfe, transparent: true, opacity: 0.25, blending: THREE.AdditiveBlending })
    ];
    
    for (let i = 0; i < ringCount; i++) {
      const radius = 1.1 + i * 0.22;
      const ringGeom = new THREE.BufferGeometry();
      const points = [];
      const segmentCount = 64;
      
      for (let j = 0; j <= segmentCount; j++) {
        const theta = (j / segmentCount) * Math.PI * 2;
        points.push(new THREE.Vector3(Math.cos(theta) * radius, Math.sin(theta) * radius, 0));
      }
      ringGeom.setFromPoints(points);
      
      const line = new THREE.Line(ringGeom, ringMaterials[i]);
      line.rotation.x = Math.random() * Math.PI;
      line.rotation.y = Math.random() * Math.PI;
      this.scene.add(line);
      
      this.rings.push({
        mesh: line,
        rotSpeedX: (Math.random() - 0.5) * 0.015,
        rotSpeedY: (Math.random() - 0.5) * 0.015,
        rotSpeedZ: (Math.random() - 0.5) * 0.015,
        baseOpacity: ringMaterials[i].opacity
      });
    }
    
    // 9. Orbiting Particles
    this.particles = new ParticleSystem(this.scene, 250);
  }
  
  setState(state) {
    if (!this.themes[state]) return;
    this.currentState = state;
  }
  
  setSpeechAmplitude(amp) {
    this.speechAmplitude = amp;
  }
  
  updateColors() {
    const targetTheme = this.themes[this.currentState];
    const lerpSpeed = 0.05; // Smooth transition
    
    // Lerp glow color and intensity
    this.activeColors.glow.lerp(targetTheme.glow, lerpSpeed);
    this.activeColors.glowIntensity += (targetTheme.glowIntensity - this.activeColors.glowIntensity) * lerpSpeed;
    
    // Pulse chest badge based on state & speech amplitude
    let intensity = 0.0;
    if (this.currentState === 'speaking') {
      intensity = 0.4 + this.speechAmplitude * 2.8;
    } else if (this.currentState === 'listening') {
      intensity = 0.15 + 0.1 * Math.sin(this.time * 6);
    } else if (this.currentState === 'thinking') {
      intensity = 0.3 + 0.25 * Math.sin(this.time * 12);
    }
    
    // Update badge emissive glow
    this.badgeMaterial.emissive.copy(this.activeColors.glow).multiplyScalar(intensity);
    
    // Update point light color and intensity
    this.pointLight.color.copy(this.activeColors.glow);
    this.pointLight.intensity = this.activeColors.glowIntensity * 1.5;
  }
  
  animate() {
    requestAnimationFrame(() => this.animate());
    
    this.time += 0.015;
    
    // Smoothly update visual helper colors & light
    this.updateColors();
    
    // 1. Breathing Animation (Belly breathing)
    let breathSpeed = 2.0;
    let breathAmp = 0.02;
    if (this.currentState === 'sleeping') {
      breathSpeed = 0.9;
      breathAmp = 0.007;
    } else if (this.currentState === 'excited') {
      breathSpeed = 3.5;
      breathAmp = 0.035;
    }
    
    const breath = 1.0 + breathAmp * Math.sin(this.time * breathSpeed);
    this.torso.scale.set(1.0, 1.22 * breath, 1.0);
    this.head.position.y = 0.65 + (breath - 1.0) * 0.15; // head moves slightly with torso breathing
    
    // 2. Emotes & State-based Joint Gestures
    let targetHeadTiltX = 0.0;
    let targetHeadTiltZ = 0.0;
    let targetLeftArmRotZ = 0.25;
    let targetRightArmRotZ = -0.25;
    let targetLeftArmRotX = 0.0;
    let targetRightArmRotX = 0.0;
    
    if (this.currentState === 'thinking') {
      targetHeadTiltX = 0.12;
    } else if (this.currentState === 'confused') {
      targetHeadTiltZ = 0.22; // Inquisitive Baymax head-tilt
      targetHeadTiltX = 0.05;
    } else if (this.currentState === 'curious') {
      // Inquisitive tilt in the opposite direction from confused, leaning slightly in
      targetHeadTiltZ = -0.18;
      targetHeadTiltX = -0.08;
    } else if (this.currentState === 'excited') {
      // Both arms lift and sway with joy (breathing is already faster/deeper in this state)
      targetLeftArmRotZ = 0.9 + Math.sin(this.time * 10) * 0.15;
      targetRightArmRotZ = -0.9 + Math.cos(this.time * 10) * 0.15;
      targetHeadTiltX = -0.05;
    } else if (this.currentState === 'happy') {
      // Waving right arm
      targetRightArmRotZ = -1.1;
      targetRightArmRotX = Math.sin(this.time * 8) * 0.25;
      targetHeadTiltZ = -0.06;
    } else if (this.currentState === 'celebrating') {
      // Raise both hands and sway!
      targetLeftArmRotZ = 1.4;
      targetRightArmRotZ = -1.4;
      targetLeftArmRotX = Math.sin(this.time * 12) * 0.25;
      targetRightArmRotX = Math.cos(this.time * 12) * 0.25;
    } else if (this.currentState === 'speaking') {
      // Sway body and arms gently as he talks
      targetLeftArmRotZ = 0.25 + Math.sin(this.time * 5) * 0.08;
      targetRightArmRotZ = -0.25 + Math.cos(this.time * 5) * 0.08;
      targetHeadTiltX = 0.06 + Math.sin(this.time * 4) * 0.04;
    } else if (this.currentState === 'sleeping') {
      targetHeadTiltX = 0.28; // head falls down slightly
    }
    
    // Lerp joint values for smooth transitions
    const lerpRotSpeed = 0.07;
    this.head.rotation.x += (targetHeadTiltX - this.head.rotation.x) * lerpRotSpeed;
    this.head.rotation.z += (targetHeadTiltZ - this.head.rotation.z) * lerpRotSpeed;
    this.leftArm.rotation.z += (targetLeftArmRotZ - this.leftArm.rotation.z) * lerpRotSpeed;
    this.rightArm.rotation.z += (targetRightArmRotZ - this.rightArm.rotation.z) * lerpRotSpeed;
    this.leftArm.rotation.x += (targetLeftArmRotX - this.leftArm.rotation.x) * lerpRotSpeed;
    this.rightArm.rotation.x += (targetRightArmRotX - this.rightArm.rotation.x) * lerpRotSpeed;
    
    // 3. Update the Holographic Speaking Mouth Wave (Eye Bridge Line)
    const positions = this.bridgeGeometry.attributes.position.array;
    for (let i = 0; i <= this.bridgeSegments; i++) {
      const idx = i * 3;
      const t = i / this.bridgeSegments;
      
      let offset = 0;
      if (this.currentState === 'speaking') {
        // Wave peaks in the center, tapers off at the eyes (t=0, t=1) using a bell curve factor
        const envelope = Math.sin(t * Math.PI);
        const wave = Math.sin(this.time * 24 + t * 18) * 0.035 * this.speechAmplitude;
        offset = wave * envelope;
      }
      
      positions[idx + 1] = 0.05 + offset; // Perturb Y-axis
    }
    this.bridgeGeometry.attributes.position.needsUpdate = true;
    
    // 4. Subtle overall body float
    this.baymaxGroup.rotation.y = Math.sin(this.time * 0.4) * 0.04;
    
    // 5. Rotate Concentric Rings
    this.rings.forEach((ring, index) => {
      let rSpeedMult = 1.0;
      if (this.currentState === 'thinking') rSpeedMult = 0.2;
      if (this.currentState === 'celebrating') rSpeedMult = 4.0;
      if (this.currentState === 'sleeping') rSpeedMult = 0.04;
      
      ring.mesh.rotation.x += ring.rotSpeedX * rSpeedMult;
      ring.mesh.rotation.y += ring.rotSpeedY * rSpeedMult;
      ring.mesh.rotation.z += ring.rotSpeedZ * rSpeedMult;
      
      // Pulse rings scale based on microphone activity/state
      let pulseAmp = 0;
      if (this.currentState === 'listening') {
        pulseAmp = 0.12 * Math.sin(this.time * 8 + index);
      } else if (this.currentState === 'speaking') {
        pulseAmp = this.speechAmplitude * 0.2 * Math.sin(this.time * 12 + index);
      }
      
      const scale = 1.0 + pulseAmp;
      ring.mesh.scale.set(scale, scale, scale);
      
      // Update ring color to match active theme glow
      ring.mesh.material.color.copy(this.activeColors.glow);
      ring.mesh.material.opacity = ring.baseOpacity * (this.currentState === 'sleeping' ? 0.2 : 1.0);
    });
    
    // 6. Update particles
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

