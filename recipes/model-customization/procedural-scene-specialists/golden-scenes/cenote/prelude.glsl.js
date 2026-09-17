// Cenote GLSL prelude. G = CORE noise/fog + scene FIELDS (caustic, beamMask,
// torch, halo). VERT_WORLD / FRAG_ROCK are the base shaders every rock/coral
// material derives from by string-surgery. TAIL is the tonemap/colorspace close.

export const G = /* glsl */`
uniform float uTime; uniform vec3 uFogTop, uFogDeep; uniform float uFogDT, uFogDD, uHaloY;
uniform vec3 uSunDir, uSunC; uniform float uSunI; uniform vec3 uAmbC; uniform float uAmbI, uCaus;
uniform vec3 uBeamTop, uBeamDir; uniform float uBeamR, uBeamI; uniform vec3 uTorchPos, uTorchDir; uniform float uTorchI;
float hash1(vec3 p){ return fract(sin(dot(p, vec3(127.1, 311.7, 74.7))) * 43758.5453); }
vec2 hash2(vec2 p){ return fract(sin(vec2(dot(p, vec2(127.1, 311.7)), dot(p, vec2(269.5, 183.3)))) * 43758.5453); }
float noise3(vec3 p){ vec3 i = floor(p), f = fract(p); f = f*f*(3.0-2.0*f);
  return mix(mix(mix(hash1(i), hash1(i+vec3(1,0,0)), f.x), mix(hash1(i+vec3(0,1,0)), hash1(i+vec3(1,1,0)), f.x), f.y),
             mix(mix(hash1(i+vec3(0,0,1)), hash1(i+vec3(1,0,1)), f.x), mix(hash1(i+vec3(0,1,1)), hash1(i+vec3(1,1,1)), f.x), f.y), f.z); }
const mat3 ROT = mat3(0.36, 0.48, -0.8, -0.8, 0.6, 0.0, 0.48, 0.64, 0.6);
float fbm3(vec3 p){ float a = 0.5, s = 0.0; for (int i = 0; i < 4; i++) { s += a * noise3(p); p = ROT * p * 2.03 + 1.7; a *= 0.5; } return s; }
float fbm2(vec2 p){ return fbm3(vec3(p, 0.37)); }
float cells(vec2 p, float t){ vec2 i = floor(p), f = fract(p); float m = 1.0;
  for (int y = -1; y <= 1; y++) for (int x = -1; x <= 1; x++) { vec2 g = vec2(float(x), float(y)); vec2 o = hash2(i + g);
    o = 0.5 + 0.45 * sin(t + 6.2831 * o); vec2 r = g + o - f; m = min(m, dot(r, r)); } return pow(1.0 - m, 3.0); }
float caustic(vec3 p){ vec2 q = p.xz * 0.32; return cells(q, uTime * 0.9) * 0.6 + cells(q * 1.9 + 3.1, uTime * 1.3) * 0.5; }
float beamMask(vec3 p){ vec3 d = p - uBeamTop; float h = dot(d, uBeamDir); vec3 q = d - h * uBeamDir;
  float r = length(q) / uBeamR; return smoothstep(1.2, 0.5, r) * smoothstep(-0.5, 0.5, h) * exp(-h * 0.035) * uBeamI; }
vec3 torchAt(vec3 p){ vec3 v = p - uTorchPos; float d = length(v); v /= max(d, 1e-3);
  float cone = pow(max(dot(v, uTorchDir), 0.0), 18.0); return uTorchI * cone / (1.0 + d * d * 0.012) * vec3(1.0, 0.93, 0.8); }
vec3 torch(vec3 p, vec3 n){ vec3 v = normalize(p - uTorchPos); return torchAt(p) * max(dot(n, -v), 0.0); }
float haloY(vec3 p){ return uHaloY + 3.2 * (fbm2(p.xz * 0.06 + uTime * 0.015) - 0.5) * 2.0; }
vec3 fog(vec3 col, vec3 p){ float d = distance(p, cameraPosition);
  if (p.y > 0.0) d *= clamp(-cameraPosition.y / max(p.y - cameraPosition.y, 1e-3), 0.0, 1.0);
  float hy = haloY(p); float k = smoothstep(hy - 5.0, hy + 4.0, p.y); vec3 fc = mix(uFogDeep, uFogTop, k); float fd = mix(uFogDD, uFogDT, k);
  return mix(fc, col, exp(-d * d * fd * fd)); }
float fogAtt(vec3 p){ float d = distance(p, cameraPosition); if (p.y > 0.0) d *= clamp(-cameraPosition.y / max(p.y - cameraPosition.y, 1e-3), 0.0, 1.0);
  float hy = haloY(p); float k = smoothstep(hy - 5.0, hy + 4.0, p.y); float fd = mix(uFogDD, uFogDT, k); return exp(-d * d * fd * fd); }
uniform vec3 uHolePos;
`;

