// SEC-09 check: with engine/game.zip blocked, the page must show a fixed message and keep details in the console.
import { connect, sleep } from "./cdp-lib.mjs";
const [port, url] = process.argv.slice(2);
const { send, ev, on } = await connect(port); const errs = [];
on((m) => { if (m.method === "Runtime.consoleAPICalled" && m.params.type === "error") errs.push(m.params.args.map((a) => a.description ?? a.value).join(" ").slice(0, 90)); });
await send("Network.enable"); await send("Runtime.enable"); await send("Page.enable");
await send("Network.setBlockedURLs", { urls: ["*engine/game.zip*"] });   // simulate a failed download
await send("Page.navigate", { url }); await sleep(8000);
console.log(JSON.stringify({ url, pageMessage: await ev("document.getElementById('msg').textContent"), consoleHasDetails: errs }));
await send("Network.setBlockedURLs", { urls: [] }); process.exit(0);
