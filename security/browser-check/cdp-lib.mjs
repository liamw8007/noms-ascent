// CDP helpers for the browser checks (security/browser-check/run.sh).
// Minimal CDP helper for headless Chromium (Node 22+ has fetch and WebSocket built in).
export const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
export async function connect(port) {
  for (let i = 0; i < 50; i++) { try { await fetch(`http://127.0.0.1:${port}/json`); break; } catch { await sleep(200); } }
  const tabs = await (await fetch(`http://127.0.0.1:${port}/json`)).json();
  const ws = new WebSocket(tabs.find((t) => t.type === "page").webSocketDebuggerUrl);
  await new Promise((r) => (ws.onopen = r));
  let id = 0; const pending = {}; const listeners = [];
  ws.onmessage = (m) => {
    const d = JSON.parse(m.data);
    if (d.id && pending[d.id]) { pending[d.id](d); delete pending[d.id]; }
    else if (d.method) listeners.forEach((f) => f(d));
  };
  const send = (method, params = {}) => new Promise((r) => { pending[++id] = r; ws.send(JSON.stringify({ id, method, params })); })
    .then((d) => { if (d.error) throw new Error(method + ": " + d.error.message); return d.result; });
  const ev = async (expression) => {
    const r = await send("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true });
    if (r.exceptionDetails) throw new Error("eval: " + JSON.stringify(r.exceptionDetails).slice(0, 300));
    return r.result.value;
  };
  return { ws, send, ev, on: (f) => listeners.push(f) };
}
// Real key events, as a player would send them.
export async function key(send, type, code, keyName) {
  const vk = { ArrowLeft: 37, ArrowRight: 39, ArrowUp: 38, Space: 32, Enter: 13, KeyR: 82, Escape: 27, Slash: 191 }[code];
  await send("Input.dispatchKeyEvent", { type, code, key: keyName ?? code, windowsVirtualKeyCode: vk, nativeVirtualKeyCode: vk,
    ...(type === "keyDown" && keyName && keyName.length === 1 ? { text: keyName } : {}) });
}
// Nom's position: centroid of the #2ec4b6 pixels on the canvas (null if none).
export const NOM_POS = `(() => { const c = document.getElementById('game'); const d = c.getContext('2d').getImageData(0,0,c.width,c.height).data;
  let n=0,sx=0,sy=0; for (let i=0;i<d.length;i+=4) if (d[i]===0x2e && d[i+1]===0xc4 && d[i+2]===0xb6) { const p=i/4; sx+=p%c.width; sy+=Math.floor(p/c.width); n++; }
  return n ? {x: Math.round(sx/n), y: Math.round(sy/n), n} : null; })()`;
