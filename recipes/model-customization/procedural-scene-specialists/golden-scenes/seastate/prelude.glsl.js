// Scene FIELDS (seastate): one skyRadiance() used by BOTH the sky dome and the
// ocean's reflections/fog, so the water always mirrors the exact sky above it.
// Materials must define CLOUD_OCT (fbm octaves) before including this chunk.

export const atmosphereUniformsGLSL = /* glsl */ `
uniform vec3  uSunDir;
uniform vec3  uSunTint;
uniform vec3  uZenith;
uniform vec3  uHorizon;
uniform float uGradFalloff;
uniform float uSunDisc;
uniform float uSunGlow;
uniform float uCloudCoverage;
uniform float uCloudDensity;
uniform float uCloudScale;
uniform vec2  uCloudOff;
uniform vec3  uCloudLit;
uniform vec3  uCloudShadow;
uniform vec3  uFogColor;
uniform float uFogVeil;
uniform float uStars;
uniform vec3  uMoonDir;
uniform float uMoon;
uniform float uLightning;
uniform float uTime;
uniform float uExposure;
`;

export const atmosphereGLSL = /* glsl */ `
float hash21(vec2 p) {
  p = fract(p * vec2(123.34, 456.21));
  p += dot(p, p + 45.32);
  return fract(p.x * p.y);
}

float vnoise(vec2 p) {
  vec2 i = floor(p);
  vec2 f = fract(p);
  vec2 u = f * f * (3.0 - 2.0 * f);
  float a = hash21(i);
  float b = hash21(i + vec2(1.0, 0.0));
  float c = hash21(i + vec2(0.0, 1.0));
  float d = hash21(i + vec2(1.0, 1.0));
  return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
}

float fbm(vec2 p) {
  float v = 0.0;
  float a = 0.5;
  mat2 r = mat2(0.8, -0.6, 0.6, 0.8);
  for (int i = 0; i < CLOUD_OCT; i++) {
    v += a * vnoise(p);
    p = r * p * 2.03;
    a *= 0.5;
  }
  return v;
}

vec4 cloudLayer(vec3 dir) {
  float horizonFade = smoothstep(0.015, 0.14, dir.y);
  if (horizonFade <= 0.001 || uCloudCoverage <= 0.004) return vec4(0.0);

  // project the view ray onto a virtual cloud deck
  vec2 uv = dir.xz * (1.0 / max(dir.y, 0.06)) * uCloudScale + uCloudOff;
  float base = fbm(uv);

  float cov  = uCloudCoverage;
  float mask  = smoothstep(1.0 - cov - 0.12, 1.0 - cov + 0.30, base);
  float thick = smoothstep(1.0 - cov, 1.0 - cov + 0.55, base);

  // cheap directional lighting: sample density toward the sun
  vec2 toSun = normalize(uSunDir.xz + vec2(0.0001, 0.0)) * 0.4;
  float baseS = fbm(uv + toSun);
  float rim = clamp((base - baseS) * 3.0 + 0.5, 0.0, 1.0);

  vec3 col = mix(uCloudLit, uCloudShadow, clamp(thick * uCloudDensity, 0.0, 1.0));
  col = mix(col, uCloudLit, rim * 0.35 * (1.0 - thick * 0.5));
  col += vec3(0.85, 0.9, 1.0) * uLightning * 0.9;

  float alpha = mask * horizonFade * clamp(uCloudDensity + 0.35, 0.0, 1.0);
  return vec4(col, clamp(alpha, 0.0, 1.0));
}

vec3 starField(vec3 dir) {
  if (uStars <= 0.003 || dir.y <= 0.0) return vec3(0.0);
  vec2 sp = vec2(atan(dir.x, dir.z), dir.y) * vec2(60.0, 90.0);
  vec2 cell = floor(sp);
  vec2 f = fract(sp);
  float h = hash21(cell);
  if (h < 0.78) return vec3(0.0);
  vec2 starPos = vec2(hash21(cell + 7.1), hash21(cell + 3.7));
  float d = length(f - starPos);
  float b = smoothstep(0.09, 0.0, d);
  float mag = (h - 0.78) / 0.22;
  float tw = 0.7 + 0.3 * sin(uTime * (1.5 + 4.0 * mag) + h * 40.0);
  return vec3(0.9, 0.93, 1.0) * b * mag * tw * smoothstep(0.0, 0.18, dir.y);
}

vec3 skyRadiance(vec3 dir) {
  float y = clamp(dir.y, 0.0, 1.0);
  vec3 col = mix(uHorizon, uZenith, pow(y, uGradFalloff));

  // sun glow + halo + disc
  float sd = max(dot(dir, uSunDir), 0.0);
  col += uSunTint * (pow(sd, 6.0) * 0.35 + pow(sd, 32.0) * 0.5) * uSunGlow;
  col += uSunTint * smoothstep(0.99930, 0.99975, sd) * uSunDisc * 1.6;

  // night sky — the sharp stars/moon disc only exist in the sky dome itself;
  // in water reflections they alias into per-pixel speckle, so skip them there
  float md = max(dot(dir, uMoonDir), 0.0);
  vec3 moonCol = vec3(0.92, 0.95, 1.0);
#ifdef SKY_FULL
  col += starField(dir) * uStars;
  col += moonCol * smoothstep(0.99985, 0.99994, md) * uMoon * 2.5;
#endif
  col += moonCol * pow(md, 150.0) * uMoon * 0.35;

  // clouds occlude everything above
  vec4 cl = cloudLayer(dir);
  col = mix(col, cl.rgb, cl.a);

  // lightning ambience
  col += vec3(0.75, 0.8, 1.0) * uLightning * 0.35;

  // haze / fog veil, densest at the horizon
  float veil = uFogVeil * mix(1.0, exp(-max(dir.y, 0.0) * 5.0), 0.75);
  col = mix(col, uFogColor, clamp(veil, 0.0, 1.0));

  return col;
}

vec3 acesTonemap(vec3 x) {
  return clamp((x * (2.51 * x + 0.03)) / (x * (2.43 * x + 0.59) + 0.14), 0.0, 1.0);
}
`;
