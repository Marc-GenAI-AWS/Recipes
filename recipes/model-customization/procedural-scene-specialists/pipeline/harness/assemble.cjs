#!/usr/bin/env node
/*
 * assemble.cjs — the contract assembler.
 *
 *   node scenes/assemble.cjs <scene-name>        (default: seastate)
 *   node scenes/assemble.cjs highpark --set layers/atmosphere.js=/abs/cand.js --out /tmp/x.cdn.html
 *
 * Reads scenes/<name>/manifest.json, concatenates the ordered build files
 * (contract runtime + scene layers) into one ES module — stripping local
 * import/export statements and keeping a single `import * as THREE` — and
 * injects it plus the <meta name="states"> list into the scene's shell.html,
 * emitting one self-contained single-file *.cdn.html.
 *
 * --set <build-file-relpath>=<candidate-path>  swap one layer for a candidate
 *   (the layer-harness wrapper uses this to drop a model's layer into a frozen
 *   host scene). Repeatable. --out overrides the manifest output path.
 */
const fs = require('node:fs');
const path = require('node:path');

const ROOT = path.resolve(__dirname, '..');
const argv = process.argv.slice(2);
const name = argv.find((a) => !a.startsWith('--')) || 'seastate';
const sets = {};
let outOverride = null;
for (let i = 0; i < argv.length; i++) {
  const a = argv[i];
  if (a === '--set') { const [k, v] = argv[++i].split(/=(.*)/s); sets[k] = v; }
  else if (a.startsWith('--set=')) { const [k, v] = a.slice(6).split(/=(.*)/s); sets[k] = v; }
  else if (a === '--out') { outOverride = argv[++i]; }
  else if (a.startsWith('--out=')) { outOverride = a.slice(6); }
}
const sceneDir = path.join(ROOT, 'scenes', name);

const manifest = JSON.parse(fs.readFileSync(path.join(sceneDir, 'manifest.json'), 'utf8'));

// Strip ES-module plumbing so the files can be concatenated into one <script>:
//  - drop relative imports (`./`, `../`) — those files are inlined
//  - drop `import * as THREE from 'three'` — consolidated to one at the top
//  - HOIST `three/addons/...` imports to the top (kept, served via the importmap)
//  - drop `export { ... }` / `export default ...` lines
//  - remove a leading `export ` from top-level declarations
const addonImports = [];
function stripModule(src) {
  return src
    .split('\n')
    .filter((line) => {
      const m = line.match(/^\s*import\b[^'"]*from\s*['"]([^'"]+)['"]/);
      if (m) {
        const spec = m[1];
        if (spec.startsWith('three/addons/') || spec.startsWith('three/examples/')) {
          const norm = line.trim();
          if (!addonImports.includes(norm)) addonImports.push(norm);
        }
        return false; // drop every import line here; addon ones are re-emitted at top
      }
      if (/^\s*export\s*\{/.test(line)) return false;
      if (/^\s*export\s+default\b/.test(line)) return false;
      return true;
    })
    .map((line) => line.replace(/^(\s*)export\s+(?=(const|let|var|function|class|async)\b)/, '$1'))
    .join('\n');
}

const bodies = [];
for (const rel of manifest.build.files) {
  const override = sets[rel];
  const fp = override
    ? (path.isAbsolute(override) ? override : path.resolve(process.cwd(), override))
    : path.join(sceneDir, rel);
  const src = fs.readFileSync(fp, 'utf8');
  bodies.push(`// ---- ${rel}${override ? ` (override: ${override})` : ''} ----`);
  bodies.push(stripModule(src).trim());
}
const header = ["import * as THREE from 'three';", ...addonImports];
const bundle = header.join('\n') + '\n\n' + bodies.join('\n\n') + '\n';

const shell = fs.readFileSync(path.join(sceneDir, manifest.shell || 'shell.html'), 'utf8');
const statesAttr = manifest.states.join(',');
const html = shell
  .replace('__STATES__', () => statesAttr)
  .replace('/*__BUNDLE__*/', () => bundle);

const outTarget = outOverride || manifest.output;
const outPath = path.isAbsolute(outTarget)
  ? outTarget
  : (outOverride ? path.resolve(process.cwd(), outTarget) : path.join(ROOT, outTarget));
fs.mkdirSync(path.dirname(outPath), { recursive: true });
fs.writeFileSync(outPath, html);

const bytes = Buffer.byteLength(html);
console.log(`assembled ${name}: ${outPath}`);
console.log(`  ${manifest.build.files.length} source files -> ${bytes} bytes, ${manifest.states.length} states`);
for (const k of Object.keys(sets)) console.log(`  override: ${k} -> ${sets[k]}`);
if (bytes > 400000) console.warn('  WARNING: exceeds harness 400 KB cap');
