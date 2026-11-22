// Part 15 regression: replays the game requirements in a real browser, in one mode.
// Movement, jumping, help, restart and name entry use real key events. To get through
// whole levels quickly, Nom is moved onto pellets, spikes or the gate through the engine
// object (test-only hook below), after waiting real time so the server's clock check passes.
import { connect, sleep, key, NOM_POS } from "./cdp-lib.mjs";
import { readFileSync, mkdirSync, writeFileSync } from "node:fs";
const [port, url, shotDir] = process.argv.slice(2);
const MODE = url.includes("5077") ? "server" : "static";
const LEVELS = [1, 2, 3].map((n) => JSON.parse(readFileSync(`levels/level_${n}.json`)));
const find = (lvl, ch) => { const out = []; lvl.grid.forEach((row, r) => [...row].forEach((c, col) => c === ch && out.push([col, r]))); return out; };
const { send, ev, on } = await connect(port);
const results = []; const csp = []; const errors = []; const foreign = new Set(); const api = [];
const check = (name, ok, detail = "") => { results.push({ name, ok: !!ok, detail }); };
on((m) => {
  if (m.method === "Log.entryAdded" && /Content Security Policy|Refused/.test(m.params.entry.text)) csp.push(m.params.entry.text.slice(0, 150));
  if (m.method === "Runtime.consoleAPICalled" && m.params.type === "error") errors.push(m.params.args.map((a) => a.description ?? a.value).join(" ").slice(0, 150));
  if (m.method === "Runtime.exceptionThrown") errors.push(String(m.params.exceptionDetails.exception?.description).slice(0, 150));
  if (m.method === "Network.requestWillBeSent") { const u = new URL(m.params.request.url); if (u.protocol.startsWith("http") && !["127.0.0.1", "localhost"].includes(u.hostname)) foreign.add(u.origin); }
  if (m.method === "Network.responseReceived" && m.params.response.url.includes("/api/") && m.params.type === "Fetch") api.push(`${new URL(m.params.response.url).pathname} ${m.params.response.status}`);
});
for (const d of ["Network", "Runtime", "Log", "Page"]) await send(`${d}.enable`);
await send("Emulation.setDeviceMetricsOverride", { width: 760, height: 760, deviceScaleFactor: 1, mobile: false });
// Test-only hook: keep a reference to the Pyodide instance so the test can read the Game object.
await send("Page.addScriptToEvaluateOnNewDocument", { source: `
  let raw;  // pyodide.js assigns loadPyodide several times; always hand out a wrapper of the latest function
  Object.defineProperty(window, "loadPyodide", { configurable: true,
    set(v) { raw = v; },
    get() { return typeof raw === "function" ? async (...a) => (window.__py = await raw(...a)) : raw; } });` });
await send("Page.navigate", { url });
const waitFor = async (expr, ms = 20000) => { for (let t = 0; t < ms; t += 100) { if (await ev(expr)) return true; await sleep(100); } return false; };
const G = (attr) => ev(`window.__py.runPython("nom.${attr}")`);
const py = (code) => ev(`window.__py.runPython(${JSON.stringify(code)})`);
const shot = async (name) => { const { data } = await send("Page.captureScreenshot", { format: "png" }); writeFileSync(`${shotDir}/${MODE}-${name}.png`, Buffer.from(data, "base64")); };
const press = async (code, k, hold = 80) => { await key(send, "keyDown", code, k); await sleep(hold); await key(send, "keyUp", code, k); };
const enter = async () => { await send("Input.dispatchKeyEvent", { type: "keyDown", code: "Enter", key: "Enter", windowsVirtualKeyCode: 13, text: "\r" }); await sleep(50); await key(send, "keyUp", "Enter", "Enter"); };
const moveTo = (col, row) => py(`nom.x = ${col} * 32 + 2; nom.y = ${row} * 32 + 2; nom.vx = nom.vy = 0.0`);
const fallOut = () => py(`nom.y = nom.rows * 32 + 40; nom.vy = 0.0`);
const scoreMsg = () => ev("document.getElementById('score-msg').textContent");
mkdirSync(shotDir, { recursive: true });

