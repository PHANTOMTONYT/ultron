uniform vec3 uColor1;
uniform vec3 uColor2;
uniform vec3 uGlowColor;
uniform float uGlowIntensity;
uniform float uTime;

varying vec3 vNormal;
varying vec3 vPosition;
varying float vNoise;

void main() {
  // Normalize normal and create view direction
  vec3 normal = normalize(vNormal);
  
  // Since we are in view space (camera is at 0,0,0), the view direction is simply normalize(-vPosition)
  vec3 viewDir = normalize(vec3(0.0, 0.0, 1.0)); // Simple camera direction
  
  // Fresnel effect (brighter on the edges)
  float fresnel = pow(1.0 - max(dot(normal, viewDir), 0.0), 2.5);
  
  // Mix colors based on the noise from vertex shader
  float noiseFactor = (vNoise + 1.0) * 0.5; // Map from [-1, 1] to [0, 1]
  vec3 baseColor = mix(uColor1, uColor2, noiseFactor);
  
  // Add a pulsing glow
  float pulse = 0.8 + 0.2 * sin(uTime * 3.0);
  vec3 finalColor = baseColor + (uGlowColor * fresnel * uGlowIntensity * pulse);
  
  // Output alpha based on fresnel and base transparency
  float alpha = mix(0.4, 0.95, fresnel);
  
  gl_FragColor = vec4(finalColor, alpha);
}
