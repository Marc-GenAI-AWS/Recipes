// Glacier GLSL prelude. G = core noise + this world's fields (crevasses, subsurface
// ice glow, snow glint, upwash). VERT_WORLD / FRAG_ICE are the bases every surface
// material derives from by string-surgery. TAIL is the tonemap/colorspace close.
//
// The distinctive field here is upwash(): on a snowfield most of the light on a
// shaded or downward-facing surface arrives from BELOW, reflected off the snow.
// Nothing here is allowed to go black — shadows are blue and filled. A layer that
// shades with a plain lambert term reads as a cut-out pasted onto the glacier.
//
// The second signature is subsurface(): sun enters the ice, scatters, and leaves
// again some metres away, so ice glows cyan from inside rather than reflecting.

export const G = /* glsl */`
uniform float uTime; uniform vec3 uAirC; uniform float uAirD;
uniform vec3 uSolarV, uSolarC; uniform float uSolarI;
uniform vec3 uZenithC, uDomeC; uniform float uDomeI;
uniform vec3 uUpwashC; uniform float uUpwashI;
uniform vec3 uSnowC, uIceC, uMoraineC;
uniform float uIceDepth, uGlareI, uWhiteout, uGlintI, uCrevasse, uDrift, uHaloI, uAlpenI, uLichenD;
uniform float uEdgeX, uCrestY;
uniform vec2 uGustV;
float hsh1(vec3 p){ return fract(sin(dot(p, vec3(127.1, 311.7, 74.7))) * 43758.5453); }
vec2 hsh2(vec2 p){ return fract(sin(vec2(dot(p, vec2(127.1, 311.7)), dot(p, vec2(269.5, 183.3)))) * 43758.5453); }
float vnz3(vec3 p){ vec3 i = floor(p), f = fract(p); f = f*f*(3.0-2.0*f);
  return mix(mix(mix(hsh1(i), hsh1(i+vec3(1,0,0)), f.x), mix(hsh1(i+vec3(0,1,0)), hsh1(i+vec3(1,1,0)), f.x), f.y),
             mix(mix(hsh1(i+vec3(0,0,1)), hsh1(i+vec3(1,0,1)), f.x), mix(hsh1(i+vec3(0,1,1)), hsh1(i+vec3(1,1,1)), f.x), f.y), f.z); }
const mat3 SPIN = mat3(0.58, 0.44, -0.69, -0.69, 0.66, -0.16, 0.44, 0.61, 0.66);
float turb3(vec3 p){ float a = 0.5, s = 0.0; for (int i = 0; i < 4; i++) { s += a * vnz3(p); p = SPIN * p * 2.07 + 1.3; a *= 0.5; } return s; }
float turb2(vec2 p){ return turb3(vec3(p, 0.61)); }

/* where the ice is torn open. Mirrors crevasseT() in field.js exactly (analytic, no
   noise) so the shading sits in the slot the mesh actually dips into. 1 = slot floor. */
float crevasseMask(vec3 p){
  float xc = p.x - (6.0 * sin(p.z * 0.012) + 2.5 * sin(p.z * 0.031 + 1.1));
  float ph = p.z * 0.26 + xc * 0.016 + 1.7 * sin(xc * 0.035 + p.z * 0.011) + 0.9 * sin(p.z * 0.05 - xc * 0.02);
  float s = sin(p.z * 0.021 + 1.0);
  float zone = min(1.0, 0.46 + 0.54 * s * s + 0.50 * smoothstep(24.0, 44.0, abs(xc)));
  /* only the glacier cracks — the rock margins and the headwall do not */
  float ice = (1.0 - smoothstep(uEdgeX - 7.0, uEdgeX + 3.0, abs(xc))) * smoothstep(-100.0, -52.0, p.z);
  return (1.0 - smoothstep(0.0, 0.38, abs(sin(ph)))) * zone * ice * uCrevasse;
}

/* how much bare rock the surface shows: the lateral moraine, and anything too steep
   to hold snow on the headwall. */
float moraineF(vec3 p, vec3 n){
  float xc = p.x - (6.0 * sin(p.z * 0.012) + 2.5 * sin(p.z * 0.031 + 1.1));
  float lat = smoothstep(uEdgeX - 4.0, uEdgeX + 8.0, abs(xc));
  /* steep ground is bare rock ONLY up on the headwall. Ungated, this test also
     catches every crevasse wall and every serac flank and paints the ice grey —
     which quietly destroys the one thing this world is for. */
  float steep = smoothstep(0.80, 0.40, n.y) * (1.0 - smoothstep(-100.0, -56.0, p.z));
  /* the medial moraine: a stripe of rubble the ice carries down the middle */
  float med = smoothstep(4.2, 1.4, abs(xc - 15.0)) * smoothstep(-46.0, -14.0, p.z);
  return clamp(max(max(lat, steep), med) * (0.45 + 1.05 * turb2(p.xz * 0.055 + 4.0)), 0.0, 1.0);
}

/* THE signature: light that went INTO the ice and came back out. Cyan, strongest
   where the path is long (crevasse walls, serac flanks) and where the sun is behind
   the surface rather than on it. */
vec3 subsurface(vec3 p, vec3 n){
  float cv = crevasseMask(p);
  float path = uIceDepth * (0.30 + 1.8 * cv + 0.5 * turb3(p * 0.07 + 2.0));
  float enter = 0.30 + 0.70 * max(dot(n, -uSolarV), 0.0);
  float leave = 0.45 + 0.55 * max(dot(normalize(cameraPosition - p), n), 0.0);
  return uIceC * path * enter * leave * (0.35 + 0.85 * uSolarI);
}

/* light bounced back UP off the snow. On a glacier this is the dominant fill: it
   lands on every downward-facing surface and keeps shadows blue instead of black. */
vec3 upwash(vec3 p, vec3 n){
  float down = 0.5 - 0.5 * n.y;
  float open = 1.0 - 0.55 * crevasseMask(p);
  return uUpwashC * uUpwashI * (0.30 + 1.05 * down) * open;
}

/* individual crystals catching the sun: a sparse quantised twinkle, not a specular
   sheen. Held near the camera, where a real snowfield glitters. */
float snowGlint(vec3 p, vec3 n){
  vec3 v = normalize(cameraPosition - p);
  vec3 hv = normalize(v - uSolarV);
  float sp = pow(max(dot(n, hv), 0.0), 60.0);
  float g = hsh1(floor(p * 22.0) + 0.5);
  float tw = 0.5 + 0.5 * sin(uTime * 3.4 + g * 62.8);
  float facet = smoothstep(0.972, 0.998, g * (0.55 + 0.45 * tw));
  float near = smoothstep(110.0, 12.0, distance(p, cameraPosition));
  return uGlintI * near * (sp * 0.45 + facet * 2.6 * pow(max(dot(n, hv), 0.0), 3.0));
}

/* thin, clean, high-altitude air: weak with distance but very bright, and it goes
   opaque the moment cloud drops into the basin. */
vec3 aerial(vec3 col, vec3 p){ float d = distance(p, cameraPosition);
  float k = uAirD * (1.0 + 3.2 * uWhiteout);
  return mix(col, uAirC, 1.0 - exp(-d * d * k * k)); }
float aerialAtt(vec3 p){ float d = distance(p, cameraPosition);
  float k = uAirD * (1.0 + 3.2 * uWhiteout); return exp(-d * d * k * k); }

/* katabatic wind pouring off the ice, used by spindrift and the moss cushions. */
vec2 gustAt(vec3 p){ return uGustV * (0.55 + 0.9 * turb2(p.xz * 0.03 + uTime * 0.09)); }
`;

