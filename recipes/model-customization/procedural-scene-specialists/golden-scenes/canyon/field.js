import * as THREE from 'three';

// Canyon geometry constants + the shared floor/wall height field. The CPU noise
// mirrors the GLSL noise so geometry, scrub placement and the camera agree.

export const LEN = 260;          // corridor runs along -z
export const HALF = 46;          // plane half-width in x
export const RIM = 34;           // wall height at the rim
export const FLOOR_Y = 0;        // nominal floor

const hashJ = (x, y, z) => { const s = Math.sin(x * 127.1 + y * 311.7 + z * 74.7) * 43758.5453; return s - Math.floor(s); };
const lerp = (a, b, t) => a + (b - a) * t;
function vnoise(x, y, z) {
  const xi = Math.floor(x), yi = Math.floor(y), zi = Math.floor(z); let xf = x - xi, yf = y - yi, zf = z - zi;
  xf = xf * xf * (3 - 2 * xf); yf = yf * yf * (3 - 2 * yf); zf = zf * zf * (3 - 2 * zf);
  const c = (dy, dz) => lerp(hashJ(xi, yi + dy, zi + dz), hashJ(xi + 1, yi + dy, zi + dz), xf);
  return lerp(lerp(c(0, 0), c(1, 0), yf), lerp(c(0, 1), c(1, 1), yf), zf);
}
export function fbmJ(x, y, z, o = 4) {
  let a = 0.5, s = 0;
  for (let i = 0; i < o; i++) { s += a * vnoise(x, y, z); x = x * 2.03 + 1.3; y = y * 2.01 + 0.7; z = z * 1.97 + 2.1; a *= 0.5; }
  return s;
}

// The corridor meanders in x as it runs along z, and pinches and opens.
export const meander = (z) => 7.5 * Math.sin(z * 0.021) + 3.2 * Math.sin(z * 0.047 + 1.7);
export const halfWidth = (z) => 9.5 + 4.5 * Math.sin(z * 0.033 + 0.6) + 2.0 * fbmJ(0, 3, z * 0.05, 2);

// domain: |x| <= HALF, |z| <= LEN/2; range: ~0 on the floor up to RIM at the rim.
// Owned by Walls; sampled by Scrub/Dust placement and the CameraRig.
export const canyonH = (x, z) => {
  const d = Math.abs(x - meander(z)) - halfWidth(z);           // <0 inside the slot
  const floor = 0.55 * fbmJ(x * 0.08, 0, z * 0.08, 3) + 0.22 * Math.sin(z * 0.3 + 2.0 * fbmJ(x * 0.2, 1, z * 0.1, 2));
  if (d <= 0) return FLOOR_Y + floor;
  const climb = Math.min(1, d / 26) ** 0.72;                    // steep near the base, easing to the rim
  const ledges = 1.6 * Math.sin(d * 0.55 + 3.0 * fbmJ(x * 0.05, 5, z * 0.05, 2));
  return FLOOR_Y + floor + RIM * climb + ledges * Math.min(1, d / 8);
};

// A convenient "is this point on the open floor" test for placement code.
export const inSlot = (x, z) => Math.abs(x - meander(z)) < halfWidth(z) - 1.2;

export const UP = new THREE.Vector3(0, 1, 0);
