(function(root) {
  "use strict";
  function confirmed(profiles, choice, key = u => u) {
    return new Set((profiles || []).filter(p => (p.verdict === "found" || p.exists === true) && choice(p.url)?.choice === "mine").map(p => key(p.url)).filter(Boolean)).size;
  }
  function recap(count) {
    const safe = Number.isSafeInteger(count) && count > 0 ? count : 0;
    return {title: "MyRecon discovery recap", text: `I confirmed ${safe} public account${safe === 1 ? "" : "s"} with MyRecon.`, url: "https://www.myrecon.xyz/"};
  }
  const api = {confirmed, recap};
  if (typeof module !== "undefined") module.exports = api;
  root.MyReconDiscovery = api;
})(typeof window !== "undefined" ? window : globalThis);
