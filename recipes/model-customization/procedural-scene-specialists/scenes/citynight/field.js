import * as THREE from 'three';

// Street layout for citynight. The CPU noise here mirrors the GLSL noise in the
// prelude so the road mesh, the weeds in the cracks, the pedestrians on the
// pavement and the camera all agree about where the ground is.
//
// This world has no sun. Its light comes from a LATTICE of fixtures standing in
// the street — sodium lamps, vertical neon signs, lit shopfronts — so the layout
// of those fixtures is a geometry constant like any other, and lives here.

export const BLOCK = 240;        // the street runs along z: |z| <= BLOCK/2
export const KERB_X = 7.0;       // roadway half-width — the kerb line
export const FACE_X = 12.6;      // building frontage stands here
export const KERB_Y = 0.34;      // pavement height above the road crown
export const FIX_SP = 15.0;      // fixture spacing along the street
export const NLAMP = 10;         // emitter slots the shaders read (== #define NLAMP in prelude.glsl.js)

const hashC = (x, y, z) => { const s = Math.sin(x * 127.1 + y * 311.7 + z * 74.7) * 43758.5453; return s - Math.floor(s); };
const mixC = (a, b, t) => a + (b - a) * t;
function vnoiseC(x, y, z) {
  const xi = Math.floor(x), yi = Math.floor(y), zi = Math.floor(z); let xf = x - xi, yf = y - yi, zf = z - zi;
  xf = xf * xf * (3 - 2 * xf); yf = yf * yf * (3 - 2 * yf); zf = zf * zf * (3 - 2 * zf);
  const c = (dy, dz) => mixC(hashC(xi, yi + dy, zi + dz), hashC(xi + 1, yi + dy, zi + dz), xf);
  return mixC(mixC(c(0, 0), c(1, 0), yf), mixC(c(0, 1), c(1, 1), yf), zf);
}
export function fbmC(x, y, z, o = 3) {
  let a = 0.5, s = 0;
  for (let i = 0; i < o; i++) { s += a * vnoiseC(x, y, z); x = x * 2.03 + 1.3; y = y * 2.01 + 0.7; z = z * 1.97 + 2.1; a *= 0.5; }
  return s;
}
const sstep = (t) => { t = Math.min(1, Math.max(0, t)); return t * t * (3 - 2 * t); };

// domain: |x| <= 16, |z| <= BLOCK/2; range: 0 in the gutter up to KERB_Y+0.06 at
// the shopfronts. Owned by Blacktop; sampled by Kerbside, Passersby and CameraRig.
export const streetH = (x, z) => {
  const ax = Math.abs(x);
  const wear = 0.055 * (fbmC(x * 0.55, 0.5, z * 0.55, 3) - 0.5);
  if (ax <= KERB_X) {                                   // cambered carriageway, water runs to the gutter
    const t = ax / KERB_X;
    return 0.20 * (1 - t * t) - 0.09 * sstep((t - 0.84) / 0.16) + wear;
  }
  if (ax <= KERB_X + 0.3) return KERB_Y * sstep((ax - KERB_X) / 0.3) + wear * 0.4;   // the kerb face
  if (ax <= FACE_X) return KERB_Y + 0.05 * (ax - KERB_X - 0.3) / (FACE_X - KERB_X) + wear * 0.5;
  return KERB_Y + 0.06;                                 // under the frontage
};

export const onWalk = (x, z) => { const ax = Math.abs(x); return ax > KERB_X + 0.7 && ax < FACE_X - 0.7; };

// ── the light fixtures ────────────────────────────────────────────────────────
// kind 0 sodium lamp on a bracket over the road, 1 vertical neon sign bolted to a
// frontage, 2 a lit shopfront box at street level. Staggered left/right so the two
// pavements never carry the same thing at the same z.
const NEON = [
  [1.00, 0.16, 0.46], [0.20, 0.92, 1.00], [0.34, 1.00, 0.50],
  [1.00, 0.40, 0.10], [0.50, 0.42, 1.00], [1.00, 0.82, 0.26],
];

function buildFixtures() {
  const out = [];
  const kMax = Math.floor(BLOCK / (2 * FIX_SP));
  for (let k = -kMax; k <= kMax; k++) {
    for (let s = -1; s <= 1; s += 2) {
      const z = k * FIX_SP + (s > 0 ? FIX_SP * 0.5 : 0);
      const h = hashC(k * 3.7, s * 1.9, 0.5), h2 = hashC(k * 1.3, s * 5.1, 2.5);
      const kind = (k * 2 + (s > 0 ? 1 : 0) + 9) % 3;
      if (kind === 0) {
        out.push({ kind: 0, x: s * (KERB_X - 0.5), y: 6.3, z, side: s, postX: s * (KERB_X + 0.8),
          c: [1.00, 0.60, 0.22], i: 1.0, sx: 0.8, sy: 0.26, sz: 0.5 });
      } else if (kind === 1) {
        out.push({ kind: 1, x: s * (FACE_X - 1.30), y: 3.9 + h * 3.6, z, side: s, postX: 0,
          c: NEON[Math.floor(h2 * NEON.length) % NEON.length], i: 1.1 + 0.7 * h,
          sx: 0.5, sy: 1.6 + h * 1.6, sz: 1.2 });
      } else {
        out.push({ kind: 2, x: s * (FACE_X - 0.18), y: 2.0, z, side: s, postX: 0,
          c: h2 > 0.55 ? [1.00, 0.90, 0.66] : [0.62, 1.00, 0.86], i: 0.42,
          sx: 0.22, sy: 1.5, sz: 3.2 });
      }
    }
  }
  return out;
}
export const FIXTURES = buildFixtures();

export const UP = new THREE.Vector3(0, 1, 0);
