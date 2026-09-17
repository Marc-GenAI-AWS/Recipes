// Citynight GLSL prelude. G = core noise + this world's fields: the emitter array
// that stands in for a sun, the water film on the road, and the sodium murk in the
// air. VERT_WORLD / FRAG_TARMAC / FRAG_BRICK are the bases every other material
// derives from by string-surgery. TAIL is the tonemap/colorspace close.
//
// The distinctive field here is the uEmi* array. There is no uSunDir: light arrives
// from NLAMP point sources at street level, each with its own colour, and the road
// is a mirror that doubles every one of them. A layer that shades against a single
// key direction will look like it was lit in a different world.

export const G = /* glsl */`
#define NLAMP 10
uniform float uTime;
uniform vec3 uEmiP[NLAMP];            /* world position of each artificial source */
uniform vec3 uEmiC[NLAMP];            /* its colour — sodium amber, neon, shopfront white */
uniform float uEmiI[NLAMP];           /* its output; 0 means the slot is unused */
uniform vec3 uMurkC; uniform float uMurkD;
uniform vec3 uGlowC; uniform float uGlowI;      /* the overcast lid, lit from below by the city */
uniform vec3 uNeonC;                  /* the dominant sign colour — what the wet air takes on */
uniform float uNeonI;                 /* master gain on every artificial source */
uniform float uLampI;                 /* sodium output */
uniform float uSignI;                 /* neon + shopfront output */
uniform vec3 uWinC; uniform float uWinI; uniform float uWinOcc;
uniform vec3 uTarC; uniform float uGrime;
uniform float uWetness;               /* 0 dry tarmac .. 1 standing water */
uniform float uRipple;                /* how hard the rain chops the film up */
uniform float uRainAmt; uniform float uHaloR; uniform float uStarI;
uniform float uKerbX; uniform float uFaceX;
uniform vec2 uGust;

float hash1(vec3 p){ return fract(sin(dot(p, vec3(127.1, 311.7, 74.7))) * 43758.5453); }
vec2 hash2(vec2 p){ return fract(sin(vec2(dot(p, vec2(127.1, 311.7)), dot(p, vec2(269.5, 183.3)))) * 43758.5453); }
float noise3(vec3 p){ vec3 i = floor(p), f = fract(p); f = f*f*(3.0-2.0*f);
  return mix(mix(mix(hash1(i), hash1(i+vec3(1,0,0)), f.x), mix(hash1(i+vec3(0,1,0)), hash1(i+vec3(1,1,0)), f.x), f.y),
             mix(mix(hash1(i+vec3(0,0,1)), hash1(i+vec3(1,0,1)), f.x), mix(hash1(i+vec3(0,1,1)), hash1(i+vec3(1,1,1)), f.x), f.y), f.z); }
const mat3 TUMBLE = mat3(0.36, 0.48, -0.8, -0.8, 0.6, 0.0, 0.48, 0.64, 0.6);
float fbm3(vec3 p){ float a = 0.5, s = 0.0; for (int i = 0; i < 4; i++) { s += a * noise3(p); p = TUMBLE * p * 2.03 + 1.7; a *= 0.5; } return s; }
float fbm2(vec2 p){ return fbm3(vec3(p, 0.37)); }

/* where the water actually stands: broad pools smeared along the street, found
   only in the low camber and the gutters. 0 on the pavement, 1 in a puddle. */
float puddleMask(vec3 p){
  float b = fbm2(p.xz * vec2(0.24, 0.085) + 3.7);
  float low = smoothstep(0.30, 0.02, p.y);
  return smoothstep(0.44, 0.64, b) * low * uWetness;
}

/* one lattice of spreading raindrop rings on standing water */
float ringsAt(vec2 q, float ph){
  vec2 i = floor(q), f = fract(q) - 0.5;
  vec2 c = (hash2(i + ph) - 0.5) * 0.7;
  float t = fract(uTime * 1.25 + hash2(i + ph + 5.0).y);
  return smoothstep(0.045, 0.0, abs(length(f - c) - t * 0.45)) * (1.0 - t);
}
float dropRings(vec2 q){ return (ringsAt(q, 0.0) + ringsAt(q * 1.7 + 3.1, 2.0)) * uRainAmt; }

/* the normal of the water film: near-mirror, chopped by wind chop and by the rings
   the rain punches into it. This is what smears a sign into a streak. */
vec3 slickN(vec3 p, vec3 n){
  vec2 q = p.xz * vec2(2.4, 1.1); float e = 0.30;
  float d0 = fbm2(q + uTime * 0.6);
  vec2 chop = vec2(d0 - fbm2(q + vec2(e, 0.0) + uTime * 0.6),
                   fbm2(q + vec2(0.0, e) + uTime * 0.6) - d0);
  float r = dropRings(p.xz * 1.15);
  return normalize(n + vec3(chop.x, 0.0, chop.y) * (0.5 + 3.0 * r) * uRipple);
}

/* the sum of every artificial source falling on a surface. This replaces the sun:
   a wrapped diffuse term so nothing facing away goes absolutely black, and an
   inverse-square falloff so a figure standing under a sign is lit by that sign. */
vec3 neonGlow(vec3 p, vec3 n){
  vec3 acc = vec3(0.0);
  for (int i = 0; i < NLAMP; i++){
    vec3 d = uEmiP[i] - p; float r = length(d);
    acc += uEmiC[i] * (uEmiI[i] / (1.0 + 0.34 * r * r)) * (0.04 + 0.96 * max(dot(n, d / max(r, 0.001)), 0.0));
  }
  return acc * uNeonI;
}

/* and the same sources seen IN the road rather than on it — the mirror image of
   every light, stretched by the chop into a vertical streak. The signature of
   this world: kill this term and a rain-wet street reads as dry grey tarmac. */
vec3 wetSpec(vec3 p, vec3 n){
  vec3 V = normalize(cameraPosition - p);
  vec3 R = reflect(-V, n);
  vec2 rh = R.xz / max(length(R.xz), 0.001);
  /* the lobe is deliberately ANISOTROPIC: narrow across the street, long along it.
     That is what turns a point source into the streak you actually see lying in a
     wet road. An isotropic highlight gives you a dot, and a dot is not a world. */
  float across = mix(40.0, 700.0, uWetness);
  float along = mix(16.0, 3.2, uWetness);
  vec3 acc = vec3(0.0);
  for (int i = 0; i < NLAMP; i++){
    vec3 d = uEmiP[i] - p; float r = length(d); vec3 L = d / max(r, 0.001);
    float az = dot(rh, L.xz / max(length(L.xz), 0.001));
    float el = R.y - L.y;
    acc += uEmiC[i] * uEmiI[i] * pow(max(az, 0.0), across) * exp(-el * el * along) / (1.0 + 0.05 * r * r);
  }
  float fres = pow(1.0 - clamp(dot(n, V), 0.0, 1.0), 4.0);   /* a mirror at a grazing angle, tar straight down */
  return acc * (0.06 + 0.95 * fres) * (0.15 + 0.85 * uWetness) * 0.42;
}

/* the only "sky" light there is: sodium bounced off the cloud lid and back down. */
vec3 skyBounce(vec3 n){ return uGlowC * uGlowI * (0.32 + 0.68 * clamp(n.y * 0.5 + 0.5, 0.0, 1.0)); }

/* wet air: thickens with the rain, and takes the colour of the signs it hangs in. */
vec3 murk(vec3 col, vec3 p){
  float d = distance(p, cameraPosition);
  float k = uMurkD * (1.0 + 0.8 * uRainAmt);
  vec3 m = uMurkC * mix(vec3(1.0), uNeonC, 0.18 * uHaloR) * (0.80 + 0.35 * uHaloR);
  return mix(col, m, clamp(1.0 - exp(-d * d * k * k), 0.0, 1.0));
}
float murkAtt(vec3 p){ float d = distance(p, cameraPosition);
  float k = uMurkD * (1.0 + 0.8 * uRainAmt); return exp(-d * d * k * k); }

/* wind funnelled down the street: slants the rain and shakes the street trees. */
vec2 gustAt(vec3 p){ return uGust * (0.7 + 0.6 * fbm2(p.xz * 0.05 + uTime * 0.11)); }
`;

