// Thin JS layer: load Python, read the keyboard, draw. All game rules live in game/.
const canvas = document.getElementById("game");
const ctx = canvas.getContext("2d");
const msg = document.getElementById("msg");
const keys = new Set();
const LEVEL_COUNT = 3;
const T = 32;  // tile size, must match game/engine.py
// "server" when Flask serves the page, "static" on GitHub Pages (set in templates/index.html).
const SERVER = document.body.dataset.mode === "server";
const levelUrl = (n) => SERVER ? `api/levels/${n}` : `levels/level_${n}.json`;

const held = (...codes) => codes.some((c) => keys.has(c));

async function fetchOk(path) {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`${path}: HTTP ${res.status}`);
  return res;
}

async function main() {
  // Pyodide's runtime files are served by this site, never a CDN (SEC-03).
  const pyodide = await loadPyodide({ indexURL: new URL("static/pyodide/", location.href).href });
  // The engine arrives as one zip (scripts/bundle_engine.py), unpacked to game/ in
  // Pyodide's virtual filesystem. The level files are copied in next to it.
  pyodide.unpackArchive(await (await fetchOk("engine/game.zip")).arrayBuffer(), "zip");
  pyodide.FS.mkdir("levels");
  for (let n = 1; n <= LEVEL_COUNT; n++) {
    pyodide.FS.writeFile(`levels/level_${n}.json`, await (await fetchOk(levelUrl(n))).text());
  }

  // Python loads and validates the levels; JS only borrows the grids for drawing.
  pyodide.runPython("import game\nnom = game.Game(game.load_levels('levels'))");
  const game = pyodide.globals.get("nom");
  const grids = pyodide.runPython("[lvl['grid'] for lvl in nom.levels]").toJs();
  msg.textContent = "Press ? for instructions";

  // Convert a Python dict to a plain JS object and free the Python proxy.
  const toState = (py) => { const s = py.toJs({ dict_converter: Object.fromEntries }); py.destroy(); return s; };
  let state = toState(game.state());  // so the first frame has something to draw
  let helpOpen = false;               // the game is paused while the instructions are shown
  const scores = setUpScores();
  scores.newRun();
  addEventListener("keydown", (e) => {
    if (e.target instanceof HTMLInputElement) return;  // typing a name, not playing
    if (["ArrowLeft", "ArrowRight", "ArrowUp", "Space"].includes(e.code)) e.preventDefault();
    keys.add(e.code);
    if (e.repeat) return;
    if (e.key === "?") { helpOpen = !helpOpen; return; }
    if (helpOpen) { if (e.code === "Escape") helpOpen = false; return; }
    if (e.code === "Enter") game.next_level();   // only acts on the level-complete screen
    if (e.code === "KeyR") {                     // the engine decides: level or whole game
      const ended = ["game_over", "won"].includes(game.status);
      game.press_restart();
      if (ended) scores.newRun();                // a whole new game is a new server run
    }
  });
  addEventListener("keyup", (e) => keys.delete(e.code));
  addEventListener("blur", () => keys.clear());

  const DT = 1 / 60;
  let acc = 0, last = performance.now();
  function frame(now) {
    acc += Math.min((now - last) / 1000, 5 * DT);  // cap catch-up after a pause
    last = now;
    if (helpOpen) acc = 0;
    while (acc >= DT) {
      const before = state.status;
      state = toState(game.step(held("ArrowLeft", "KeyA"), held("ArrowRight", "KeyD"),
                                held("Space", "ArrowUp", "KeyW")));
      acc -= DT;
      // The step that reaches a Moon Gate: record the level (sent to the server in server mode).
      if (state.status !== before && ["level_complete", "won"].includes(state.status)) {
        scores.levelDone(toState(game.progress()));
      }
    }
    scores.update(state);
    draw(grids[state.level - 1], state, now / 1000);
    if (helpOpen) drawHelp();
    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
}

// --- High scores ------------------------------------------------------------
// Server mode: the browser only reports what happened. The server checks each
// level and calculates the score itself, so nothing here can set the score.
// Static mode: no server, so the engine's score is saved in localStorage.
function setUpScores() {
  const form = document.getElementById("score-form");
  const nameInput = document.getElementById("score-name");
  const scoreMsg = document.getElementById("score-msg");
  const table = document.getElementById("score-table");
  if (!SERVER) document.querySelector("#scores h2").textContent = "High scores (local scores only)";

  let queue = Promise.resolve();  // run score actions one after another, in order
  let levelsDone = 0, submitted = false, lastScore = 0;
  const call = (fn) => {
    queue = queue.then(fn).catch((e) => {
      scoreMsg.textContent = `${SERVER ? "Server" : "Not saved"}: ${e.message}`;
    });
  };

  async function showTable() {
    const top = SERVER ? await api.topScores() : localScores.topScores();
    const rows = top.map((s, i) => {
      const tr = document.createElement("tr");
      for (const value of [i + 1, s.name, s.score, s.levels_completed]) {
        const td = document.createElement("td");
        td.textContent = value;  // as text, never HTML: a name can't inject markup
        tr.append(td);
      }
      return tr;
    });
    table.tBodies[0].replaceChildren(...rows);
    table.hidden = rows.length === 0;
    if (rows.length === 0 && !scoreMsg.textContent) scoreMsg.textContent = "No scores yet.";
  }

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    call(async () => {
      const { rank } = SERVER ? await api.submitScore(nameInput.value)
                              : localScores.submit(nameInput.value, lastScore, levelsDone);
      submitted = true;
      nameInput.blur();
      scoreMsg.textContent = `Saved! You are #${rank}.`;
      await showTable();
    });
  });
  call(showTable);

  return {
    newRun() {
      levelsDone = 0; submitted = false;
      if (SERVER) call(async () => { await api.startRun(); scoreMsg.textContent = ""; });
    },
    levelDone(progress) {
      if (!SERVER) { levelsDone++; return; }
      call(async () => {
        const { score } = await api.reportLevel(progress);
        levelsDone++;
        scoreMsg.textContent = `Level ${progress.level} recorded. Server score: ${score}.`;
      });
    },
    update(state) {  // the name form shows once the game is over, if there is a score to save
      lastScore = state.score;  // used only in static mode; the server keeps its own score
      form.hidden = !(["game_over", "won"].includes(state.status) && levelsDone > 0 && !submitted);
    },
  };
}

