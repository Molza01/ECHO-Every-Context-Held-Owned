const BACKEND = "http://127.0.0.1:8765";

async function init() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  document.getElementById("page").textContent = tab?.title || tab?.url || "(no page)";

  const { captureEnabled = true } = await chrome.storage.local.get("captureEnabled");
  document.getElementById("toggle").checked = captureEnabled;

  // backend status
  try {
    const res = await fetch(`${BACKEND}/api/status`);
    const ok = res.ok && (await res.json())?.supermemory?.reachable;
    setState(ok);
  } catch {
    setState(false);
  }
}

function setState(ok) {
  document.getElementById("dot").style.background = ok ? "#22c55e" : "#f59e0b";
  document.getElementById("state").textContent = ok ? "Local :6767" : "offline";
}

document.getElementById("toggle").addEventListener("change", (e) => {
  chrome.storage.local.set({ captureEnabled: e.target.checked });
});

document.getElementById("remember").addEventListener("click", () => {
  chrome.runtime.sendMessage({ type: "remember-current" }, () => {
    const btn = document.getElementById("remember");
    btn.textContent = "Remembered ✓";
    setTimeout(() => (btn.textContent = "Remember this page"), 1200);
  });
});

document.getElementById("panel").addEventListener("click", async () => {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  try {
    await chrome.sidePanel.open({ tabId: tab.id });
    window.close();
  } catch {}
});

init();