export const VERT_WORLD = /* glsl */`
varying vec3 vP, vN; uniform float uSway; uniform float uTime; uniform vec2 uGust;
void main(){
  #ifdef USE_INSTANCING
  mat4 m = modelMatrix * instanceMatrix;
  #else
  mat4 m = modelMatrix;
  #endif
  vec4 wp = m * vec4(position, 1.0);
  if (uSway > 0.0) { float s = clamp(wp.y / 5.0, 0.0, 1.0); s *= s;
    wp.xz += uSway * s * (uGust * 0.9 + vec2(sin(uTime * 1.9 + wp.z * 0.45), cos(uTime * 1.5 + wp.x * 0.55)) * 0.28); }
  vP = wp.xyz; vN = normalize(mat3(m) * normal); gl_Position = projectionMatrix * viewMatrix * wp; }`;

/* The road, the kerb and the pavement in one shader: dry aggregate where the water
   has run off, a chopped mirror where it has not, and painted lines so the surface
   reads as a carriageway and not as grey ground. */
export const FRAG_TARMAC = G + /* glsl */`
varying vec3 vP, vN; uniform float uAggr;
void main(){ vec3 p = vP; vec3 g = normalize(vN);
  float ax = abs(p.x);
  vec3 bump = vec3(noise3(p * 7.0) - 0.5, 0.0, noise3(p * 7.0 + 4.0) - 0.5) * 0.50
            + vec3(noise3(p * 26.0) - 0.5, 0.0, noise3(p * 26.0 + 7.0) - 0.5) * 0.20;
  vec3 nd = normalize(g + bump * uAggr);
  float pool = puddleMask(p);
  float wet = clamp(pool + 0.34 * uWetness, 0.0, 1.0);
  vec3 n = normalize(mix(nd, slickN(p, g), wet));

  vec3 base = uTarC * (0.78 + 0.34 * fbm3(p * 1.7) + 0.16 * noise3(p * 14.0));
  if (ax > uKerbX) {                                    /* flagstone pavement */
    vec2 c = vec2(p.x, p.z) / vec2(1.6, 1.95);
    vec2 j = abs(fract(c) - 0.5);
    float joint = smoothstep(0.42, 0.50, max(j.x, j.y));
    base = mix(vec3(0.34, 0.335, 0.33), vec3(0.11, 0.11, 0.12), joint) * (0.72 + 0.55 * fbm3(p * 1.4));
  } else {                                              /* carriageway paint */
    float dash = smoothstep(0.17, 0.10, ax) * step(0.55, fract(p.z * 0.19));
    float edge = smoothstep(0.22, 0.14, abs(ax - (uKerbX - 0.7)));
    float paint = clamp(dash + edge, 0.0, 1.0) * (0.45 + 0.55 * fbm2(p.xz * 2.6));
    base = mix(base, vec3(0.70, 0.66, 0.50), paint * (1.0 - 0.4 * uGrime));
  }
  base *= 1.0 - 0.30 * uGrime;
  base = mix(base, base * 0.15, wet * 0.92);             /* wet stone is dark stone */

  vec3 lit = base * (skyBounce(n) + neonGlow(p, n)) + wetSpec(p, n) * mix(0.10, 1.0, wet);
  lit += uEmiC[0] * uEmiI[0] * 0.006 * dropRings(p.xz * 1.15) * pool;   /* ring crests catch a highlight */
  gl_FragColor = vec4(murk(lit, p), 1.0);
  #include <tonemapping_fragment>
  #include <colorspace_fragment>
}`;

