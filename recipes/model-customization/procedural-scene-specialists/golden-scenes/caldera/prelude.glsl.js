// Caldera GLSL prelude.
//
// G = core noise + this world's fields. VERT_WORLD / FRAG_CRUST are the bases
// every solid material derives from by string-surgery. TAIL closes main().
//
// The distinctive field here is fireLight(): in a caldera the light comes UP off
// the floor. Faces that point DOWN are the lit ones, vertical faces catch the
// grazing spill, and up-facing tops are the darkest part of any object. Anything
// shaded with a conventional sky-over-ground model reads as if it were pasted in
// from a different world — which, in this set, it would have been.

export const G = /* glsl */`
uniform float uTime;
uniform vec3 uAshC; uniform float uAshD, uAshFall;
uniform vec3 uVaultC; uniform float uVaultI;
uniform vec3 uPaleDir, uPaleC; uniform float uPaleI;
uniform vec3 uLavaC, uCrustC, uSulphC;
uniform float uCrackI, uCrackW, uFireI, uGlowH, uWarp;
uniform float uSteamI, uSparkI, uScorch, uStarI, uBowlR, uRimY;
uniform vec2 uGust;

float hashV(vec3 p){ return fract(sin(dot(p, vec3(113.5, 271.9, 51.3))) * 39718.4531); }
vec2 hash2V(vec2 p){ return fract(sin(vec2(dot(p, vec2(113.5, 271.9)), dot(p, vec2(197.3, 83.1)))) * 39718.4531); }
float vnz3(vec3 p){ vec3 i = floor(p), f = fract(p); f = f*f*(3.0-2.0*f);
  return mix(mix(mix(hashV(i), hashV(i+vec3(1,0,0)), f.x), mix(hashV(i+vec3(0,1,0)), hashV(i+vec3(1,1,0)), f.x), f.y),
             mix(mix(hashV(i+vec3(0,0,1)), hashV(i+vec3(1,0,1)), f.x), mix(hashV(i+vec3(0,1,1)), hashV(i+vec3(1,1,1)), f.x), f.y), f.z); }
const mat3 TUMBLE = mat3(0.60, 0.48, -0.64, -0.64, 0.75, 0.16, 0.48, 0.45, 0.75);
float turb3(vec3 p){ float a = 0.5, s = 0.0; for (int i = 0; i < 4; i++) { s += a * vnz3(p); p = TUMBLE * p * 2.07 + 1.3; a *= 0.5; } return s; }
float turb2(vec2 p){ return turb3(vec3(p, 0.61)); }

/* ── the fissure network. Mirrored exactly in field.js so the CPU and the GPU
      put the cracks in the same places. riftPhi ~ 0 means "on a seam". ── */
float riftA(vec2 q){ return sin(q.x*0.245 + 1.70*sin(q.y*0.095)) + 0.62*sin(q.y*0.212 - 2.10*sin(q.x*0.086)); }
float riftB(vec2 q){ float u = q.x*0.62 + q.y*0.78, v = q.x*0.78 - q.y*0.62;
  return sin(u*0.330 + 1.40*sin(v*0.117)) + 0.55*sin(v*0.171 + 1.10*sin(u*0.077)); }
float riftPhi(vec2 q){ return min(abs(riftA(q)), abs(riftB(q))*1.3); }

/* the seam distance the emission and the irradiance both key off, with the phase
   meandered and frayed by noise so no crack is a drawn curve. Factored out so
   crackAmt() and crackGlow() can never drift apart. */
float seamD(vec2 q){ return riftPhi(q) + 0.26*(turb2(q*0.11) - 0.5) + 0.10*(turb2(q*0.62) - 0.5); }

/* not every seam is live. A slow field over the pan leaves whole quarters crusted
   over and black while others run open, so the network reads as cooling rock with
   fire in it rather than as a lit wireframe laid over a plane. */
float heatAt(vec2 q){ return 0.16 + 0.84*smoothstep(0.30, 0.72, turb2(q*0.016 + 21.0)); }

/* only the sunken pan is cracked; the caldera wall is cold rock. */
float panMask(vec2 q){ return smoothstep(uBowlR*1.02, uBowlR*0.78, length(q)); }

/* how molten the floor is at q: 1 in the open seam, 0 on cold crust. Breathes,
   because a fissure is a convecting slot and not a neon strip. */
float crackAmt(vec2 q){
  float d = seamD(q);
  float breath = 0.68 + 0.32*sin(uTime*0.55 + q.x*0.048 + q.y*0.031);
  return smoothstep(uCrackW, 0.0, d) * breath * heatAt(q) * panMask(q);
}

/* the emissive colour of the floor at q: white-hot in the seam, cooling out
   through the crust shoulders. This is the whole world's light source. */
vec3 crackGlow(vec2 q){
  float d = seamD(q);
  float core = smoothstep(uCrackW, 0.0, d);
  /* chilled crust rafts floating on the melt: without them a seam is a neon tube */
  core *= mix(0.16, 1.0, smoothstep(0.32, 0.60, turb2(q*0.85 + 13.0)));
  float shoulder = smoothstep(uCrackW*3.5, uCrackW*0.5, d);
  float churn = clamp(0.40 + 1.05*turb2(q*0.55 + vec2(0.0, uTime*0.22)), 0.35, 1.25);
  vec3 hot = mix(uLavaC, vec3(1.0, 0.88, 0.60), smoothstep(0.80, 1.35, core*churn));
  return uCrackI * panMask(q) * heatAt(q) * (hot*core*churn*0.90 + uLavaC*shoulder*0.055);
}

/* ── THE INVERSION ──
   Irradiance arriving from the GROUND. Sampled at a few lateral offsets so a
   point is lit by the seams around it, not only the one under it; falls off
   with height; and weighted so DOWN-facing surfaces are the bright ones and
   flat tops the dark ones. Shadows in this world run upward. */
vec3 fireLight(vec3 p, vec3 n){
  float a = crackAmt(p.xz)
          + 0.60*crackAmt(p.xz + vec2( 7.0,  3.0))
          + 0.55*crackAmt(p.xz + vec2(-4.0,  8.0))
          + 0.35*crackAmt(p.xz + vec2(-12.0,-14.0))
          + 0.35*crackAmt(p.xz + vec2(15.0, -9.0));
  a = min(a, 1.7);
  float h = max(p.y, 0.0);
  float fall = 1.0 / (1.0 + (h*h) / (uGlowH*uGlowH));
  float facing = 0.30 + 0.85*max(-n.y, 0.0) + 0.45*(1.0 - abs(n.y));
  /* the whole pan acts as one broad source, so the caldera wall is lit at its foot
     and goes to soot toward the rim — reach well past uBowlR or the wall is a hole */
  float wide = smoothstep(uBowlR*1.85, uBowlR*0.55, length(p.xz));
  return uLavaC * uFireI * (0.16 + a) * fall * facing * wide;
}

/* the only light from above: ash-filtered day, or starlight. Never dominant —
   in every state it is a fraction of what the floor is throwing up. */
vec3 vaultLight(vec3 n){
  return uVaultC * uVaultI * 2.1 * (0.22 + 0.78*max(n.y, 0.0))
       + uPaleC * uPaleI * max(dot(n, -uPaleDir), 0.0);
}

/* sulphur bloom: sharp-edged yellow crusts that gather on cool rock beside the
   seams, where the gas condenses. Never inside a seam. */
float sulphur(vec3 p){
  float band = smoothstep(0.46, 0.92, turb2(p.xz*0.085 + 4.3));
  float near = smoothstep(0.85, 0.22, riftPhi(p.xz));
  return band * near * smoothstep(0.28, 0.78, turb3(p*0.9)) * panMask(p.xz);
}

/* ash + steam. The medium itself glows near the floor, because the fissures are
   lighting it from inside — so distance does not fade to grey here, it fades to
   a dull orange down low and to soot up high. */
vec3 ashVeil(vec3 col, vec3 p){
  float d = distance(p, cameraPosition);
  float k = uAshD * (1.0 + 1.4*uAshFall);
  float f = 1.0 - exp(-d*d*k*k);
  float lowGlow = exp(-max(p.y, 0.0) / max(uGlowH*1.4, 1.0)) * uCrackI;
  vec3 med = mix(uAshC, uLavaC*0.32, clamp(0.45*lowGlow, 0.0, 0.55));
  return mix(col, med, clamp(f, 0.0, 1.0));
}
float ashAtt(vec3 p){ float d = distance(p, cameraPosition);
  float k = uAshD * (1.0 + 1.4*uAshFall); return exp(-d*d*k*k); }

/* convection shimmer over the hot ground: a small uv/normal nudge that rises
   with the heat, so the crust boils a little where the seams are open. */
vec2 heatWarp(vec3 p){
  float h = crackAmt(p.xz) * uWarp * exp(-max(p.y, 0.0)/6.0);
  return h * vec2(turb2(p.xz*0.45 + uTime*0.75) - 0.5, turb2(p.zx*0.45 - uTime*0.62) - 0.5);
}

/* how much ember a point in the air is carrying — drives the spark layer and
   the glow on anything hanging over an open seam. */
float emberAt(vec3 p){
  return crackAmt(p.xz) * uSparkI * exp(-max(p.y, 0.0) / (uGlowH*1.8));
}

/* the caldera draws its own wind: hot air off the pan, cold off the rim. */
vec2 gustAt(vec3 p){ return uGust * (0.55 + 0.9*turb2(p.xz*0.028 + uTime*0.045)); }
`;

