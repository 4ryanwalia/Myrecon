(() => {
  "use strict";
  const account = () => window.MyReconAccount;
  const base = () => (window.MYRECON || {}).apiBase || "";
  const byId = (id) => document.getElementById(id);
  let deferredInstall = null;
  let previousStates = new Map();
  let timer = null;
  let hasSnapshot = false;
  let activeUserId = null;

  function message(text, error = false) {
    const notice = byId("notice");
    notice.textContent = text;
    notice.hidden = !text;
    notice.classList.toggle("error", error);
  }

  function describe(worker) {
    if (worker.state === "idle") return "Ready to claim a queued scan.";
    if (worker.state === "busy") return "Running a scan and reporting progress.";
    if (worker.state === "recovering") return "Finishing a scan or waiting for its next poll.";
    if (worker.state === "unreachable") return `No contact for ${worker.age_seconds}s. Waiting before alerting.`;
    if (worker.state === "stopped") return "Stopped cleanly by its notebook cell.";
    return `No contact for ${worker.age_seconds || 0}s. Render will use its fallback.`;
  }

  function renderWorkers(workers) {
    const root = byId("workers");
    root.replaceChildren();
    if (!workers.length) {
      const card = document.createElement("article");
      card.className = "card";
      card.innerHTML = "<h2>No live check-in yet</h2><p>Open the private notebook launcher, run all cells, and keep the final worker cell running until it prints Live status confirmed.</p>";
      root.append(card);
      return;
    }
    for (const worker of workers) {
      const card = document.createElement("article");
      card.className = "card";
      const head = document.createElement("div");
      head.className = "card-head";
      const title = document.createElement("h2");
      title.textContent = worker.label;
      const badge = document.createElement("span");
      badge.className = `badge ${worker.state}`;
      badge.textContent = worker.state;
      head.append(title, badge);
      const detail = document.createElement("p");
      detail.textContent = describe(worker);
      card.append(head, detail);
      if (worker.duplicate) {
        const warning = document.createElement("div");
        warning.className = "warning";
        warning.textContent = "Two live runtimes use this label.";
        card.append(warning);
      }
      root.append(card);
    }
  }

  function foregroundNotification(worker) {
    if (!("Notification" in window) || Notification.permission !== "granted") return;
    const wasLive = ["idle", "busy", "recovering", "unreachable"].includes(previousStates.get(worker.label));
    if (wasLive && ["offline", "stopped"].includes(worker.state)) {
      new Notification("MyRecon worker offline", { body: `${worker.label}: ${describe(worker)}`, icon: "/worker-console/icon-192.png" });
    }
  }

  function responseMessage(data, status) {
    if (data.code === "worker_console_unconfigured") {
      return "Set SCAN_WORKER_OPERATOR_EMAIL on Render to the Google address used here, then refresh.";
    }
    if (data.code === "worker_console_not_owner") {
      return "This Google account is not the configured worker-console owner. Use the configured account or update SCAN_WORKER_OPERATOR_EMAIL on Render.";
    }
    if (status === 401 || data.code === "sign_in_required") {
      return "Your sign-in could not be verified. Sign in again, then refresh.";
    }
    return data.error || "Could not load live worker status.";
  }

  async function loadStatus() {
    const state = account().state();
    const userId = state.user && state.user.uid;
    if (activeUserId !== userId) {
      activeUserId = userId;
      hasSnapshot = false;
      previousStates = new Map();
      byId("workers").replaceChildren();
    }
    if (!state.user) {
      byId("summary").textContent = "Sign in with the owner Google account to see live worker status.";
      byId("sign-in").hidden = false;
      byId("refresh").hidden = true;
      byId("launcher").hidden = true;
      return;
    }
    byId("sign-in").hidden = true;
    byId("refresh").hidden = false;
    message("");
    try {
      const response = await fetch(base() + "/api/operator/worker-console", {
        headers: await account().authHeaders(), cache: "no-store",
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        const error = new Error(data.error || "Could not load worker status.");
        error.status = response.status;
        error.data = data;
        throw error;
      }
      byId("summary").textContent = `Last checked ${new Date(data.observed_at * 1000).toLocaleTimeString()}.`;
      const launcher = byId("launcher");
      launcher.hidden = !data.launcher_url;
      if (data.launcher_url) launcher.href = data.launcher_url;
      renderWorkers(data.workers || []);
      for (const worker of data.workers || []) foregroundNotification(worker);
      previousStates = new Map((data.workers || []).map((worker) => [worker.label, worker.state]));
      hasSnapshot = true;
    } catch (error) {
      byId("summary").textContent = hasSnapshot
        ? "Showing the last successful status. Live refresh is unavailable."
        : "Live worker status is unavailable.";
      message(responseMessage(error.data || {}, error.status || 0) || error.message, true);
    }
  }

  function schedule() {
    clearInterval(timer);
    timer = setInterval(() => { if (!document.hidden) loadStatus(); }, 30_000);
  }

  function refreshWhenVisible() {
    if (!document.hidden) loadStatus();
  }

  window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault();
    deferredInstall = event;
    byId("install").hidden = false;
  });
  window.addEventListener("appinstalled", () => { deferredInstall = null; byId("install").hidden = true; });

  document.addEventListener("DOMContentLoaded", async () => {
    if ("serviceWorker" in navigator) navigator.serviceWorker.register("/worker-console/service-worker.js", { scope: "/worker-console/" }).catch(() => {});
    byId("sign-in").addEventListener("click", () => account().signIn().catch((error) => message(account().friendly(error) || error.message, true)));
    byId("refresh").addEventListener("click", loadStatus);
    byId("install").addEventListener("click", async () => {
      if (!deferredInstall) return;
      await deferredInstall.prompt();
      await deferredInstall.userChoice;
      deferredInstall = null;
      byId("install").hidden = true;
    });
    await account().ready;
    account().onChange(loadStatus);
    document.addEventListener("visibilitychange", refreshWhenVisible);
    window.addEventListener("focus", refreshWhenVisible);
    await loadStatus();
    schedule();
  });
})();
