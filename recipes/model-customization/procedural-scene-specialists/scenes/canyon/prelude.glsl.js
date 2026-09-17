// Canyon GLSL prelude. G = core noise + this world's fields (strata, slot shadow,
// wall bounce, dust haze). VERT_WORLD / FRAG_ROCK are the base shaders every rock
// material derives from by string-surgery. TAIL is the tonemap/colorspace close.
//
// The distinctive field here is bounce(): in a slot canyon most of the light on a
// shaded wall arrives off the opposite SUNLIT wall, not from the sky. Layers that
// ignore it read as flat cut-outs.

export const G = /* glsl */`
uniform float uTime; uniform vec3 uHazeC; uniform float uHazeD;
uniform vec3 uSunDir, uSunC; uniform float uSunI; uniform vec3 uSkyC; uniform float uSkyI;
uniform vec3 uBounceC; uniform float uBounceI; uniform float uDust, uShimmer, uStrata, uMoon, uStars, uRimY;
uniform vec2 uWind;
float hash1(vec3 p){ return fract(sin(dot(p, vec3(127.1, 311.7, 74.7))) * 43758.5453); }
vec2 hash2(vec2 p){ return fract(sin(vec2(dot(p, vec2(127.1, 311.7)), dot(p, vec2(269.5, 183.3)))) * 43758.5453); }
float noise3(vec3 p){ vec3 i = floor(p), f = fract(p); f = f*f*(3.0-2.0*f);
  return mix(mix(mix(hash1(i), hash1(i+vec3(1,0,0)), f.x), mix(hash1(i+vec3(0,1,0)), hash1(i+vec3(1,1,0)), f.x), f.y),
             mix(mix(hash1(i+vec3(0,0,1)), hash1(i+vec3(1,0,1)), f.x), mix(hash1(i+vec3(0,1,1)), hash1(i+vec3(1,1,1)), f.x), f.y), f.z); }
const mat3 ROT = mat3(0.36, 0.48, -0.8, -0.8, 0.6, 0.0, 0.48, 0.64, 0.6);
float fbm3(vec3 p){ float a = 0.5, s = 0.0; for (int i = 0; i < 4; i++) { s += a * noise3(p); p = ROT * p * 2.03 + 1.7; a *= 0.5; } return s; }
float fbm2(vec2 p){ return fbm3(vec3(p, 0.37)); }

/* sedimentary banding: the signature of this world's rock. Bands run level in y
   and wobble slowly, so they read across every wall at once. */
float strata(vec3 p){ float y = p.y * 0.42 + 0.9 * fbm2(p.xz * 0.035) + 0.25 * fbm3(p * 0.11);
  float band = 0.5 + 0.5 * sin(y * 6.2831); return mix(1.0, 0.55 + 0.9 * band, uStrata); }

/* hard light down a narrow slot: lit only where the point can see the strip of sky. */
float slotLight(vec3 p){ float openness = smoothstep(-2.0, 16.0, p.y) ;
  float ridge = fbm2(p.xz * 0.05 + 11.0);
  return clamp(openness * (0.55 + 0.6 * ridge), 0.0, 1.5); }

/* light bounced off the opposite sunlit wall - warm, broad, and strongest low down. */
vec3 bounce(vec3 p, vec3 n){ float low = smoothstep(uRimY, -2.0, p.y);
  float facing = 0.5 + 0.5 * dot(n, normalize(vec3(-uSunDir.x, 0.25, -uSunDir.z)));
  return uBounceC * uBounceI * low * facing; }

/* airborne dust: a warm forward-scattering haze that thickens with distance. */
vec3 haze(vec3 col, vec3 p){ float d = distance(p, cameraPosition);
  float k = uHazeD * (1.0 + 1.6 * uDust) * (1.0 - 0.45 * smoothstep(0.0, 30.0, p.y));
  return mix(col, uHazeC, 1.0 - exp(-d * d * k * k)); }
float hazeAtt(vec3 p){ float d = distance(p, cameraPosition);
  float k = uHazeD * (1.0 + 1.6 * uDust); return exp(-d * d * k * k); }

/* wind on the floor, used by scrub sway and dust drift. */
vec2 windAt(vec3 p){ return uWind * (0.6 + 0.8 * fbm2(p.xz * 0.04 + uTime * 0.06)); }
`;

export const VERT_WORLD = /* glsl */`
varying vec3 vP, vN; uniform float uSway; uniform float uTime; uniform vec2 uWind;
void main(){
  #ifdef USE_INSTANCING
  mat4 m = modelMatrix * instanceMatrix;
  #else
  mat4 m = modelMatrix;
  #endif
  vec4 wp = m * vec4(position, 1.0);
  if (uSway > 0.0) { float s = clamp(wp.y / 3.0, 0.0, 1.0); s *= s;
    wp.xz += uSway * s * (uWind * 0.7 + vec2(sin(uTime * 1.7 + wp.z * 0.5), cos(uTime * 1.3 + wp.x * 0.6)) * 0.35); }
  vP = wp.xyz; vN = normalize(mat3(m) * normal); gl_Position = projectionMatrix * viewMatrix * wp; }`;

export const FRAG_ROCK = G + /* glsl */`
varying vec3 vP, vN; uniform vec3 uRockC; uniform float uGrain;
void main(){ vec3 p = vP;
  vec3 n = normalize(normalize(vN)
    + 0.40 * vec3(noise3(p * 0.5 + 1.0) - 0.5, noise3(p * 0.5 + 2.0) - 0.5, noise3(p * 0.5 + 3.0) - 0.5)
    + 0.30 * vec3(noise3(p * 1.7 + 1.0) - 0.5, noise3(p * 1.7 + 2.0) - 0.5, noise3(p * 1.7 + 3.0) - 0.5)
    + 0.10 * vec3(noise3(p * 6.0) - 0.5, noise3(p * 6.0 + 4.0) - 0.5, noise3(p * 6.0 + 8.0) - 0.5));
  float m = fbm3(p * 0.28), m2 = fbm3(p * 1.4 + 9.0);
  vec3 base = uRockC * strata(p) * (1.0 - uGrain * 0.35 + uGrain * 0.8 * m) * (0.82 + 0.26 * m2);
  base *= 0.72 + 0.28 * smoothstep(-1.0, 4.0, p.y);                      /* dust-stained at the base */
  float lam = max(dot(n, -uSunDir), 0.0), sl = slotLight(p);
  vec3 light = uSkyC * uSkyI * (0.35 + 0.65 * max(n.y, 0.0)) * (0.4 + 0.6 * sl)
             + uSunC * uSunI * lam * sl
             + bounce(p, n)
             + uSkyC * uMoon * 0.12 * (0.4 + 0.6 * max(n.y, 0.0));
  gl_FragColor = vec4(haze(base * light, p), 1.0);
  #include <tonemapping_fragment>
  #include <colorspace_fragment>
}`;

export const TAIL = /* glsl */`
  #include <tonemapping_fragment>
  #include <colorspace_fragment>
}`;
