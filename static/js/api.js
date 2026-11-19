// fetch() wrappers for server mode, and localStorage scores for static mode.
// The server re-checks everything the fetch() calls send.
async function postJson(path, body) {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
  return data;
}

const api = {
  startRun: () => postJson("api/runs", {}),
  // progress = {level, pellets, time} from the engine's progress() method
  reportLevel: (progress) => postJson("api/progress", progress),
  submitScore: (name) => postJson("api/scores", { name }),
  async topScores() {
    const res = await fetch("api/scores");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  },
};

// Static mode (GitHub Pages) has no server, so scores live in this browser's
// localStorage (FR-30). Anyone can edit localStorage, so these scores are for
// this device only, and every entry read back is checked before it is shown.
const LOCAL_KEY = "noms-ascent-scores";
const NAME_RE = /^[A-Za-z0-9 _-]{1,16}$/;  // the same rule as NAME_RE in app.py
const validName = (name) => NAME_RE.test(name) && /[^ _]/.test(name);  // not only spaces/underscores

const localScores = {
  load() {
    try {
      const rows = JSON.parse(localStorage.getItem(LOCAL_KEY));
      if (!Array.isArray(rows)) return [];
      return rows.filter((r) => r && typeof r.name === "string" && validName(r.name)
        && Number.isInteger(r.score) && Number.isInteger(r.levels_completed));
    } catch {
      return [];  // nothing saved yet, corrupt JSON, or storage blocked by the browser
    }
  },
  topScores() {
    // sort() is stable, so of two equal scores the earlier one stays first.
    return this.load().sort((a, b) => b.score - a.score).slice(0, 10);
  },
  submit(name, score, levelsCompleted) {
    name = name.trim();
    if (!validName(name)) throw new Error("use 1-16 letters, digits, spaces, _ or -");
    const rows = this.topScores();
    rows.push({ name, score, levels_completed: levelsCompleted, created_at: new Date().toISOString() });
    rows.sort((a, b) => b.score - a.score);
    try {
      localStorage.setItem(LOCAL_KEY, JSON.stringify(rows.slice(0, 10)));
    } catch {
      throw new Error("this browser is blocking local storage");
    }
    return { rank: 1 + rows.filter((r) => r.score > score).length };
  },
};