check("page loads and engine starts", await waitFor("window.__py && document.getElementById('msg').textContent.startsWith('Press ?')", 60000));
check("starts on level 1 with 3 lives and 0 points", (await G("level_index")) === 0 && (await G("lives")) === 3 && (await G("score")) === 0);
check("Nom is drawn on the canvas", !!(await ev(NOM_POS)));
await shot("1-level1-start");

// --- Movement, jumping, collision (real keys) --------------------------------------
await waitFor(`window.__py.runPython("nom.on_ground")`);
let x0 = await G("x"); await press("ArrowRight", undefined, 400); await sleep(300);
let x1 = await G("x"); check("ArrowRight moves right", x1 > x0 + 20, `${x0.toFixed(0)} -> ${x1.toFixed(0)}`);
await press("KeyA", "a", 300); await sleep(300);
let x2 = await G("x"); check("A moves left", x2 < x1 - 10, `${x1.toFixed(0)} -> ${x2.toFixed(0)}`);
const floorY = await G("y");
await key(send, "keyDown", "Space", " "); let minY = floorY;
for (let i = 0; i < 12; i++) { await sleep(40); minY = Math.min(minY, await G("y")); }
await key(send, "keyUp", "Space", " ");
check("Space jumps (full hold reaches ~3 tiles)", floorY - minY > 80, `rose ${(floorY - minY).toFixed(0)} px`);
await waitFor(`window.__py.runPython("nom.on_ground")`, 3000);
check("Nom lands back on the floor (collision)", Math.abs((await G("y")) - floorY) < 0.5 && (await G("on_ground")));
await key(send, "keyDown", "ArrowUp"); await sleep(20); await key(send, "keyUp", "ArrowUp");   // a quick tap
let hopMin = floorY; for (let i = 0; i < 12; i++) { await sleep(40); hopMin = Math.min(hopMin, await G("y")); }
await waitFor(`window.__py.runPython("nom.on_ground")`, 3000);
check("ArrowUp tap gives a shorter hop than a held jump", floorY - hopMin > 5 && floorY - hopMin < (floorY - minY) / 2, `rose ${(floorY - hopMin).toFixed(0)} px`);
await py("nom.x = 0.0; nom.vx = 0.0"); await press("ArrowLeft", undefined, 200); await sleep(100);
check("the world edge stops Nom", (await G("x")) === 0);

// --- Help overlay pauses the game -------------------------------------------------
await press("Slash", "?"); await sleep(100); const t0 = await G("level_time"); await sleep(500);
check("? opens help and pauses the game", (await G("level_time")) === t0);
await shot("2-help");
await press("Escape", "Escape"); await sleep(300);
check("Esc closes help and resumes", (await G("level_time")) > t0);

// --- Pellets, death, restart -------------------------------------------------------
const [p1, p2] = find(LEVELS[0], "o");   // (7,7) and (8,7): in the air, not yet collected
const had = await py("len(nom.collected)"), hadScore = await G("score");
await moveTo(...p1); await sleep(100); await moveTo(...p2); await sleep(100);
const got = await py("len(nom.collected)");
check("pellets are collected (+10 each)", got === had + 2 && (await G("score")) === hadScore + 20, `${had} -> ${got} pellets`);
await fallOut(); await waitFor(`window.__py.runPython("nom.status") == "dying"`, 2000);
check("falling out of the world costs a life", (await G("lives")) === 2);
await waitFor(`window.__py.runPython("nom.status") == "playing"`, 4000);
check("respawn after the death animation, pellets kept", (await G("status")) === "playing" && (await py("len(nom.collected)")) === got);
await press("KeyR", "r"); await sleep(150);
check("R restarts the level: pellet points removed, no life lost", (await G("score")) === 0 && (await py("len(nom.collected)")) === 0 && (await G("lives")) === 2);

