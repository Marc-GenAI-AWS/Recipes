// High Park GLSL prelude. G = CORE noise/fog + scene FIELDS (windAt, cloudShad,
// shaftMask) shared by every layer so one state moves the whole basin.

export const G = /* glsl */`
uniform float uTime; uniform vec3 uSkyTop, uSkyHorizon, uSunC; uniform float uSunI; uniform vec3 uSunDir;
uniform vec3 uFogC; uniform float uFogD, uWind, uCloud, uShadowAmt, uShaft, uFlash; uniform vec3 uShaftDir, uSaddle;
const vec3 FLASH_C = vec3(0.78, 0.84, 1.0);   /* cold blue-white lightning light */
float hash1(vec3 p){ return fract(sin(dot(p, vec3(127.1, 311.7, 74.7))) * 43758.5453); }
float noise3(vec3 p){ vec3 i = floor(p), f = fract(p); f = f*f*(3.0-2.0*f);
  return mix(mix(mix(hash1(i), hash1(i+vec3(1,0,0)), f.x), mix(hash1(i+vec3(0,1,0)), hash1(i+vec3(1,1,0)), f.x), f.y),
             mix(mix(hash1(i+vec3(0,0,1)), hash1(i+vec3(1,0,1)), f.x), mix(hash1(i+vec3(0,1,1)), hash1(i+vec3(1,1,1)), f.x), f.y), f.z); }
float fbm3(vec3 p){ float a = 0.5, s = 0.0; for (int i = 0; i < 4; i++) { s += a * noise3(p); p = p * 2.03 + 1.7; a *= 0.5; } return s; }
float fbm2(vec2 p){ return fbm3(vec3(p, 0.37)); }
/* wind field: broad gusts + fine ripples travelling east (+x); every swaying thing samples this */
float windAt(vec2 xz, float t){ return (fbm2(xz * 0.020 - vec2(t * 0.50, t * 0.06)) * 0.75
  + fbm2(xz * 0.11 - vec2(t * 1.5, 0.0)) * 0.35 + 0.18) * uWind; }
/* cloud-shadow factor: 1 in sun, dips where cumulus pass; shared by turf, grass, herd, rocks */
float cloudShad(vec3 p){ return 1.0 - uShadowAmt * 0.6 *
  smoothstep(0.16, 0.5, fbm2(p.xz * 0.0045 + vec2(uTime * 0.014, uTime * 0.004))); }
/* the hero: crepuscular corridor falling from the saddle along uShaftDir */
float shaftMask(vec3 p){
  vec3 d = p - uSaddle; float h = dot(d, uShaftDir); vec3 q = d - h * uShaftDir;
  float r = length(q.xz * vec2(1.0, 2.2)) / (18.0 + h * 0.18);                 /* widening elliptical corridor */
  float blades = 0.55 + 0.45 * fbm2(vec2(q.x * 0.14 + 5.0, uTime * 0.05));     /* it is made of separate blades */
  return uShaft * smoothstep(1.1, 0.35, r) * smoothstep(-6.0, 30.0, h) * exp(-h * 0.006) * blades; }
/* valley haze: denser low, tinted by state; every material calls this last */
vec3 fog(vec3 col, vec3 p){ float d = distance(p, cameraPosition);
  float alt = clamp((p.y + 6.0) / 130.0, 0.0, 1.0);
  float f = 1.0 - exp(-uFogD * d * (1.15 - 1.0 * alt));
  return mix(col, uFogC, clamp(f, 0.0, 0.95)); }
float fogAtt(vec3 p){ float d = distance(p, cameraPosition); float alt = clamp((p.y + 6.0) / 130.0, 0.0, 1.0);
  return exp(-uFogD * d * (1.15 - 1.0 * alt)); }
`;

export const TAIL = /* glsl */`
  #include <tonemapping_fragment>
  #include <colorspace_fragment>
}`;

export const VERT_WORLD = /* glsl */`
varying vec3 vP, vN;
void main(){
  #ifdef USE_INSTANCING
  mat4 m = modelMatrix * instanceMatrix;
  #else
  mat4 m = modelMatrix;
  #endif
  vec4 wp = m * vec4(position, 1.0);
  vP = wp.xyz; vN = normalize(mat3(m) * normal); gl_Position = projectionMatrix * viewMatrix * wp; }`;

/* base lit-matter fragment: albedo mottled by fbm, lit by sun×cloudShad + sky ambient + shaft boost */
export const FRAG_MATTER = G + /* glsl */`
varying vec3 vP, vN; uniform vec3 uBase; uniform float uMottle;
void main(){ vec3 p = vP;
  vec3 n = normalize(normalize(vN) + 0.4 * vec3(noise3(p * 0.8 + 1.0) - 0.5, noise3(p * 0.8 + 2.0) - 0.5, noise3(p * 0.8 + 3.0) - 0.5));
  float m1 = fbm3(p * 0.35), m2 = noise3(p * 3.0);
  vec3 base = uBase * (1.0 - uMottle * 0.4 + uMottle * 0.8 * m1) * (0.82 + 0.28 * m2);
  float lam = max(dot(n, normalize(uSunDir)), 0.0);
  float sm = shaftMask(p), cs = cloudShad(p);
  vec3 skyFill = mix(uSkyHorizon, uSkyTop, 0.5) * (0.30 + 0.22 * max(n.y, 0.0));
  vec3 light = skyFill + uSunC * uSunI * lam * (0.5 + 0.6 * cs) + uSunC * sm * (0.4 + 0.6 * lam) + FLASH_C * uFlash * (0.7 + 0.6 * max(n.y, 0.0));
  gl_FragColor = vec4(fog(base * light, p), 1.0);` + TAIL;
