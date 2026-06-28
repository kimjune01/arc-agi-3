// arc-agi-3 agent viewer — two same-size 64x64 canvases side by side:
//   #board  the current frame, canonical ARC palette (palette.js)
//   #diff   ONLY the cells that changed from the previous frame, in neutral grey (jotter's spatial
//           delta) — it moves with you as you step forward/back in time.
// LIVE polls /api/live (the session as the agent plays); REPLAY steps /api/frames (the corpus).

const N = 64;
const board = document.getElementById("board"), bctx = board.getContext("2d");
const diff = document.getElementById("diff"), dctx = diff.getContext("2d");
const cell = board.width / N;                    // 512/64 = 8px
const $ = (id) => document.getElementById(id);

const DIFF_BG = "#0b0a0a";                        // diff canvas background (unchanged cells)

// palette hex -> [r,g,b], precomputed, so the diff can subtract colour values per channel
const RGB = Object.fromEntries(Object.entries(ARC.CELL_COLORS).map(([k, h]) => {
  const n = parseInt(h.slice(1), 16);
  return [k, [(n >> 16) & 255, (n >> 8) & 255, n & 255]];
}));

let mode = "live";
let frames = [], cur = 0, playing = false;
let pollTimer = null, playTimer = null;

// ---- render ---------------------------------------------------------------
function drawBoard(grid, state) {
  if (!grid) return;
  const flash = ARC.STATE_FLASH[state];
  if (flash) { bctx.fillStyle = flash; bctx.fillRect(0, 0, board.width, board.height); }
  for (let y = 0; y < grid.length; y++)
    for (let x = 0; x < grid[y].length; x++) {
      bctx.fillStyle = ARC.CELL_COLORS[grid[y][x]] ?? "#000";
      bctx.fillRect(x * cell, y * cell, cell, cell);
    }
}

// A true PIXEL DIFF: each cell rendered as (after − before) mod 256 per RGB channel (the palette
// colours subtracted, wrapping instead of reflecting — so direction of change matters: A→B and B→A
// differ). Unchanged cells -> 0 -> vanish. Task-independent — no per-colour meaning, just arithmetic.
const mod256 = (n) => ((n % 256) + 256) % 256;
function drawDiff(prev, grid) {
  dctx.fillStyle = DIFF_BG; dctx.fillRect(0, 0, diff.width, diff.height);
  if (!prev || !grid) return;
  for (let y = 0; y < grid.length; y++)
    for (let x = 0; x < grid[y].length; x++) {
      const a = RGB[prev[y]?.[x]], b = RGB[grid[y][x]];
      if (!a || !b) continue;
      const dr = mod256(b[0] - a[0]), dg = mod256(b[1] - a[1]), db = mod256(b[2] - a[2]);
      if (dr + dg + db === 0) continue;                     // unchanged -> leave the dark field
      dctx.fillStyle = `rgb(${dr},${dg},${db})`;
      dctx.fillRect(x * cell, y * cell, cell, cell);
    }
}

// The input that produced this diff: the raw action token (we do NOT interpret it as a direction —
// what an action does is what the agent is learning). For a coordinate action (ACTION6 carries x,y,
// protocol-level) ring the clicked cell, since that IS the literal input location.
function drawInput(action, x, y) {
  if (!action) return;
  if (x != null && y != null) {
    dctx.strokeStyle = "#FFDC00"; dctx.lineWidth = 2;
    dctx.beginPath();
    dctx.arc(x * cell + cell / 2, y * cell + cell / 2, cell * 1.6, 0, 2 * Math.PI);
    dctx.stroke();
  }
  const label = x != null ? `${action}  ${x},${y}` : action;
  dctx.font = "600 16px ui-monospace, Menlo, monospace";
  const w = dctx.measureText(label).width;
  dctx.fillStyle = "rgba(0,0,0,0.6)"; dctx.fillRect(8, 8, w + 16, 28);
  dctx.fillStyle = "#e8e6e6"; dctx.textBaseline = "middle";
  dctx.fillText(label, 16, 23);
}

function setState(state) {
  const el = $("state"); el.textContent = state ?? "—";
  const flash = ARC.STATE_FLASH[state];
  el.style.background = flash || "#2a2626";
  el.style.color = flash ? "#062" : "var(--ink)";
}

function hud({ game_id, state, score, win_score, spent, action, frameno }) {
  if (game_id !== undefined) $("game").textContent = game_id ?? "—";
  setState(state);
  $("score").textContent = `${score ?? "—"} / ${win_score ?? "—"}`;
  $("spent").textContent = spent ?? "—";
  $("action").textContent = action ?? "—";
  $("frameno").textContent = frameno ?? "—";
}