// --- Levels 1-3, transitions, server scoring, win --------------------------------
let expectServer = 0;
for (let n = 0; n < 3; n++) {
  const lvl = LEVELS[n];
  if (n === 1) {   // level 2 has spikes: check they hurt
    const lives = await G("lives"); await moveTo(...find(lvl, "x")[0]);
    await waitFor(`window.__py.runPython("nom.status") == "dying"`, 2000);
    check("spikes cost a life (level 2)", (await G("lives")) === lives - 1);
    await waitFor(`window.__py.runPython("nom.status") == "playing"`, 4000);
  }
  const pel = find(lvl, "o")[0]; await moveTo(...pel); await sleep(100);
  await moveTo(...find(lvl, "S")[0]);   // back to the start, away from hazards, while time passes
  // Real time must pass: the server refuses a level reported faster than its own clock (SEC-01).
  await waitFor(`window.__py.runPython("nom.level_time") > ${lvl.min_time + 0.5}`, 30000);
  const [gc, gr] = find(lvl, "G")[0]; await moveTo(gc, gr);
  const done = n < 2 ? "level_complete" : "won";
  check(`level ${n + 1} can be completed (${done})`, await waitFor(`window.__py.runPython("nom.status") == "${done}"`, 3000));
  const score = await G("score"); expectServer += 10 + 100;
  if (MODE === "server") {
    const ok = await waitFor(`document.getElementById('score-msg').textContent.includes('Level ${n + 1} recorded')`, 5000);
    const m = (await scoreMsg()).match(/Server score: (\d+)/);
    check(`server accepted level ${n + 1}; server score = engine score`, ok && m && +m[1] === score && score === expectServer, `${await scoreMsg()} engine=${score}`);
  }
  if (n === 0) await shot("3-level-complete");
  if (n < 2) { await enter(); await sleep(150);
    check(`Enter moves on to level ${n + 2}`, (await G("level_index")) === n + 1 && (await G("status")) === "playing"); }
}
await shot("4-won");

// --- Name entry and the score table ------------------------------------------------
check("the name form appears after the win", await waitFor("!document.getElementById('score-form').hidden", 3000));
await ev("document.getElementById('score-name').focus()");
await send("Input.insertText", { text: "Regress" });
await press("KeyR", "r");   // typed into the name: must not restart the game
check("R is ignored while typing a name", (await G("status")) === "won" && (await ev("document.getElementById('score-name').value")) === "Regressr");
await enter();
check("the score is saved", await waitFor("document.getElementById('score-msg').textContent.startsWith('Saved!')", 5000), await scoreMsg());
const rows = await ev("[...document.querySelectorAll('#score-table tbody tr')].map(tr => [...tr.children].map(td => td.textContent))");
const mine = rows.find((r) => r[1] === "Regressr");
check("the name and score appear in the top-10 table", mine && +mine[2] === expectServer, JSON.stringify(mine));
if (MODE === "static") check("static mode says 'local scores only'", (await ev("document.querySelector('#scores h2').textContent")).includes("local scores only"));
await shot("5-scores");

// --- New game after a win, then losing -------------------------------------------------
await ev("document.activeElement.blur()");
await press("KeyR", "r"); await sleep(200);
check("R after a win starts a new game", (await G("level_index")) === 0 && (await G("lives")) === 3 && (await G("score")) === 0 && (await G("status")) === "playing");
for (let i = 0; i < 3; i++) {
  await waitFor(`window.__py.runPython("nom.status") == "playing"`, 4000);
  await fallOut(); await waitFor(`window.__py.runPython("nom.status") != "playing"`, 2000);
}
check("losing all 3 lives ends the game", await waitFor(`window.__py.runPython("nom.status") == "game_over"`, 4000));
await press("KeyR", "r"); await sleep(150);
check("R after a loss can't cancel it but starts a new game", (await G("status")) === "playing" && (await G("lives")) === 3);
await shot("6-new-game-after-loss");
if (MODE === "server") await sleep(500);

check("no CSP violations", csp.length === 0, csp.join(" | "));
check("no JavaScript errors", errors.length === 0, errors.join(" | "));
check("no requests to other sites", foreign.size === 0, [...foreign].join(" "));
if (MODE === "server") check("API calls succeeded", api.length > 0 && api.every((a) => a.endsWith(" 200")), api.join(", "));
const failed = results.filter((r) => !r.ok);
console.log(`\n## ${MODE} mode (${url}): ${results.length - failed.length}/${results.length} checks passed`);
for (const r of results) console.log(`- [${r.ok ? "x" : " "}] ${r.name}${r.detail ? ` (${r.detail})` : ""}`);
process.exit(0);
