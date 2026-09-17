import * as THREE from 'three';

// The factored state manifest: a time-of-day preset combined with a weather
// preset produces one flat target object (colours, vectors, numbers) that the
// contract StateMachine interpolates. See SCENE_CONTRACT.md §8 (factored form).

// ---------- time of day: sun position and palette ----------

const TIMES = {
  dawn: {
    label: 'Dawn',
    sunEl: 6, sunAz: -20,
    sunTint: [1.0, 0.62, 0.36],
    zenith: [0.13, 0.21, 0.4],
    horizon: [0.9, 0.5, 0.3],
    falloff: 0.34,
    glow: 0.85, disc: 1.0,
    cloudLit: [1.0, 0.72, 0.52],
    cloudShadow: [0.28, 0.28, 0.38],
    stars: 0.12, moon: 0.0,
    waterDeep: [0.02, 0.05, 0.09],
    waterShallow: [0.1, 0.17, 0.19],
    exposure: 1.0,
  },
  midday: {
    label: 'Midday',
    sunEl: 62, sunAz: 15,
    sunTint: [1.0, 0.98, 0.92],
    zenith: [0.09, 0.32, 0.72],
    horizon: [0.55, 0.72, 0.88],
    falloff: 0.36,
    glow: 0.5, disc: 1.0,
    cloudLit: [1.0, 1.0, 1.0],
    cloudShadow: [0.55, 0.6, 0.68],
    stars: 0.0, moon: 0.0,
    waterDeep: [0.015, 0.08, 0.14],
    waterShallow: [0.05, 0.28, 0.3],
    exposure: 1.0,
  },
  dusk: {
    label: 'Dusk',
    sunEl: 3.5, sunAz: 18,
    sunTint: [1.0, 0.42, 0.18],
    zenith: [0.16, 0.1, 0.26],
    horizon: [0.95, 0.4, 0.16],
    falloff: 0.34,
    glow: 1.1, disc: 1.0,
    cloudLit: [1.0, 0.5, 0.3],
    cloudShadow: [0.32, 0.22, 0.32],
    stars: 0.18, moon: 0.0,
    waterDeep: [0.02, 0.045, 0.08],
    waterShallow: [0.11, 0.12, 0.14],
    exposure: 1.0,
  },
  night: {
    label: 'Night',
    sunEl: -14, sunAz: 0,
    sunTint: [0.05, 0.07, 0.12],
    zenith: [0.008, 0.012, 0.03],
    horizon: [0.045, 0.06, 0.1],
    falloff: 0.6,
    glow: 0.0, disc: 0.0,
    cloudLit: [0.1, 0.12, 0.18],
    cloudShadow: [0.02, 0.025, 0.04],
    stars: 1.0, moon: 0.9,
    waterDeep: [0.004, 0.008, 0.014],
    waterShallow: [0.02, 0.05, 0.07],
    exposure: 1.3,
  },
};

// ---------- weather: sea + cloud + visibility character ----------

const WEATHERS = {
  clear: {
    label: 'Clear',
    coverage: 0.08, cloudDensity: 0.55, cloudScale: 1.1, cloudDrift: 0.004,
    desat: 0.0, darken: 1.0, cloudDark: 1.0,
    disc: 1.0, glow: 1.0, stars: 1.0, moon: 1.0,
    fogDensity: 0.0013, veil: 0.05,
    amp: 0.35, chop: 0.7, speed: 1.0,
    foam: 0.15, detail: 0.18, specPower: 720, spec: 1.0,
    rain: 0.0, storminess: 0.0,
  },
  cloudy: {
    label: 'Cloudy',
    coverage: 0.48, cloudDensity: 0.8, cloudScale: 1.2, cloudDrift: 0.01,
    desat: 0.25, darken: 0.9, cloudDark: 0.85,
    disc: 0.55, glow: 0.7, stars: 0.55, moon: 0.8,
    fogDensity: 0.0016, veil: 0.12,
    amp: 0.7, chop: 0.95, speed: 1.0,
    foam: 0.45, detail: 0.3, specPower: 380, spec: 0.8,
    rain: 0.0, storminess: 0.0,
  },
  fog: {
    label: 'Fog',
    coverage: 0.8, cloudDensity: 0.5, cloudScale: 1.4, cloudDrift: 0.006,
    desat: 0.55, darken: 0.92, cloudDark: 1.0,
    disc: 0.0, glow: 0.25, stars: 0.12, moon: 0.3,
    fogDensity: 0.012, veil: 0.85,
    amp: 0.26, chop: 0.6, speed: 0.9,
    foam: 0.1, detail: 0.14, specPower: 500, spec: 0.3,
    rain: 0.0, storminess: 0.0,
  },
  rain: {
    label: 'Rain',
    coverage: 0.85, cloudDensity: 0.95, cloudScale: 1.25, cloudDrift: 0.018,
    desat: 0.5, darken: 0.78, cloudDark: 0.85,
    disc: 0.0, glow: 0.35, stars: 0.1, moon: 0.35,
    fogDensity: 0.0028, veil: 0.3,
    amp: 0.85, chop: 1.1, speed: 1.05,
    foam: 0.6, detail: 0.42, specPower: 200, spec: 0.4,
    rain: 0.8, storminess: 0.25,
  },
  storm: {
    label: 'Storm',
    coverage: 0.98, cloudDensity: 1.15, cloudScale: 1.15, cloudDrift: 0.032,
    desat: 0.6, darken: 0.5, cloudDark: 0.5,
    disc: 0.0, glow: 0.2, stars: 0.0, moon: 0.15,
    fogDensity: 0.0032, veil: 0.32,
    amp: 1.55, chop: 1.25, speed: 1.15,
    foam: 1.0, detail: 0.55, specPower: 140, spec: 0.3,
    rain: 1.0, storminess: 1.0,
  },
};