// ---- live -----------------------------------------------------------------
// The diff is the LAST action's effect, straight from the session: prev_grid -> grid. The substrate
// records both, so it's correct on first load (no need to have watched the transition happen) and
// stays put between polls until the next action updates both grids together.
async function pollLive() {
  try {
    const d = await (await fetch("/api/live", { cache: "no-store" })).json();
    $("conn").textContent = d.grid ? "live · connected" : "live · no active session";
    if (d.grid) {
      drawBoard(d.grid, d.state);
      drawDiff(d.prev_grid, d.grid);
      drawInput(d.action, d.x, d.y);
      hud({ game_id: d.game_id, state: d.state, score: d.score, win_score: d.win_score,
            spent: d.spent, action: d.action, frameno: `live (${d.spent ?? 0})` });
    }
  } catch (e) { $("conn").textContent = "live · server down"; }
}

// ---- replay ---------------------------------------------------------------
async function loadFrames() {
  const d = await (await fetch("/api/frames", { cache: "no-store" })).json();
  frames = d.frames || [];
  $("seek").max = Math.max(0, frames.length - 1);
  cur = 0; showFrame();
}

function showFrame() {
  if (!frames.length) { $("conn").textContent = "replay · no full frames in corpus"; return; }
  const f = frames[cur], prev = cur > 0 ? frames[cur - 1].grid : null;
  drawBoard(f.grid, f.state);
  drawDiff(prev, f.grid);
  drawInput(f.action, f.x, f.y);
  hud({ game_id: f.game_id, state: f.state, score: f.score, win_score: f.win_score,
        spent: f.spent, action: f.label, frameno: `${cur + 1} / ${frames.length}` });
  $("seek").value = cur;
  $("conn").textContent = "replay · loaded";
}

function step(d) { cur = Math.max(0, Math.min(frames.length - 1, cur + d)); showFrame(); }

function togglePlay(on) {
  playing = on ?? !playing;
  $("play").textContent = playing ? "⏸ pause" : "▶ play";
  $("play").classList.toggle("on", playing);
  clearInterval(playTimer);
  if (playing) playTimer = setInterval(() => {
    if (cur >= frames.length - 1) { togglePlay(false); return; }
    step(1);
  }, 600);
}

// ---- mode -----------------------------------------------------------------
function setMode(m) {
  mode = m;
  $("mLive").classList.toggle("on", m === "live");
  $("mReplay").classList.toggle("on", m === "replay");
  $("replayCtl").style.display = m === "replay" ? "inline-flex" : "none";
  $("seekWrap").style.display = m === "replay" ? "block" : "none";
  clearInterval(pollTimer); togglePlay(false);
  if (m === "live") { pollLive(); pollTimer = setInterval(pollLive, 1000); }
  else loadFrames();
}

$("mLive").onclick = () => setMode("live");
$("mReplay").onclick = () => setMode("replay");
$("first").onclick = () => { cur = 0; showFrame(); };
$("last").onclick = () => { cur = frames.length - 1; showFrame(); };
$("prev").onclick = () => step(-1);
$("next").onclick = () => step(1);
$("play").onclick = () => togglePlay();
$("seek").oninput = (e) => { cur = +e.target.value; showFrame(); };
document.onkeydown = (e) => {
  if (mode !== "replay") return;
  if (e.key === "ArrowRight") step(1);
  else if (e.key === "ArrowLeft") step(-1);
  else if (e.key === " ") { e.preventDefault(); togglePlay(); }
};

setMode("live");

// ---- agent context tail ---------------------------------------------------
// Tails the newest wake/sleep transcript (/api/agent) under the board, so you watch what the agent
// is thinking/doing as it plays. Auto-scrolls unless you've scrolled up to read back.
const TRUNC = 700;
function escapeHTML(s) { return s.replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c])); }
function evHTML(e) {
  const clip = (s) => (s.length > TRUNC ? s.slice(0, TRUNC) + " …" : s);
  if (e.kind === "tool")
    return `<div class="ev tool"><span class="tag">$</span><span class="nm">${e.name || ""}</span> ${escapeHTML(clip(e.text))}</div>`;
  const tag = { thinking: "think", text: "say", result: "out" }[e.kind] || e.kind;
  return `<div class="ev ${e.kind}"><span class="tag">${tag}</span>${escapeHTML(clip(e.text))}</div>`;
}
async function pollAgent() {
  try {
    const d = await (await fetch("/api/agent", { cache: "no-store" })).json();
    $("agentMeta").textContent = d.session
      ? `${d.phase || "session"} · ${d.session} · ${d.age != null ? d.age + "s ago" : ""}${d.age > 20 ? " (idle)" : " (live)"}`
      : "no agent transcript yet";
    const log = $("agentLog");
    const atBottom = log.scrollHeight - log.scrollTop - log.clientHeight < 40;
    log.innerHTML = (d.events || []).map(evHTML).join("") || `<div class="ev result">—</div>`;
    if (atBottom) log.scrollTop = log.scrollHeight;     // follow the tail unless reading back
  } catch (e) { /* server momentarily down — keep last view */ }
}
setInterval(pollAgent, 1500);
pollAgent();
