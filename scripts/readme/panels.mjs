// CONSTRAINT CONTRACT for every panel on this page. A violation is a bug,
// not a taste call.
//
//   1. The conceit is the coordinate transform: one screen, two coordinate
//      spaces, and the moment sight becomes action. Every panel is a view of
//      that loop. Nothing decorative gets drawn.
//   2. One accent colour, and it means exactly one thing: this is where an
//      action fires. It is spent on the crosshair, the return arrow's head,
//      and nothing else, ever.
//   3. Both grids step every 160 pixels of their own coordinate space, so the
//      cells land at the same on-screen size. That equality is the point: it
//      shows the two frames are one picture at two pixel counts, and the frame
//      size difference is what carries the downscale. The grid is never
//      decoration and its step is never chosen by eye.
//   4. Every number rendered here is computed in facts.mjs from source that is
//      still in the repo. No number is typed into a panel.
//   5. Monospace carries coordinates and tool names. Sans carries labels.
//      Nothing else gets a typeface.
//   6. It survives 390px: narrow variants are recomposed (stacked), never the
//      wide panel scaled down.
//   7. It survives both themes, with no script, no hover, no external request.
//   8. Motion loops or it does not exist, and reduced motion restores the end
//      state rather than only switching animation off.
import fs from 'node:fs';
import path from 'node:path';
import { FACTS, TOOLS, ROOT } from './facts.mjs';

const THEMES = {
  light: { ink: '#1f2328', mute: '#59636e', rule: '#d1d9e0', grid: '#ccd4dd', accent: '#bc4c00' },
  dark: { ink: '#f0f6fc', mute: '#9198a1', rule: '#3d444d', grid: '#2f363e', accent: '#f0883e' },
};
const MONO = "ui-monospace,'SF Mono','Cascadia Mono',Menlo,Consolas,'Liberation Mono',monospace";
const SANS = "-apple-system,BlinkMacSystemFont,'Segoe UI','Noto Sans',Helvetica,Arial,sans-serif";

const esc = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const r1 = n => Number(n.toFixed(1));

// The panel's payload (both crosshairs, both coordinate readouts) is in the
// authored state, so it is complete before any animation runs and stays
// complete if none ever does. Motion only carries the travelling dots.
const REDUCED = `
@media (prefers-reduced-motion:reduce){
 *{animation:none!important}
 .trav,.ring{opacity:0}
}`;

