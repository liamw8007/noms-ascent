// SEC-05 check (server mode): an injected inline script and onerror handler must be blocked by the CSP, and another site must not be able to frame the game.
import { connect, sleep } from "./cdp-lib.mjs";
const [port, url] = process.argv.slice(2);
if (!url.includes("5077")) process.exit(0);           // server-mode checks only
const { send, ev, on } = await connect(port);
const blocked = [];
on((m) => { if (m.method === "Log.entryAdded" && /Refused|Content Security Policy|frame-ancestors|X-Frame-Options/.test(m.params.entry.text)) blocked.push(m.params.entry.text.slice(0, 160)); });
await send("Log.enable"); await send("Page.enable");
await send("Page.navigate", { url }); await sleep(6000);
const inline = await ev(`(() => { window.__ran = false; const s = document.createElement('script'); s.textContent = 'window.__ran = true'; document.body.append(s); return new Promise(r => setTimeout(() => r(window.__ran), 300)); })()`);
const handler = await ev(`(() => { const d = document.createElement('div'); d.innerHTML = '<img src=x onerror="window.__ran2=true">'; document.body.append(d); return new Promise(r => setTimeout(() => r(!!window.__ran2), 500)); })()`);
await send("Page.navigate", { url: "http://127.0.0.1:8078/" }); await sleep(3000);
const framed = await ev(`(() => { try { return document.getElementById('f').contentDocument?.body?.innerHTML.length ?? 'cross-origin (no access)'; } catch (e) { return String(e); } })()`);
console.log(JSON.stringify({ inlineScriptRan: inline, injectedOnerrorRan: handler, framedDocument: framed, browserMessages: blocked }, null, 1));
process.exit(0);