function draw(grid, s, t) {
  const W = canvas.width, H = canvas.height;
  const worldW = grid[0].length * T, worldH = grid.length * T;
  // Camera follows Nom, clamped so it never shows outside the level.
  const camX = Math.max(0, Math.min(s.x + s.size / 2 - W / 2, worldW - W));
  const camY = Math.max(0, Math.min(s.y + s.size / 2 - H / 2, worldH - H));

  ctx.clearRect(0, 0, W, H);
  ctx.save();
  ctx.translate(-Math.round(camX), -Math.round(camY));
  const c0 = Math.floor(camX / T), c1 = Math.ceil((camX + W) / T);
  const r0 = Math.floor(camY / T), r1 = Math.ceil((camY + H) / T);
  for (let r = r0; r < Math.min(r1, grid.length); r++) {
    for (let c = c0; c < Math.min(c1, grid[r].length); c++) {
      const ch = grid[r][c], x = c * T, y = r * T;
      if (ch === "#") { ctx.fillStyle = "#5b6b8c"; ctx.fillRect(x, y, T, T); }
      if (ch === "x") drawSpikes(x, y);
      if (ch === "G") drawGate(x, y);
    }
  }
  for (const [c, r] of s.pellets) drawPellet(c * T + T / 2, r * T + T / 2, t);
  drawNom(s, t);
  ctx.restore();

  drawHud(s);
  if (s.status === "level_complete") {
    overlay(`Level ${s.level} complete!`, [`+100 bonus · Score ${s.score}`, "Press Enter to continue"]);
  }
  if (s.status === "game_over") overlay("You lose!", [`Final score ${s.score}`, "Press R to try again"]);
  if (s.status === "won") {
    overlay("You reached the final Moon Gate!", [`Final score ${s.score}`, "Press R to play again"]);
  }
}

function drawHud(s) {
  const W = canvas.width;
  ctx.fillStyle = "rgba(11,16,38,0.75)"; ctx.fillRect(0, 0, W, 30);
  ctx.font = "15px system-ui"; ctx.textBaseline = "middle"; ctx.fillStyle = "#cfe3ff";
  ctx.textAlign = "left";
  ctx.fillText(`Level ${s.level}/${s.levels}: ${s.name}`, 10, 15);
  ctx.textAlign = "center";
  ctx.fillText(`Score ${s.score}   ·   Pellets ${s.pellets_got}/${s.pellets_total}`, W / 2 + 40, 15);
  // Lives as small Nom icons, greyed out once lost.
  for (let i = 0; i < 3; i++) {
    const cx = W - 70 + i * 20, cy = 15;
    ctx.fillStyle = i < s.lives ? "#2ec4b6" : "#3a4466";
    ctx.beginPath(); ctx.moveTo(cx, cy); ctx.arc(cx, cy, 7, 0.5, 2 * Math.PI - 0.5); ctx.fill();
  }
  ctx.textAlign = "right"; ctx.fillStyle = "#8a9bc4";
  ctx.fillText("?", W - 6, 15);
  ctx.textBaseline = "alphabetic";
}

