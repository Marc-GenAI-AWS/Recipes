import * as THREE from 'three';

// Caldera geometry constants, the CPU mirror of the fissure network, and the
// crust height field.
//
// The fissure network is ANALYTIC (pure sin/cos, no hashed noise), so the CPU
// here and the GLSL in prelude.glsl.js agree to float precision. That matters
// more in this world than in any other: the cracks are the light source, so
// vent placement, ember emitters, moss avoidance and the camera all have to
// land on the same seams the shader is setting on fire.

export const SPAN = 300;        // floor plate, x and z
export const BOWL = 118;        // radius of open floor before the wall climbs
export const RIM = 28;          // caldera wall height at the outer edge
export const PAN_Y = 0;         // nominal floor level

// ---- CPU value noise (mirrors the GLSL vnz3/turb3 in form, not bit-for-bit) ----
const hashK = (x, y, z) => { const s = Math.sin(x * 113.5 + y * 271.9 + z * 51.3) * 39718.4531; return s - Math.floor(s); };
const mix1 = (a, b, t) => a + (b - a) * t;
function vnzK(x, y, z) {
  const xi = Math.floor(x), yi = Math.floor(y), zi = Math.floor(z);
  let xf = x - xi, yf = y - yi, zf = z - zi;
  xf = xf * xf * (3 - 2 * xf); yf = yf * yf * (3 - 2 * yf); zf = zf * zf * (3 - 2 * zf);
  const c = (dy, dz) => mix1(hashK(xi, yi + dy, zi + dz), hashK(xi + 1, yi + dy, zi + dz), xf);
  return mix1(mix1(c(0, 0), c(1, 0), yf), mix1(c(0, 1), c(1, 1), yf), zf);
}
export function turbK(x, y, z, o = 4) {
  let a = 0.5, s = 0;
  for (let i = 0; i < o; i++) { s += a * vnzK(x, y, z); x = x * 2.07 + 0.9; y = y * 1.93 + 2.3; z = z * 2.01 + 1.1; a *= 0.5; }
  return s;
}

// ---- the fissure network (mirrored verbatim in prelude.glsl.js) ----
// Two families of curved seams crossing at a shallow angle, the way a caldera
// floor cracks as it sags. riftPhi is ~0 ON a seam; |riftPhi| grows away from it.
export const riftA = (x, z) =>
  Math.sin(x * 0.245 + 1.70 * Math.sin(z * 0.095)) + 0.62 * Math.sin(z * 0.212 - 2.10 * Math.sin(x * 0.086));
export const riftB = (x, z) => {
  const u = x * 0.62 + z * 0.78, v = x * 0.78 - z * 0.62;
  return Math.sin(u * 0.330 + 1.40 * Math.sin(v * 0.117)) + 0.55 * Math.sin(v * 0.171 + 1.10 * Math.sin(u * 0.077));
};
// distance-to-nearest-seam, in phase units (~0.28 per world unit): the seam network
// repeats every ~13 units, so the camera always has cracks in the near field.
export const riftPhi = (x, z) => Math.min(Math.abs(riftA(x, z)), Math.abs(riftB(x, z)) * 1.3);

// domain: |x| <= SPAN/2, |z| <= SPAN/2; range: ~-1 in the seams, up to RIM on the wall.
// Owned by Crust; sampled by Scorch/Plumes placement and the CameraRig.
export const crustH = (x, z) => {
  const roll = 2.6 * (turbK(x * 0.011, 0, z * 0.011, 3) - 0.5) + 0.85 * (turbK(x * 0.058, 4, z * 0.058, 2) - 0.5);
  const seam = -1.15 * Math.max(0, 1 - riftPhi(x, z) / 0.95);    // the cracks are sunken trenches
  let h = PAN_Y + roll + seam;
  const d = Math.hypot(x, z) - BOWL;
  if (d > 0) {
    const climb = Math.min(1, d / 38) ** 0.78;
    const benches = 2.6 * Math.sin(d * 0.34 + 6.0 * turbK(x * 0.02, 7, z * 0.02, 2));
    h += RIM * climb + benches * Math.min(1, d / 9);
  }
  return h;
};

// cool enough for anything to grow: away from every seam and off the bare pan.
export const coolAt = (x, z) => riftPhi(x, z);
export const onFloor = (x, z) => Math.hypot(x, z) < BOWL - 3;

export const UP = new THREE.Vector3(0, 1, 0);