function svg(W, H, label, body, css) {
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img" aria-label="${esc(label)}">
<style>${css}${REDUCED}</style>
${body}
</svg>`;
}

// ---------------------------------------------------------------- transform

// Grid whose cell count reflects the coordinate space it covers: the native
// panel gets one line per 160 native pixels, the model panel one line per 160
// model pixels, so the model grid is genuinely coarser by the scale factor.
function grid(x, y, w, h, spaceW, spaceH, step, cls) {
  const parts = [];
  for (let px = step; px < spaceW; px += step) {
    const gx = r1(x + (px / spaceW) * w);
    parts.push(`<line class="${cls}" x1="${gx}" y1="${y}" x2="${gx}" y2="${r1(y + h)}"/>`);
  }
  for (let py = step; py < spaceH; py += step) {
    const gy = r1(y + (py / spaceH) * h);
    parts.push(`<line class="${cls}" x1="${x}" y1="${gy}" x2="${r1(x + w)}" y2="${gy}"/>`);
  }
  return parts.join('\n');
}

function crosshair(cx, cy, arm, id) {
  return `<g class="hit ${id}">
<line class="ax" x1="${r1(cx - arm)}" y1="${r1(cy)}" x2="${r1(cx + arm)}" y2="${r1(cy)}"/>
<line class="ax" x1="${r1(cx)}" y1="${r1(cy - arm)}" x2="${r1(cx)}" y2="${r1(cy + arm)}"/>
<circle class="dot" cx="${r1(cx)}" cy="${r1(cy)}" r="3.2"/>
</g>`;
}

function transform(t, narrow) {
  const f = FACTS;
  const down = f.shotW / f.exW;
  const up = f.exW / f.shotW;
  // The marked point as a fraction of each frame, identical in both spaces:
  // that sameness is the whole claim the panel makes.
  const fx = f.modelX / f.shotW;
  const fy = f.modelY / f.shotH;

  const W = narrow ? 380 : 880;
  const H = narrow ? 470 : 300;

  let nx, ny, nw, nh, mx, my, mw, mh;
  if (narrow) {
    nw = 300;
    nh = r1((nw * f.exH) / f.exW);
    nx = 40;
    ny = 52;
    mw = r1(nw * down);
    mh = r1((mw * f.shotH) / f.shotW);
    mx = 40;
    my = r1(ny + nh + 116);
  } else {
    nw = 330;
    nh = r1((nw * f.exH) / f.exW);
    nx = 26;
    ny = 74;
    mw = r1(nw * down);
    mh = r1((mw * f.shotH) / f.shotW);
    mx = 566;
    my = r1(ny + (nh - mh) / 2);
  }

  const ncx = r1(nx + fx * nw);
  const ncy = r1(ny + fy * nh);
  const mcx = r1(mx + fx * mw);
  const mcy = r1(my + fy * mh);

  // Travel paths: capture goes native -> model, the click comes back.
  const capture = narrow
    ? `M ${ncx} ${r1(ny + nh)} C ${ncx} ${r1(ny + nh + 46)}, ${mcx} ${r1(my - 60)}, ${mcx} ${r1(my)}`
    : `M ${r1(nx + nw)} ${r1(ny + 24)} C ${r1(nx + nw + 78)} ${r1(ny + 24)}, ${r1(mx - 78)} ${r1(my + 16)}, ${r1(mx)} ${r1(my + 16)}`;
  const click = narrow
    ? `M ${r1(mx + 14)} ${r1(my + mh)} C ${r1(mx + 14)} ${r1(my + mh + 40)}, ${r1(nx + 14)} ${r1(ny + nh + 74)}, ${r1(nx + 14)} ${r1(ny + nh + 30)}`
    : `M ${r1(mx)} ${r1(my + mh - 16)} C ${r1(mx - 78)} ${r1(my + mh - 16)}, ${r1(nx + nw + 78)} ${r1(ny + nh - 24)}, ${r1(nx + nw)} ${r1(ny + nh - 24)}`;

  const capLabel = narrow ? [r1(nx + 150), r1(ny + nh + 40)] : [r1(nx + nw + 80), r1(ny + 12)];
  const clkLabel = narrow ? [r1(nx + 150), r1(ny + nh + 74)] : [r1(nx + nw + 80), r1(ny + nh - 34)];

  const body = `
<g class="lab">
<text class="ttl" x="${nx}" y="${narrow ? 26 : 34}">native screen</text>
<text class="sub" x="${nx}" y="${narrow ? 42 : 52}">what Windows draws</text>
<text class="ttl" x="${mx}" y="${narrow ? r1(my - 26) : 34}">model screen</text>
<text class="sub" x="${mx}" y="${narrow ? r1(my - 10) : 52}">what Claude is sent</text>
</g>

<g class="gridline">${grid(nx, ny, nw, nh, f.exW, f.exH, 160, 'g')}</g>
<g class="gridline">${grid(mx, my, mw, mh, f.shotW, f.shotH, 160, 'g')}</g>

<rect class="frame" x="${nx}" y="${ny}" width="${nw}" height="${nh}"/>
<rect class="frame" x="${mx}" y="${my}" width="${mw}" height="${mh}"/>

<text class="dim" x="${nx}" y="${r1(ny + nh + 16)}">${f.exW} x ${f.exH}</text>
<text class="dim" x="${mx}" y="${r1(my + mh + 16)}">${f.shotW} x ${f.shotH}</text>

<path class="beam" d="${capture}"/>
<path class="beam" d="${click}"/>
<circle class="trav t1" r="3.4"><animateMotion dur="6s" begin="0s" repeatCount="indefinite" keyPoints="0;0;1;1" keyTimes="0;0.06;0.34;1" calcMode="linear" path="${capture}"/></circle>
<circle class="trav t2" r="3.4"><animateMotion dur="6s" begin="0s" repeatCount="indefinite" keyPoints="0;0;1;1" keyTimes="0;0.5;0.78;1" calcMode="linear" path="${click}"/></circle>

<g class="lab">
<text class="cap" x="${capLabel[0]}" y="${capLabel[1]}">screenshot</text>
<text class="num" x="${capLabel[0]}" y="${r1(capLabel[1] + 15)}">x ${down.toFixed(3)}</text>
<text class="cap" x="${clkLabel[0]}" y="${clkLabel[1]}">click</text>
<text class="num" x="${clkLabel[0]}" y="${r1(clkLabel[1] + 15)}">x ${up.toFixed(3)}</text>
</g>

${crosshair(mcx, mcy, 13, 'h1')}
${crosshair(ncx, ncy, 15, 'h2')}
<circle class="ring" cx="${ncx}" cy="${ncy}" r="6"/>

<text class="coord" x="${r1(mcx + 18)}" y="${r1(mcy - 8)}">${f.modelX}, ${f.modelY}</text>
<text class="coord" x="${r1(ncx + 20)}" y="${r1(ncy - 10)}">${f.nativeX}, ${f.nativeY}</text>
`;

  const css = `
.frame{fill:none;stroke:${t.rule};stroke-width:1.25}
.g{stroke:${t.grid};stroke-width:1}
.beam{fill:none;stroke:${t.rule};stroke-width:1.1;stroke-dasharray:3 4;opacity:.9}
.trav{fill:${t.accent}}
.ax{stroke:${t.accent};stroke-width:1.4}
.dot{fill:${t.accent}}
.ttl{font:600 ${narrow ? 13 : 14}px ${SANS};fill:${t.ink}}
.sub{font:400 ${narrow ? 11 : 12}px ${SANS};fill:${t.mute}}
.cap{font:600 12px ${SANS};fill:${t.ink}}
.num,.dim{font:400 11px ${MONO};fill:${t.mute}}
.coord{font:600 12px ${MONO};fill:${t.accent}}
.ring{fill:none;stroke:${t.accent};stroke-width:1.6;opacity:0}
.t1,.t2{opacity:0}
.t1{animation:t1 6s linear infinite}
.t2{animation:t2 6s linear infinite}
.ring{animation:ring 6s linear infinite}
@keyframes t1{0%,5%{opacity:0}6%,33%{opacity:1}35%,100%{opacity:0}}
@keyframes t2{0%,49%{opacity:0}50%,77%{opacity:1}79%,100%{opacity:0}}
@keyframes ring{0%,77%{opacity:0;r:6}80%{opacity:.9;r:7}92%,100%{opacity:0;r:19}}`;

  const label = `The same point in two coordinate spaces. A ${f.exW} by ${f.exH} screen is captured as a ${f.shotW} by ${f.shotH} screenshot, scaled by ${down.toFixed(3)}. Claude clicks at ${f.modelX}, ${f.modelY} in that screenshot and the server fires the click at ${f.nativeX}, ${f.nativeY} on the real screen.`;
  return svg(W, H, label, body, css);
}

// -------------------------------------------------------------------- reach

// One row per group, one cell per real tool, counts recomputed from the parsed
// source rather than from this file's own list.
function reach(t, narrow) {
  const items = JSON.parse(fs.readFileSync(path.join(ROOT, 'scripts/readme/items.json'), 'utf8'));
  const known = new Set(TOOLS.map(x => x.name));
  const listed = items.groups.flatMap(g => g.tools);
  for (const name of listed) {
    if (!known.has(name)) throw new Error(`items.json lists ${name}, which server.py does not define`);
  }
  if (listed.length !== TOOLS.length) {
    throw new Error(`items.json groups ${listed.length} tools, server.py defines ${TOOLS.length}`);
  }

  const cw = narrow ? 7.3 : 7.8;
  const fs_ = narrow ? 11.5 : 12.5;
  const padX = narrow ? 9 : 11;
  const gapX = narrow ? 6 : 8;
  const rowH = narrow ? 25 : 28;
  const chipH = narrow ? 20 : 22;
  const left = narrow ? 12 : 18;
  const maxW = (narrow ? 380 : 880) - left * 2;

  // Wrap chips into lines, so the panel reflows instead of overflowing.
  const rows = [];
  for (const g of items.groups) {
    const lines = [[]];
    let used = 0;
    for (const name of g.tools) {
      const w = Math.round(name.length * cw + padX * 2);
      if (used && used + w > maxW) {
        lines.push([]);
        used = 0;
      }
      lines.at(-1).push({ name, w });
      used += w + gapX;
    }
    rows.push({ g, lines });
  }

  const headH = narrow ? 30 : 34;
  let y = narrow ? 20 : 24;
  const parts = [];
  for (const { g, lines } of rows) {
    parts.push(`<text class="gl" x="${left}" y="${y}">${esc(g.label)}</text>`);
    parts.push(`<text class="gn" x="${left + (narrow ? 46 : 52)}" y="${y}">${esc(g.note)}</text>`);
    parts.push(
      `<text class="gc" x="${(narrow ? 380 : 880) - left}" y="${y}" text-anchor="end">${g.tools.length}</text>`,
    );
    parts.push(
      `<line class="rule" x1="${left}" y1="${r1(y + 8)}" x2="${(narrow ? 380 : 880) - left}" y2="${r1(y + 8)}"/>`,
    );
    let ly = y + (narrow ? 22 : 24);
    for (const line of lines) {
      let x = left;
      for (const chip of line) {
        parts.push(`<rect class="chip" x="${x}" y="${ly}" width="${chip.w}" height="${chipH}" rx="3"/>`);
        parts.push(
          `<text class="cn" x="${r1(x + chip.w / 2)}" y="${r1(ly + chipH / 2 + fs_ * 0.35)}" text-anchor="middle">${esc(chip.name)}</text>`,
        );
        x += chip.w + gapX;
      }
      ly += rowH;
    }
    y = ly + (headH - rowH) + (narrow ? 14 : 12);
  }

  const H = Math.round(y - (narrow ? 6 : 4));
  const W = narrow ? 380 : 880;

  const css = `
.gl{font:600 ${narrow ? 12 : 13}px ${SANS};fill:${t.ink}}
.gn{font:400 ${narrow ? 11 : 12}px ${SANS};fill:${t.mute}}
.gc{font:600 ${narrow ? 11 : 12}px ${MONO};fill:${t.mute}}
.rule{stroke:${t.rule};stroke-width:1}
.chip{fill:none;stroke:${t.rule};stroke-width:1}
.cn{font:400 ${fs_}px ${MONO};fill:${t.ink}}`;

  const label = `The ${TOOLS.length} tools this server exposes, grouped by what they do: ${items.groups
    .map(g => `${g.tools.length} that ${g.label} (${g.tools.join(', ')})`)
    .join('; ')}.`;
  return svg(W, H, label, parts.join('\n'), css);
}

// ------------------------------------------------------------------- build

const PANELS = { transform, reach };

const outDir = path.join(ROOT, 'assets');
fs.mkdirSync(outDir, { recursive: true });

for (const [name, build] of Object.entries(PANELS)) {
  for (const theme of ['light', 'dark']) {
    fs.writeFileSync(path.join(outDir, `${name}-${theme}.svg`), build(THEMES[theme], false));
    fs.writeFileSync(path.join(outDir, `${name}-narrow-${theme}.svg`), build(THEMES[theme], true));
  }
}

// Each panel recomputes what it drew and the build fails on a mismatch.
const NEED = {
  transform: ['exW', 'exH', 'shotW', 'shotH', 'modelX', 'modelY', 'nativeX', 'nativeY'],
  'transform-narrow': ['exW', 'exH', 'shotW', 'shotH', 'modelX', 'modelY', 'nativeX', 'nativeY'],
  // reach asserts counts, not FACTS numbers; its guard is the throw above,
  // plus the chip count checked here.
};

let bad = 0;
for (const [file, keys] of Object.entries(NEED)) {
  for (const theme of ['light', 'dark']) {
    const text = fs.readFileSync(path.join(outDir, `${file}-${theme}.svg`), 'utf8');
    for (const k of keys) {
      if (!new RegExp(`\\b${FACTS[k]}\\b`).test(text)) {
        console.error(`FAIL ${file}-${theme}: ${k} should read ${FACTS[k]}`);
        bad++;
      }
    }
  }
}
for (const theme of ['light', 'dark']) {
  for (const suffix of ['', '-narrow']) {
    const text = fs.readFileSync(path.join(outDir, `reach${suffix}-${theme}.svg`), 'utf8');
    const chips = (text.match(/class="chip"/g) || []).length;
    if (chips !== TOOLS.length) {
      console.error(`FAIL reach${suffix}-${theme}: ${chips} chips for ${TOOLS.length} tools`);
      bad++;
    }
  }
}
if (bad) process.exit(1);

console.error(`ok  ${Object.keys(PANELS).length} panels x 4 variants, ${TOOLS.length} tools, ${FACTS.shotW}x${FACTS.shotH} transform verified`);