export const VERT_WORLD = /* glsl */`
varying vec3 vP, vN; uniform float uBend; uniform float uTime; uniform vec2 uGust;
void main(){
  #ifdef USE_INSTANCING
  mat4 m = modelMatrix * instanceMatrix;
  #else
  mat4 m = modelMatrix;
  #endif
  vec4 wp = m * vec4(position, 1.0);
  if (uBend > 0.0) { float s = clamp(wp.y * 0.55, 0.0, 1.0); s *= s;
    wp.xz += uBend * s * (uGust * 0.9 + vec2(sin(uTime*1.9 + wp.z*0.6), cos(uTime*1.5 + wp.x*0.7)) * 0.28); }
  vP = wp.xyz; vN = normalize(mat3(m) * normal); gl_Position = projectionMatrix * viewMatrix * wp; }`;

export const FRAG_CRUST = G + /* glsl */`
varying vec3 vP, vN; uniform vec3 uBaseC; uniform float uRough;
void main(){
  vec3 p = vP;
  vec2 hw = heatWarp(p);
  vec3 n = normalize(normalize(vN)
    + vec3(hw.x, 0.0, hw.y) * 1.4
    + 0.38 * vec3(vnz3(p*0.55 + 1.0) - 0.5, vnz3(p*0.55 + 2.0) - 0.5, vnz3(p*0.55 + 3.0) - 0.5)
    + 0.26 * vec3(vnz3(p*2.1 + 1.0) - 0.5, vnz3(p*2.1 + 2.0) - 0.5, vnz3(p*2.1 + 3.0) - 0.5)
    + 0.10 * vec3(vnz3(p*7.0) - 0.5, vnz3(p*7.0 + 4.0) - 0.5, vnz3(p*7.0 + 8.0) - 0.5));

  float m = turb3(p*0.26), m2 = turb3(p*1.45 + 9.0);
  vec3 base = uBaseC * uCrustC * (1.0 - uRough*0.4 + uRough*0.95*m) * (0.80 + 0.30*m2);

  /* obsidian: glassy sheets on the ropy pahoehoe, near-black but mirror-bright
     where the seam light grazes them */
  float glass = smoothstep(0.60, 0.92, turb3(p*0.16 + 3.0));
  base = mix(base, base*0.28 + vec3(0.03, 0.03, 0.045), glass*0.72);

  /* sulphur crusts at the cool shoulders */
  float su = sulphur(p);
  base = mix(base, uSulphC, su*0.85);

  vec3 light = fireLight(p, n) + vaultLight(n);
  vec3 col = base * light;

  /* a sharp specular off the glassy crust, from the seams below */
  vec3 v = normalize(cameraPosition - p);
  float graze = pow(1.0 - max(dot(n, v), 0.0), 3.0);
  col += uLavaC * uCrackI * glass * graze * 0.35 * crackAmt(p.xz + vec2(3.0, -2.0));

  /* the caldera's own shadow, cast UPWARD: the wall goes to soot above the line
     the seam light can reach, which is where an ordinary world would be brightest */
  col *= mix(1.0, 0.55, smoothstep(2.0, uRimY*0.75, p.y));

  /* and the seams themselves, emitting */
  col += crackGlow(p.xz) * (1.0 - 0.55*su);

  gl_FragColor = vec4(ashVeil(col, p), 1.0);
  #include <tonemapping_fragment>
  #include <colorspace_fragment>
}`;

export const TAIL = /* glsl */`
  #include <tonemapping_fragment>
  #include <colorspace_fragment>
}`;
