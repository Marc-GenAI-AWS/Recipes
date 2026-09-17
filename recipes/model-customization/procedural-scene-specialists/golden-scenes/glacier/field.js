import * as THREE from 'three';

// Glacier geometry constants + the shared ice-surface height field. The CPU noise
// mirrors the GLSL noise so the mesh, the lichen placement, the spindrift and the
// camera all agree about where the ice is.
//
// The basin runs along z: -z is UP-glacier (the headwall), +z is down toward the
// snout. Ice fills |x - flowline(z)| < EDGE; beyond that the lateral moraine climbs.

export const BASIN = 320;        // length of the basin along z
export const HALF = 112;         // plane half-width in x
export const EDGE = 44;          // half-width of the ice tongue
export const CREST = 58;         // lateral moraine / ridge height
export const HEADW = 74;         // headwall height at the back of the basin
export const MEDIAL = 15;        // x-offset of the medial moraine: rubble riding on the ice

const hashA = (x, y, z) => { const s = Math.sin(x * 127.1 + y * 311.7 + z * 74.7) * 43758.5453; return s - Math.floor(s); };
const lerp = (a, b, t) => a + (b - a) * t;
export const sstep = (a, b, x) => { const t = Math.min(1, Math.max(0, (x - a) / (b - a))); return t * t * (3 - 2 * t); };
function vnoiseA(x, y, z) {
  const xi = Math.floor(x), yi = Math.floor(y), zi = Math.floor(z); let xf = x - xi, yf = y - yi, zf = z - zi;
  xf = xf * xf * (3 - 2 * xf); yf = yf * yf * (3 - 2 * yf); zf = zf * zf * (3 - 2 * zf);
  const c = (dy, dz) => lerp(hashA(xi, yi + dy, zi + dz), hashA(xi + 1, yi + dy, zi + dz), xf);
  return lerp(lerp(c(0, 0), c(1, 0), yf), lerp(c(0, 1), c(1, 1), yf), zf);
}
export function fbmA(x, y, z, o = 4) {
  let a = 0.5, s = 0;
  for (let i = 0; i < o; i++) { s += a * vnoiseA(x, y, z); x = x * 2.03 + 1.3; y = y * 2.01 + 0.7; z = z * 1.97 + 2.1; a *= 0.5; }
  return s;
}

// The ice stream wanders as it comes down the basin.
export const flowline = (z) => 6.0 * Math.sin(z * 0.012) + 2.5 * Math.sin(z * 0.031 + 1.1);

// Crevasse field. Purely analytic (no noise) so the JS mesh and the GLSL
// crevasseMask() agree to the pixel: transverse bands that curve down-glacier and
// open hardest at the margins, where the ice drags against the rock.
export const crevasseT = (x, z) => {
  const xc = x - flowline(z);
  const ph = z * 0.26 + xc * 0.016 + 1.7 * Math.sin(xc * 0.035 + z * 0.011) + 0.9 * Math.sin(z * 0.05 - xc * 0.02);
  const s = Math.sin(z * 0.021 + 1.0);
  const zone = Math.min(1, 0.46 + 0.54 * s * s + 0.50 * sstep(24, 44, Math.abs(xc)));
  // only the glacier cracks. Without this gate the transverse bands climb the
  // headwall and the back of the basin turns into a wedding cake.
  const ice = (1 - sstep(EDGE - 7, EDGE + 3, Math.abs(xc))) * sstep(-BASIN / 2 + 60, -BASIN / 2 + 108, z);
  return (1 - sstep(0.0, 0.38, Math.abs(Math.sin(ph)))) * zone * ice;
};

// domain: |x| <= HALF, |z| <= BASIN/2; range: ~-16 at the snout up to CREST/HEADW.
// Owned by Icefield; sampled by Lichen/Spindrift placement and the CameraRig.
export const iceH = (x, z) => {
  const xc = x - flowline(z);
  const fall = -z * 0.095;                                           // the whole surface tilts down-glacier
  const crown = 3.4 * Math.exp(-(xc * xc) / 1800);                   // glaciers are convex in cross-section
  const swell = 1.7 * fbmA(x * 0.02, 1, z * 0.02, 3)
              + 0.75 * Math.sin(z * 0.085 + 2.0 * fbmA(x * 0.04, 2, z * 0.03, 2));  // ogives and wind swells
  // sastrugi: the wind carves the surface at a few metres, and without it the near
  // foreground is an unreadable white sheet — the one thing this world cannot afford
  const sastrugi = 0.34 * Math.sin(x * 0.62 + 3.0 * fbmA(x * 0.05, 8, z * 0.05, 2))
                 + 0.24 * Math.sin(z * 0.85 + x * 0.25 + 2.0 * fbmA(x * 0.09, 6, z * 0.09, 2))
                 + 0.50 * (fbmA(x * 0.22, 3, z * 0.22, 3) - 0.5);
  const medial = 0.95 * Math.exp(-((xc - MEDIAL) ** 2) / 11) * sstep(-46, 34, z);   // debris stripe on the ice
  // the crevasse profile is raised to a power before it is cut: a crevasse is a
  // narrow slot with near-vertical walls, and a soft wide dip of the same depth
  // reads as a snow dune instead
  let h = fall + crown + swell + sastrugi + medial - 9.0 * crevasseT(x, z) ** 1.9;
  const ht = Math.pow(sstep(-BASIN / 2 + 88, -BASIN / 2 + 4, z), 1.35);            // headwall at the back
  h += HEADW * ht + (17.0 * (fbmA(x * 0.022, 11, z * 0.022, 4) - 0.45)
                   + 6.5 * (fbmA(x * 0.07, 13, z * 0.07, 3) - 0.5)) * ht;
  const d = Math.abs(xc) - EDGE;
  if (d > 0) {
    const climb = Math.min(1, d / 54) ** 0.78;
    // broken rock, not a smooth cone: two octaves of relief carve the skyline
    const rough = 12.0 * (fbmA(x * 0.035, 7, z * 0.035, 4) - 0.45)
                + 7.0 * (fbmA(x * 0.13, 9, z * 0.13, 3) - 0.5);
    const benches = 2.0 * Math.sin(d * 0.34 + 3.0 * fbmA(x * 0.03, 5, z * 0.03, 2));
    h += CREST * climb + (benches + rough) * Math.min(1, d / 9);
  }
  return h;
};

// "is this point out on the open ice" / "is it up on the rock" — for placement code.
export const onIce = (x, z) => Math.abs(x - flowline(z)) < EDGE - 3;
export const onRock = (x, z) => { const d = Math.abs(x - flowline(z)) - EDGE; return d > 1.5 && d < 30; };

export const UP = new THREE.Vector3(0, 1, 0);
