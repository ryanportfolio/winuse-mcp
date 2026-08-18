// Every number the README shows is computed here, from the source that is
// still in the repo at build time. Nothing on the page is typed by hand.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

export const ROOT = path.resolve(fileURLToPath(new URL('../../', import.meta.url)));

const server = fs.readFileSync(path.join(ROOT, 'src/winuse_mcp/server.py'), 'utf8');
const pyproject = fs.readFileSync(path.join(ROOT, 'pyproject.toml'), 'utf8');

// Tool names come from the decorator when it renames the function ("type"),
// otherwise from the function name underneath it.
function readTools(src) {
  const out = [];
  const re = /@mcp\.tool\((?:name="([a-z_]+)")?\)\s*\ndef\s+([a-z_]+)\s*\(([^)]*)\)/g;
  for (const m of src.matchAll(re)) {
    const params = m[3]
      .split(',')
      .map(p => p.trim().split(':')[0].trim())
      .filter(Boolean);
    out.push({ name: m[1] || m[2], params });
  }
  return out;
}

// Defaults live in the signature, not in a module constant, so they are read
// from there rather than restated on the page.
function readDefault(src, fn, param) {
  const sig = src.match(new RegExp(`def ${fn}\\(([^)]*)\\)`));
  if (!sig) throw new Error(`no signature for ${fn}`);
  const m = sig[1].match(new RegExp(`${param}\\s*:[^=]*=\\s*([\\d.]+)`));
  if (!m) throw new Error(`no default for ${fn}(${param})`);
  return Number(m[1]);
}

function readConst(src, name) {
  const m = src.match(new RegExp(`^${name}\\s*=\\s*([\\d.]+)`, 'm'));
  if (!m) throw new Error(`constant ${name} not found in server.py`);
  return Number(m[1]);
}

// Read the [project] dependencies array specifically. A line-shape regex over
// the whole file would also count a dev group, and would miscount the moment a
// trailing comma moved.
function readDeps(toml) {
  // Close on a bracket at the start of a line: a dependency can carry its own
  // brackets, as "mcp[cli]" does, and the first "]" in the file is inside one.
  const m = toml.match(/^dependencies\s*=\s*\[([\s\S]*?)^\]/m);
  if (!m) throw new Error('no dependencies array in pyproject.toml');
  const names = [...m[1].matchAll(/"([^"]+)"/g)].map(x => x[1]);
  if (!names.length) throw new Error('dependencies array parsed as empty');
  return names.length;
}

export const TOOLS = readTools(server);

const decorators = (server.match(/@mcp\.tool\(/g) || []).length;
if (decorators !== TOOLS.length) {
  throw new Error(`parsed ${TOOLS.length} tools but found ${decorators} @mcp.tool decorators`);
}

const LONG_EDGE = readConst(server, 'MAX_LONG_EDGE');

// The same arithmetic the server runs, applied to one worked example so the
// page can show a transform a reader can check against their own display.
const EX_W = 1920;
const EX_H = 1080;
const scale = Math.min(1, LONG_EDGE / Math.max(EX_W, EX_H));
const shotW = Math.round(EX_W * scale);
const shotH = Math.round(EX_H * scale);
const modelX = Math.round(shotW / 2);
const modelY = Math.round(shotH * 0.574);
const nativeX = Math.round(modelX / scale);
const nativeY = Math.round(modelY / scale);

export const FACTS = {
  tools: TOOLS.length,
  longEdge: LONG_EDGE,
  recordFrames: readConst(server, 'MAX_RECORD_FRAMES'),
  recordSeconds: readConst(server, 'MAX_RECORD_SECONDS'),
  recordDefaultFrames: readDefault(server, 'record', 'max_frames'),
  recordDefaultSeconds: readDefault(server, 'record', 'duration_seconds'),
  waitSeconds: readConst(server, 'MAX_WAIT_SECONDS'),
  deps: readDeps(pyproject),
  python: fs.readFileSync(path.join(ROOT, '.python-version'), 'utf8').trim(),
  exW: EX_W,
  exH: EX_H,
  shotW,
  shotH,
  modelX,
  modelY,
  nativeX,
  nativeY,
};

export const REPO = 'ryanportfolio/winuse-mcp';