function drawPellet(x, y, t) {  // a firefly: a soft glow with a bright core that pulses
  const pulse = 0.75 + 0.25 * Math.sin(t * 4 + x);
  ctx.fillStyle = `rgba(245,233,168,${0.25 * pulse})`;
  ctx.beginPath(); ctx.arc(x, y, 8, 0, 2 * Math.PI); ctx.fill();
  ctx.fillStyle = "#f5e9a8";
  ctx.beginPath(); ctx.arc(x, y, 3.5, 0, 2 * Math.PI); ctx.fill();
}

const HELP = [
  ["← → / A D", "Move"],
  ["Space / ↑ / W", "Jump (hold for higher)"],
  ["R", "Restart level / start a new game"],
  ["Enter", "Next level"],
  ["?", "Show / hide these instructions"],
];

function drawHelp() {
  const W = canvas.width, H = canvas.height;
  ctx.fillStyle = "rgba(11,16,38,0.92)"; ctx.fillRect(0, 0, W, H);
  ctx.textAlign = "center"; ctx.fillStyle = "#f5e9a8"; ctx.font = "24px system-ui";
  ctx.fillText("How to play", W / 2, 50);
  ctx.font = "15px system-ui"; ctx.fillStyle = "#cfe3ff";
  ctx.fillText("Guide Nom to the Moon Gate in each of the 3 levels.", W / 2, 84);
  ctx.fillText("Fireflies are worth 10 points; each Moon Gate gives a 100-point bonus.", W / 2, 106);
  ctx.fillText("Spikes and falls cost a life. Lose all 3 and the game is over.", W / 2, 128);
  HELP.forEach(([k, action], i) => {
    const y = 172 + i * 28;
    ctx.textAlign = "right"; ctx.fillStyle = "#f5e9a8"; ctx.fillText(k, W / 2 - 16, y);
    ctx.textAlign = "left"; ctx.fillStyle = "#cfe3ff"; ctx.fillText(action, W / 2 + 16, y);
  });
  ctx.textAlign = "center"; ctx.fillStyle = "#8a9bc4";
  ctx.fillText("Game paused · press ? or Esc to resume", W / 2, H - 30);
}

function drawSpikes(x, y) {  // bramble spikes: three thorns in the lower half of the tile
  ctx.fillStyle = "#c4486b";
  ctx.beginPath();
  for (let i = 0; i < 3; i++) {
    const bx = x + i * (T / 3);
    ctx.moveTo(bx, y + T); ctx.lineTo(bx + T / 6, y + T / 2); ctx.lineTo(bx + T / 3, y + T);
  }
  ctx.fill();
}

function drawGate(x, y) {  // Moon Gate: a glowing arch
  ctx.strokeStyle = "#f5e9a8"; ctx.lineWidth = 4;
  ctx.beginPath(); ctx.arc(x + T / 2, y + T / 2, T / 2 - 2, Math.PI, 0);
  ctx.lineTo(x + T - 2, y + T); ctx.moveTo(x + 2, y + T); ctx.lineTo(x + 2, y + T / 2);
  ctx.stroke();
}

function drawNom(s, t) {  // a teal circle with a wedge mouth that chomps while moving
  if (s.status === "game_over") return;  // Nom already vanished in the final death animation
  const rad = s.size / 2, cx = s.x + rad, cy = s.y + rad;
  const dying = s.status === "dying";
  // While dying, each edge of the mouth turns from its resting angle round to the
  // back of Nom (pi), where the two edges meet and Nom disappears.
  let open = s.moving ? 0.25 + 0.2 * Math.abs(Math.sin(t * 12)) : 0.2;
  if (dying) open = 0.2 + s.death * (Math.PI - 0.2);
  if (open >= Math.PI) return;  // edges have met: nothing left to draw (the pause before respawn)
  const base = s.facing > 0 ? 0 : Math.PI;
  ctx.fillStyle = "#2ec4b6";
  ctx.beginPath(); ctx.moveTo(cx, cy);
  ctx.arc(cx, cy, rad, base + open, base - open + 2 * Math.PI); ctx.fill();
  if (dying) return;  // no eye while the mouth sweeps round
  ctx.fillStyle = "#0b1026";
  ctx.beginPath(); ctx.arc(cx + s.facing * 3, cy - rad / 2, 2.5, 0, 2 * Math.PI); ctx.fill();
}

function overlay(title, lines) {  // a message screen below the HUD bar, which stays visible
  const W = canvas.width, H = canvas.height;
  ctx.fillStyle = "rgba(11,16,38,0.7)"; ctx.fillRect(0, 30, W, H - 30);
  ctx.fillStyle = "#f5e9a8"; ctx.font = "28px system-ui"; ctx.textAlign = "center";
  ctx.fillText(title, W / 2, H / 2);
  ctx.font = "16px system-ui";
  lines.forEach((line, i) => ctx.fillText(line, W / 2, H / 2 + 32 + i * 24));
}

main().catch((e) => { msg.textContent = "Failed to load: " + e; console.error(e); });