export const VERT_WORLD = /* glsl */`
varying vec3 vP, vN; uniform float uSway; uniform float uTime;
void main(){
  #ifdef USE_INSTANCING
  mat4 m = modelMatrix * instanceMatrix;
  #else
  mat4 m = modelMatrix;
  #endif
  vec4 wp = m * vec4(position, 1.0);
  if (uSway > 0.0) { float s = clamp((12.0 - wp.y) / 20.0, 0.0, 1.0); s *= s;
    wp.xz += uSway * s * vec2(sin(uTime * 0.55 + wp.y * 0.35 + wp.x * 0.7), cos(uTime * 0.47 + wp.z * 0.8 + wp.y * 0.3)); }
  vP = wp.xyz; vN = normalize(mat3(m) * normal); gl_Position = projectionMatrix * viewMatrix * wp; }`;

export const FRAG_ROCK = G + /* glsl */`
varying vec3 vP, vN; uniform vec3 uBase; uniform float uMottle;
void main(){ vec3 p = vP; vec3 n = normalize(normalize(vN) + 0.45 * vec3(noise3(p * 0.45 + 1.0) - 0.5, noise3(p * 0.45 + 2.0) - 0.5, noise3(p * 0.45 + 3.0) - 0.5) + 0.4 * vec3(noise3(p * 1.3 + 1.0) - 0.5, noise3(p * 1.3 + 2.0) - 0.5, noise3(p * 1.3 + 3.0) - 0.5) + 0.12 * vec3(noise3(p * 5.0) - 0.5, noise3(p * 5.0 + 4.0) - 0.5, noise3(p * 5.0 + 8.0) - 0.5));
  float m = fbm3(p * 0.33), m2 = fbm3(p * 1.6 + 9.0), m3 = noise3(p * 6.0);
  vec3 base = uBase * (1.0 - uMottle * 0.45 + uMottle * 0.9 * m) * (0.78 + 0.3 * m2 + 0.14 * m3);
  base *= 1.0 - 0.35 * smoothstep(1.5, -0.5, abs(p.y));                       /* dark waterline stain */
  float bm = beamMask(p), lam = max(dot(n, -uSunDir), 0.0);
  vec3 toHole = uHolePos - p; float dh = length(toHole); float sky = max(dot(n, toHole / dh), 0.0) * 55.0 / (dh * dh + 60.0);   /* irradiance from the opening */
  vec3 light = uAmbC * uAmbI * (0.5 + 0.5 * (n.y * 0.5 + 0.5)) * (0.4 + 0.6 * smoothstep(-20.0, 0.0, p.y))
             + uSunC * uSunI * (lam * (0.08 + 0.4 * bm) + sky * 0.6)
             + uSunC * caustic(p) * uCaus * (0.14 + 0.45 * bm) * (0.35 + 0.65 * max(n.y, 0.0)) * step(p.y, 0.0) * smoothstep(-23.0, -6.0, p.y)
             + torch(p, n);
  gl_FragColor = vec4(fog(base * light, p), 1.0);
  #include <tonemapping_fragment>
  #include <colorspace_fragment>
}`;

export const TAIL = /* glsl */`
  #include <tonemapping_fragment>
  #include <colorspace_fragment>
}`;
