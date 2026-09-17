import * as THREE from 'three';

// High Park constants + the shared ground field. groundH is the ONE floor
// function used by the mesh, grass, rocks, horses and camera alike (SCENE_CONTRACT §6).

export const SADDLE = new THREE.Vector3(0, 38, -340);   /* the gap the light falls through */
export const BASIN_R = 200;                             /* prairie extent */

const hashJ = (x, y) => { const s = Math.sin(x * 127.1 + y * 311.7) * 43758.5453; return s - Math.floor(s); };
export function vnoise2(x, y) {
  const xi = Math.floor(x), yi = Math.floor(y); let xf = x - xi, yf = y - yi;
  xf = xf * xf * (3 - 2 * xf); yf = yf * yf * (3 - 2 * yf);
  const a = hashJ(xi, yi), b = hashJ(xi + 1, yi), c = hashJ(xi, yi + 1), d = hashJ(xi + 1, yi + 1);
  return a + (b - a) * xf + (c - a) * yf + (a - b - c + d) * xf * yf;
}
export const fbmJ = (x, y, o = 4) => { let a = 0.5, s = 0; for (let i = 0; i < o; i++) { s += a * vnoise2(x, y); x = x * 2.03 + 1.3; y = y * 2.01 + 0.7; a *= 0.5; } return s; };

// domain: the basin, roughly |x|<500, -480<z<130 (peaks apron included);
// range: ≈ -8 in the hollows up to ~+24 at the peak apron rim. Owned by Prairie.
export const groundH = (x, z) => {
  const roll = fbmJ(x * 0.011, z * 0.011, 4) * 12 - 6 + Math.sin(x * 0.05) * 1.2;
  const apron = THREE.MathUtils.clamp((-z - 150) / 130, 0, 1); const hollow = -2.5 * Math.exp(-((x - 35) ** 2 + (z + 60) ** 2) / 2400);
  return roll + apron * apron * 30 + hollow;   /* apron caps at a low rim; Peaks supplies the summits */
};

// peak ridge profile (also drives the silhouette ranks)
export const ridged = (x, s) => { let a = 0.5, f = 1, sum = 0, w = 1;
  for (let i = 0; i < 6; i++) { let n = 1 - Math.abs(vnoise2(x * f + s * 13.7, s * 7.1) * 2 - 1); n = n * n * w; w = Math.min(1, n * 1.7); sum += n * a; f *= 2.1; a *= 0.55; } return sum; };