export const VERT_WORLD = /* glsl */`
varying vec3 vP, vN; uniform float uFlex; uniform float uTime; uniform vec2 uGustV;
void main(){
  #ifdef USE_INSTANCING
  mat4 m = modelMatrix * instanceMatrix;
  #else
  mat4 m = modelMatrix;
  #endif
  vec3 q = position;
  if (uFlex > 0.0) { float s = clamp(q.y, 0.0, 1.0); s *= s;
    q.xz += uFlex * s * (uGustV * 0.5 + vec2(sin(uTime * 2.3 + q.z * 3.0), cos(uTime * 1.9 + q.x * 3.0)) * 0.18); }
  vec4 wp = m * vec4(q, 1.0);
  vP = wp.xyz; vN = normalize(mat3(m) * normal); gl_Position = projectionMatrix * viewMatrix * wp; }`;

export const FRAG_ICE = G + /* glsl */`
varying vec3 vP, vN; uniform float uGrit, uBare, uRocky;
void main(){ vec3 p = vP;
  /* near-field relief matters more here than anywhere: a snowfield with no grain in
     the foreground is a sheet of white paper, and this world has nothing darker to
     hide that behind */
  float near = smoothstep(95.0, 6.0, distance(p, cameraPosition));
  vec3 n = normalize(normalize(vN)
    + 0.26 * vec3(vnz3(p * 0.55 + 1.0) - 0.5, vnz3(p * 0.55 + 2.0) - 0.5, vnz3(p * 0.55 + 3.0) - 0.5)
    + 0.16 * vec3(vnz3(p * 2.4 + 1.0) - 0.5, vnz3(p * 2.4 + 2.0) - 0.5, vnz3(p * 2.4 + 3.0) - 0.5)
    + near * 0.30 * vec3(vnz3(p * 4.6 + 1.0) - 0.5, vnz3(p * 4.6 + 5.0) - 0.5, vnz3(p * 4.6 + 9.0) - 0.5)
    + near * 0.16 * vec3(vnz3(p * 15.0) - 0.5, vnz3(p * 15.0 + 4.0) - 0.5, vnz3(p * 15.0 + 8.0) - 0.5)
    /* wind ripple: sastrugi lie in ranks across the basin, not at random */
    + near * 0.22 * vec3(sin(p.x * 2.9 + 2.5 * turb2(p.xz * 0.35)), 0.0, sin(p.z * 2.1 + p.x * 0.7)));
  float cv = crevasseMask(p);
  float rockF = moraineF(p, n) * uRocky;
  /* wind-scoured blue ice where the snow cover thins, and inside every crevasse */
  float bare = clamp(uBare * (0.35 + 0.9 * turb3(p * 0.09 + 7.0)) + 0.85 * cv, 0.0, 1.0);
  /* wind-combed streaks: stretched along x, the way sastrugi lie across the basin */
  vec3 snow = uSnowC * (0.90 + 0.16 * turb3(p * 0.30))
            * (1.0 - 0.13 * uGrit * turb3(vec3(p.x * 2.1, p.y * 0.7, p.z * 0.50)))
            * (1.0 - 0.07 * uGrit * turb3(p * 6.5));
  /* bare ice is layered: annual bands of bubbles and dust, near-horizontal, which is
     what stops a serac reading as a sheet of coloured card */
  vec3 blue = mix(uSnowC * 0.88, uIceC, 0.33)
            * (0.74 + 0.52 * turb3(vec3(p.x * 0.75, p.y * 3.4, p.z * 0.75) + 5.0));
  vec3 rock = uMoraineC * (0.55 + 0.85 * turb3(p * 0.40 + 3.0)) * (0.80 + 0.30 * turb3(p * 1.7));
  vec3 base = mix(mix(snow, blue, bare), rock, rockF) * (1.0 - 0.42 * cv);
  float lam = max(dot(n, -uSolarV), 0.0);
  float shade = 1.0 - 0.90 * cv;                                       /* slots see almost no sun */
  vec3 light = uSolarC * uSolarI * lam * shade * (1.0 - 0.72 * uWhiteout)
             + uDomeC * uDomeI * (0.38 + 0.62 * max(n.y, 0.0)
                 + 0.40 * max(dot(n, normalize(vec3(-uSolarV.x, 0.3, -uSolarV.z))), 0.0)) * (1.0 - 0.78 * cv)
             + upwash(p, n);
  /* a grazing view through the surface of clean ice goes bright at the edge */
  float fres = pow(1.0 - clamp(dot(n, normalize(cameraPosition - p)), 0.0, 1.0), 3.0);
  vec3 col = base * light
           + mix(uSnowC, uIceC, 0.55) * fres * bare * (0.20 + 0.60 * uDomeI + 0.25 * uSolarI)
           + subsurface(p, n) * (0.22 + 0.70 * bare + 1.0 * cv) * (1.0 - 0.85 * rockF)
           + uSolarC * snowGlint(p, n) * (1.0 - rockF) * (1.0 - 0.7 * bare);
  gl_FragColor = vec4(aerial(col, p), 1.0);
  #include <tonemapping_fragment>
  #include <colorspace_fragment>
}`;

export const TAIL = /* glsl */`
  #include <tonemapping_fragment>
  #include <colorspace_fragment>
}`;
