import * as THREE from 'three';

// Cenote geometry constants + the shared floor height field (CPU noise mirrors
// the GLSL noise so geometry, placement and camera agree). See SCENE_CONTRACT §6.

export const HOLE_ANGLE = 16 * Math.PI / 180;
export const DOME = new THREE.Vector3(26, 19.5, 26);
export const DOME_C = -2;
export const HALO_Y = -13.5;
export const HOLE_R = Math.sin(HOLE_ANGLE) * DOME.x;
export const HOLE_Y = DOME_C + Math.cos(HOLE_ANGLE) * DOME.y;

const hashJ = (x, y, z) => { const s = Math.sin(x * 127.1 + y * 311.7 + z * 74.7) * 43758.5453; return s - Math.floor(s); };
const lerp = (a, b, t) => a + (b - a) * t;
function vnoise(x, y, z) {
  const xi = Math.floor(x), yi = Math.floor(y), zi = Math.floor(z); let xf = x - xi, yf = y - yi, zf = z - zi;
  xf = xf * xf * (3 - 2 * xf); yf = yf * yf * (3 - 2 * yf); zf = zf * zf * (3 - 2 * zf);
  const c = (dy, dz) => lerp(hashJ(xi, yi + dy, zi + dz), hashJ(xi + 1, yi + dy, zi + dz), xf);
  return lerp(lerp(c(0, 0), c(1, 0), yf), lerp(c(0, 1), c(1, 1), yf), zf);
}
export function fbmJ(x, y, z, o = 4) { let a = 0.5, s = 0; for (let i = 0; i < o; i++) { s += a * vnoise(x, y, z); x = x * 2.03 + 1.3; y = y * 2.01 + 0.7; z = z * 1.97 + 2.1; a *= 0.5; } return s; }

// domain: r = hypot(x,z) ≲ 35 (seabed plane is 70×70); range: ≈ -16 (centre) up
// to the rim wall. Owned by Cavern; sampled by Reef/Fish/Bubbles placement.
export const floorH = (x, z) => {
  const r = Math.hypot(x, z);
  return -16 + 1.1 * fbmJ(x * 0.22, 0, z * 0.22, 3) + 0.35 * Math.sin(x * 0.55 + 2.0 * fbmJ(z * 0.3, 3, x * 0.1, 2)) + 0.1 * Math.sin(x * 2.4 + z * 0.9 + 3.0 * fbmJ(x * 0.15, 5, z * 0.15, 2)) + 3.0 * Math.max(0, (r - 20 + 1.5 * fbmJ(x * 0.2, 7, z * 0.2, 2)) / 7) ** 2;
};
