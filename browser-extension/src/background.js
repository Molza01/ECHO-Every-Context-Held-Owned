// ContextOS browser extension — service worker.
// Sends *page-level* context (title, URL, domain) to the local ContextOS backend on
// navigation. It never reads page contents, form fields, or keystrokes. Selected text is
// only ever sent through the explicit "Remember this" context-menu actions.

const BACKEND = "http://127.0.0.1:8765";
let lastKey = "";
let debounceTimer = null;

const SKIP = /^(chrome|edge|about|chrome-extension|moz-extension|view-source|devtools):/i;

function domainOf(url) {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return null;
  }
}

async function isEnabled() {
  const { captureEnabled = true } = await chrome.storage.local.get("captureEnabled");
  return captureEnabled;
}

async function post(path, body) {
  try {
    await fetch(`${BACKEND}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch (e) {
    // backend offline — fail silently; the panel surfaces connection state
  }
}

async function sendPageContext(tab, setCurrent = true) {
  if (!tab || !tab.url || SKIP.test(tab.url)) return;
  if (!(await isEnabled())) return;
  const domain = domainOf(tab.url);
  const key = `${tab.url}|${tab.title}`;
  if (setCurrent && key === lastKey) return;
  lastKey = key;
  await post("/api/ingest", {
    source_type: "browser",
    title: tab.title || null,
    url: tab.url,
    domain,
    set_current: setCurrent,
  });
}

function debouncedSend(tab) {
  if (debounceTimer) clearTimeout(debounceTimer);
  debounceTimer = setTimeout(() => sendPageContext(tab, true), 700);
}

chrome.tabs.onActivated.addListener(async ({ tabId }) => {
  try {
    const tab = await chrome.tabs.get(tabId);
    debouncedSend(tab);
  } catch {}
});

chrome.tabs.onUpdated.addListener((_tabId, changeInfo, tab) => {
  if (changeInfo.status === "complete" && tab.active) debouncedSend(tab);
});

// --- explicit "remember this" actions (no silent capture) ----------------------------
chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: "contextos-remember-selection",
    title: "ContextOS: Remember this selection",
    contexts: ["selection"],
  });
  chrome.contextMenus.create({
    id: "contextos-remember-page",
    title: "ContextOS: Remember this page",
    contexts: ["page"],
  });
  try {
    chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: false });
  } catch {}
});

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  const domain = domainOf(tab?.url || "");
  if (info.menuItemId === "contextos-remember-selection" && info.selectionText) {
    await post("/api/ingest", {
      source_type: "manual",
      content: `Noted while reading "${tab?.title || domain}": ${info.selectionText.trim().slice(0, 800)}`,
      url: tab?.url || null,
      domain,
      set_current: false,
    });
  } else if (info.menuItemId === "contextos-remember-page") {
    await sendPageContext(tab, false);
  }
});

// popup asks the worker to force-send the current page
chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg?.type === "remember-current") {
    chrome.tabs.query({ active: true, currentWindow: true }).then(([tab]) => {
      sendPageContext(tab, false).then(() => sendResponse({ ok: true }));
    });
    return true;
  }
});
