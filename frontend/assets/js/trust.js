(function () {
  "use strict";
  async function loadChangelog() {
    const target = document.querySelector("#changelogEntries");
    if (!target) return;
    target.setAttribute("aria-busy", "true");
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 8000);
    try {
      const response = await fetch("/data/changelog.json", { cache: "no-store", signal: controller.signal });
      if (!response.ok) throw new Error("Unavailable changelog");
      const data = await response.json();
      if (!Array.isArray(data.entries)) throw new Error("Invalid changelog");
      const entries = data.entries.filter((e) => e && /^\d{4}-\d{2}-\d{2}$/.test(e.date)
        && typeof e.title === "string" && Array.isArray(e.changes)
        && e.changes.every((change) => typeof change === "string"));
      if (!entries.length) throw new Error("No published updates");
      const list = document.createElement("ol");
      list.className = "changelog-list";
      entries.sort((a, b) => b.date.localeCompare(a.date)).forEach((entry, index) => {
        const row = document.createElement("li");
        row.className = "changelog-entry";
        const date = document.createElement("time");
        date.dateTime = entry.date;
        // Noon UTC keeps a date-only release stable across user timezones.
        date.textContent = new Date(entry.date + "T12:00:00Z").toLocaleDateString(undefined,
          { year: "numeric", month: "short", day: "numeric", timeZone: "UTC" });
        const title = document.createElement("h3");
        title.textContent = entry.title;
        const meta = document.createElement("div");
        meta.className = "changelog-meta";
        meta.append(date);
        if (entry.version) {
          const version = document.createElement("span");
          version.className = "changelog-version";
          version.textContent = String(entry.version);
          meta.append(version);
        }
        if (index === 0) {
          const latest = document.createElement("span");
          latest.className = "changelog-latest";
          latest.textContent = "Latest update";
          meta.append(latest);
        }
        row.append(meta);
        row.append(title);
        const changes = document.createElement("ul");
        entry.changes.forEach((change) => {
          const item = document.createElement("li");
          item.textContent = change;
          changes.append(item);
        });
        row.append(changes);
        list.append(row);
      });
      target.replaceChildren(list);
    } catch {
      target.replaceChildren();
      const fallback = document.createElement("p");
      fallback.className = "changelog-fallback";
      fallback.textContent = "Updates are temporarily unavailable. The lookup tool is still available. ";
      const retry = document.createElement("button");
      retry.type = "button";
      retry.className = "btn btn-ghost btn-sm";
      retry.textContent = "Retry updates";
      retry.addEventListener("click", loadChangelog, { once: true });
      fallback.append(retry);
      target.append(fallback);
    } finally {
      clearTimeout(timer);
      target.removeAttribute("aria-busy");
    }
  }
  document.addEventListener("DOMContentLoaded", () => {
    loadChangelog();
    // Tool mode hides overview sections. Evidence links must reveal their
    // destination even after a lookup, without changing the current results.
    const reveal = () => {
      if (["#benchmarks", "#changelog"].includes(location.hash)) {
        document.body.classList.remove("tool-mode");
        document.querySelector(location.hash)?.scrollIntoView();
      }
    };
    window.addEventListener("hashchange", reveal);
    document.querySelectorAll('a[href="/#benchmarks"], a[href="/#changelog"]').forEach((link) => {
      link.addEventListener("click", () => document.body.classList.remove("tool-mode"));
    });
    reveal();
  });
})();
