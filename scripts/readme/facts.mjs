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

function readConst(src, name) {
  const m = src.match(new RegExp(`^${name}\\s*=\\s*([\\d.]+)`, 'm'));
  if (!m) throw new Error(`constant ${name} not found in server.py`);
  return Number(m[1]);
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
  waitSeconds: readConst(server, 'MAX_WAIT_SECONDS'),
  deps: (pyproject.match(/^\s*"[^"]+",$/gm) || []).length,
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