// ---------- helpers ----------

function dirFrom(elevDeg, azDeg) {
  const el = THREE.MathUtils.degToRad(elevDeg);
  const az = THREE.MathUtils.degToRad(azDeg);
  return new THREE.Vector3(
    Math.sin(az) * Math.cos(el),
    Math.sin(el),
    -Math.cos(az) * Math.cos(el)
  );
}

function gloom(rgb, desat, darken) {
  const c = new THREE.Color(rgb[0], rgb[1], rgb[2]);
  const lum = c.r * 0.299 + c.g * 0.587 + c.b * 0.114;
  c.lerp(new THREE.Color(lum, lum, lum), desat);
  c.multiplyScalar(darken);
  return c;
}

// ---------- combine a time preset with a weather preset ----------

export function computeTarget(timeKey, wxKey) {
  const T = TIMES[timeKey];
  const W = WEATHERS[wxKey];

  const horizon = gloom(T.horizon, W.desat, W.darken);
  const lumGray = (() => {
    const l = horizon.r * 0.299 + horizon.g * 0.587 + horizon.b * 0.114;
    return new THREE.Color(l, l, l);
  })();

  return {
    sunDir: dirFrom(T.sunEl, T.sunAz),
    sunTint: gloom(T.sunTint, W.desat * 0.5, W.darken),
    zenith: gloom(T.zenith, W.desat, W.darken),
    horizon,
    gradFalloff: T.falloff,
    sunDisc: T.disc * W.disc,
    sunGlow: T.glow * W.glow,
    cloudCoverage: W.coverage,
    cloudDensity: W.cloudDensity,
    cloudScale: W.cloudScale,
    cloudDrift: W.cloudDrift,
    cloudLit: gloom(T.cloudLit, W.desat * 0.6, W.darken * W.cloudDark),
    cloudShadow: gloom(T.cloudShadow, W.desat * 0.4, W.cloudDark),
    fogColor: horizon.clone().lerp(lumGray, 0.5),
    fogVeil: W.veil,
    stars: T.stars * W.stars,
    moonDir: dirFrom(12, -26),
    moon: T.moon * W.moon,
    waterDeep: gloom(T.waterDeep, W.desat * 0.7, W.darken),
    waterShallow: gloom(T.waterShallow, W.desat * 0.7, W.darken),
    ampMul: W.amp,
    chopMul: W.chop,
    speedMul: W.speed,
    foamAmount: W.foam,
    detail: W.detail,
    specPower: W.specPower,
    spec: W.spec,
    fogDensity: W.fogDensity,
    rain: W.rain,
    storminess: W.storminess,
    exposure: T.exposure,
  };
}

// ---------- the forecast line ----------

const FORECAST = {
  clear:  { sky: 'clear skies',     wind: 'light airs',      sea: 'sea slight',    vis: 'excellent' },
  cloudy: { sky: 'scattered cloud', wind: 'moderate breeze', sea: 'sea moderate',  vis: 'good' },
  fog:    { sky: 'fog banks',       wind: 'near calm',       sea: 'sea smooth',    vis: 'less than one mile' },
  rain:   { sky: 'steady rain',     wind: 'fresh breeze',    sea: 'sea rough',     vis: 'moderate' },
  storm:  { sky: 'storm force ten', wind: 'violent squalls', sea: 'sea very high', vis: 'very poor' },
};

export function forecastLine(timeKey, wxKey) {
  const f = FORECAST[wxKey];
  const t = TIMES[timeKey].label;
  const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);
  return `${t} — ${f.sky}. ${cap(f.wind)}, ${f.sea}. Visibility ${f.vis}.`;
}

export const TIME_KEYS = Object.keys(TIMES);
export const WEATHER_KEYS = Object.keys(WEATHERS);