/* Frontage: soot-dark masonry carrying a grid of windows, some of them lit. The
   windows are the other half of this world's lighting — hundreds of small warm
   sources stacked above the street. aFace = (seed, lit fraction, storey offset). */
export const FRAG_BRICK = G + /* glsl */`
varying vec3 vP, vN; varying vec3 vFace; uniform vec3 uBrickC; uniform float uPane;
void main(){ vec3 p = vP; vec3 n = normalize(vN);
  vec2 fc = (abs(n.x) > 0.5) ? vec2(p.z, p.y) : vec2(p.x, p.y);
  vec2 cu = vec2(fc.x / 2.45, (fc.y - 2.6 - vFace.z) / 3.15);
  vec2 cell = floor(cu), f = fract(cu);

  /* How big is one window cell on screen? fwidth() answers that directly, in cell
     units per pixel. Below ~0.5 the grid is finer than the pixel grid sampling it,
     which is the Nyquist limit: drawn crisply it moires, and the moire crawls as the
     camera moves, which reads as flicker rather than as detail. View angle and
     distance are only proxies for this quantity - they miss the dependence on FOV,
     resolution and the pattern's own scale, so they under-correct exactly where it
     matters most. Measure the footprint instead, and widen the pane edges by it so
     the edges filter themselves instead of shimmering. */
  vec2 w = fwidth(cu);
  float foot = max(w.x, w.y);
  float res = smoothstep(0.62, 0.18, foot);          /* 1 = resolvable, 0 = sub-pixel */
  float ax = clamp(w.x * 1.4, 0.0, 0.34), ay = clamp(w.y * 1.4, 0.0, 0.30);
  float pane = smoothstep(0.14 - ax, 0.22 + ax, f.x) * smoothstep(0.86 + ax, 0.78 - ax, f.x)
             * smoothstep(0.24 - ay, 0.32 + ay, f.y) * smoothstep(0.88 + ay, 0.80 - ay, f.y);
  float r = hash1(vec3(cell, vFace.x * 37.0));
  float on = step(1.0 - vFace.y * uWinOcc * uPane, r) * step(3.2, fc.y);
  float tv = 1.0 + 0.55 * step(0.90, fract(r * 13.0)) * sin(uTime * 6.5 + r * 40.0);
  vec3 wc = mix(uWinC, vec3(0.52, 0.72, 1.00), step(0.78, fract(r * 7.0)));
  vec3 emis = wc * uWinI * pane * on * tv;

  /* brick courses alias for the same reason; fade them out once a course is sub-pixel */
  float course = 0.95 + 0.05 * sin(fc.y * 12.0) * smoothstep(0.5, 0.12, fwidth(fc.y) * 12.0);
  float streak = 0.80 + 0.36 * fbm2(vec2(fc.x * 0.9, fc.y * 0.08));  /* rain runs down the render */
  float soot = 0.55 + 0.6 * fbm3(p * 0.55) - 0.35 * smoothstep(14.0, 2.0, p.y) * uGrime;
  vec3 wall = uBrickC * course * streak * (0.7 + 0.7 * fract(vFace.x * 5.0)) * clamp(soot, 0.15, 1.6);

  /* the ground floor is glazed, not bricked: a band of shopfront between mullions,
     dark where the shutters are down and lit where they are not */
  float shop = smoothstep(3.3, 3.0, fc.y) * smoothstep(0.25, 0.55, fc.y);
  float bay = fract(fc.x / 1.7);
  float mull = smoothstep(0.10, 0.17, bay) * smoothstep(0.93, 0.86, bay);
  float shopOn = clamp(step(0.40, hash1(vec3(floor(fc.x / 1.7), 3.0, vFace.x * 11.0))) * uWinOcc * 2.4, 0.0, 1.0);
  wall = mix(wall, wall * 0.30, shop);
  emis += uWinC * uWinI * 0.55 * shop * mull * shopOn;

  /* Collapse the grid into its own average wherever it can no longer be drawn
     honestly. res is the measured footprint test above, not a proxy for it, so the
     crossover lands where the aliasing actually starts regardless of FOV or distance.
     (No backticks in this file: every shader here lives inside a JS template literal,
     and one stray backtick ends the literal and breaks the whole module.) */
  vec3 soft = uWinC * uWinI * uWinOcc * vFace.y * (0.26 * step(3.2, fc.y) + 0.22 * shop);
  emis = mix(soft, emis, res);
  wall = mix(uBrickC * clamp(soot, 0.15, 1.6) * (0.7 + 0.7 * fract(vFace.x * 5.0)), wall, 0.30 + 0.70 * res);

  vec3 col = wall * (skyBounce(n) + neonGlow(p, n) * 0.85) + emis;
  gl_FragColor = vec4(murk(col, p), 1.0);
  #include <tonemapping_fragment>
  #include <colorspace_fragment>
}`;

export const TAIL = /* glsl */`
  #include <tonemapping_fragment>
  #include <colorspace_fragment>
}`;
