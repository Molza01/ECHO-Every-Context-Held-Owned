const BACKEND = "http://127.0.0.1:8765";

const SOURCE_COLORS = {
  browser: "#6476ed",
  git: "#f97316",
  file: "#22c55e",
  terminal: "#eab308",
  manual: "#ec4899",
  active_window: "#a78bfa",
  unknown: "#8b93a7",
};

function domainOf(url) {
  try { return new URL(url).hostname.replace(/^www\./, ""); } catch { return null; }
}

function confColor(v) {
  return v >= 70 ? "#22c55e" : v >= 50 ? "#6476ed" : "#f59e0b";
}

function render(surfaced) {
  const list = document.getElementById("list");
  if (!surfaced || surfaced.length === 0) {
    list.innerHTML = '<div class="empty">No related memories for this page yet.</div>';
    return;
  }
  list.innerHTML = surfaced
    .map((s) => {
      const m = s.memory;
      const color = SOURCE_COLORS[m.source_type] || SOURCE_COLORS.unknown;
      const reasons = (s.reasons || []).map((r) => `<li>• ${r}</li>`).join("");
      const link = m.url ? `<div><a href="${m.url}" target="_blank">${m.domain || m.url}</a></div>` : "";
      return `<div class="card">
        <span class="conf" style="color:${confColor(s.context_confidence)}">${s.context_confidence}%</span>
        <span class="badge" style="color:${color};background:${color}22">${m.source_type || "memory"}</span>
        <div class="body">${(m.content || m.title || "").replace(/</g, "&lt;")}</div>
        ${link}
        <ul class="why">${reasons}</ul>
      </div>`;
    })
    .join("");
}

async function refresh() {
  // find current tab, ask the backend for memories related to this page
  let tab;
  try {
    [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  } catch {}
  try {
    const status = await fetch(`${BACKEND}/api/status`).then((r) => r.json());
    const ok = status?.supermemory?.reachable;
    document.getElementById("dot").style.background = ok ? "#22c55e" : "#f59e0b";
    document.getElementById("state").textContent = ok ? "Local :6767" : "offline";
  } catch {
    document.getElementById("dot").style.background = "#f59e0b";
    document.getElementById("state").textContent = "offline";
    return;
  }

  if (!tab || !tab.url) return;
  const query = tab.title || domainOf(tab.url) || "";
  try {
    const res = await fetch(`${BACKEND}/api/related`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query }),
    });
    const data = await res.json();
    render(data.surfaced);
  } catch {}
}

refresh();
setInterval(refresh, 4000);
chrome.tabs.onActivated.addListener(refresh);
chrome.tabs.onUpdated.addListener((_id, info) => info.status === "complete" && refresh());
