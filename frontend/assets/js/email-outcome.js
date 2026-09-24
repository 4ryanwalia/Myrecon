/* Shared interpretation for email results, saved notes and exports. */
(function (root) {
  "use strict";
  function emailOutcome(data = {}) {
    const summary = data.summary || {};
    const supplied = summary.breach_coverage;
    const rawSources = supplied && Array.isArray(supplied.sources) ? supplied.sources : [
      ["LeakCheck", data.breaches], ["XposedOrNot analytics", data.darkweb],
      ["XposedOrNot fallback", data.fallback], ["Have I Been Pwned", data.hibp],
    ].filter(([name, value]) => value || ["LeakCheck", "XposedOrNot analytics"].includes(name)).map(([name, source]) => {
      const value = source || {};
      return {
      name,
      status: value.status || (value.error || value.checked === false ? "unavailable" : value.checked === true ? "ok" : "unknown"),
      error: value.error,
      checked: value.checked,
      };
    });
    const sources = rawSources.map((source) => ({
      ...source,
      status: source.error || source.checked === false
        ? (["skipped", "unconfigured", "rate_limited"].includes(source.status) ? source.status : "unavailable")
        : source.status || "unknown",
    }));
    const attempted = sources.filter((s) => !["skipped", "unconfigured"].includes(s.status));
    const completed = attempted.filter((s) => s.status === "ok" && s.checked !== false).length;
    // Old reports with an aggregate failure must stay incomplete even when a
    // legacy provider omitted its own failure field.
    const partial = !attempted.length || completed < attempted.length ||
      (!!summary.breach_status && summary.breach_status !== "ok");
    const found = !!summary.breached || [data.breaches, data.darkweb, data.fallback, data.hibp].some((s) => s && s.breached);
    const state = found ? "found" : !completed ? "unavailable" : partial ? "incomplete" : "no_match";
    const label = { found: "Breach exposure detected", no_match: "No match in checked sources", incomplete: "Breach check incomplete", unavailable: "Breach check unavailable" }[state];
    const coverage = `${completed} of ${attempted.length} attempted source checks completed`;
    const detail = partial
      ? "Some sources could not be checked. This result cannot establish that this address has no breach exposure."
      : found ? "Matches were reported by the checked sources. Other breaches may not be covered by these sources."
      : "No matches were reported by the checked sources. This does not prove the address has never been exposed.";
    return { state, label, found, partial, completed, attempted: attempted.length, sources, coverage, detail };
  }
  if (typeof module !== "undefined" && module.exports) module.exports = emailOutcome;
  else root.MyReconEmailOutcome = emailOutcome;
})(typeof window !== "undefined" ? window : globalThis);
