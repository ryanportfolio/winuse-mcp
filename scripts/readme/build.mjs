import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(HERE, '../..');

// Fail before the first step rather than generating a page full of zeroes.
for (const required of ['src/winuse_mcp/server.py', 'pyproject.toml', '.python-version']) {
  if (!fs.existsSync(path.join(root, required))) {
    console.error(`FAIL ${required} is missing; the panels have nothing to read`);
    process.exit(1);
  }
}

const steps = [
  ['panels.mjs', 'SVG panels computed from server.py'],
  ['readme.mjs', 'README.md, and its own invariants'],
];

for (const [file, what] of steps) {
  process.stderr.write(`\n-> ${file}  (${what})\n`);
  execFileSync(process.execPath, [path.join(HERE, file)], { cwd: root, stdio: 'inherit' });
}

process.stderr.write('\nbuild ok\n');
