/* Shared interpretation for email results, saved notes and exports. */
(function (root) {
  "use strict";
  function emailOutcome(data = {}) {
    const summary = data.summary || {};
    const supplied = summary.breach_coverage;
    const rawSources = supplied && Array.isArray(supplied.sources) ? supplied.sources : [
      ["LeakCheck", data.breaches], ["XposedOrNot analytics", data.darkweb],
      ["XposedOrNot fallback", data.fallback], ["Have I Been Pwned", data.hibp],
      ["LeakCheck Pro", data.breach_details],
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
    const found = !!summary.breached || [data.breaches, data.darkweb, data.fallback, data.hibp, data.breach_details].some((s) => s && s.breached);
    const state = found ? "found" : !completed ? "unavailable" : partial ? "incomplete" : "no_match";
    const label = { found: "Breach exposure detected", no_match: "No match in checked sources", incomplete: "Breach check incomplete", unavailable: "Breach check unavailable" }[state];
    const coverage = `${completed} of ${attempted.length} attempted source checks completed`;
    const detail = partial
      ? "Some sources could not be checked. This result cannot establish that this address has no breach exposure."
      : found ? "Matches were reported by the checked sources. Other breaches may not be covered by these sources."
      : "No matches were reported by the checked sources. This does not prove the address has never been exposed.";
    return { state, label, found, partial, completed, attempted: attempted.length, sources, coverage, detail };
  }
  const count = (value) => Number.isSafeInteger(value) && value >= 0 ? value : null;
  const rows = (value) => Array.isArray(value) ? value.filter(r => r && typeof r === "object" && !Array.isArray(r)) : [];
  const platformAliases = {
    google: "Google", googleaccount: "Google", googlemaps: "Google", googlepublicprofile: "Google", mapsgoogle: "Google", maps: "Google", gmail: "Google", googlemail: "Google", youtube: "Google",
    github: "GitHub", linkedin: "LinkedIn", linkedinpublicprofile: "LinkedIn", twitter: "X", x: "X", twitterx: "X", xtwitter: "X",
    facebook: "Facebook", gravatar: "Gravatar", spotify: "Spotify", wordpress: "WordPress", wix: "Wix", zoom: "Zoom",
    aliexpress: "AliExpress", duolingo: "Duolingo",
  };
  function canonicalPlatform(value) {
    const name = typeof value === "string" ? value.trim() : "";
    if (!name) return null;
    const key = name.toLowerCase().replace(/^https?:\/\//, "").replace(/^www\./, "")
      .replace(/\.(com|net|org|io|co|me|ru|de|fr|uk|in)\/?$/, "").replace(/[^a-z0-9]/g, "");
    return key && !["openpgp", "openpgpkey", "keysopenpgp", "pgp"].includes(key) ? { id: (platformAliases[key] || name).toLowerCase().replace(/[^a-z0-9]/g, ""), name: platformAliases[key] || name } : null;
  }
  function sourceRows(data) {
    const sources = [...rows(data.account_checks?.sources), ...rows(data.profile_enrichment?.sources)];
    const unique = new Map();
    sources.forEach(source => {
      const id = [source.name, source.provider, source.contributor_id].map(v => String(v || "").toLowerCase()).join("|");
      unique.set(id, { ...source });
    });
    return [...unique.values()];
  }
  function platformCoverage(data, supplied = {}) {
    const sources = rows(supplied.sources).length ? rows(supplied.sources) : sourceRows(data);
    const platformSources = sources.filter(s => s.scope !== "reviews" && !/\breviews?\b/i.test(s.name || ""));
    const excluded = new Set(["skipped", "disabled", "unconfigured", "off"]);
    const completedStates = new Set(["ok", "found", "no_match", "no_signal", "not_found"]);
    const attemptedSources = platformSources.filter(s => !excluded.has(s.status));
    const registration = data.registration_checks || {};
    const attempted = count(supplied.attempted) ?? ((count(registration.attempted) || 0) + attemptedSources.length);
    const completed = count(supplied.checked) ?? count(supplied.completed) ?? ((count(registration.checked) || 0) + attemptedSources.filter(s => completedStates.has(s.status)).length);
    const unavailable = count(supplied.unknown) ?? count(supplied.unavailable) ?? Math.max(0, attempted - completed);
    const unconfigured = platformSources.filter(s => s.status === "unconfigured").length;
    const skipped = count(supplied.skipped) ?? platformSources.filter(s => ["skipped", "disabled", "off"].includes(s.status)).length;
    const aggregate = data.platform_summary || data.evidence_report?.platform_summary || {};
    const enabled = aggregate.enabled ?? data.account_checks?.enabled;
    const failed = attemptedSources.some(s => !completedStates.has(s.status));
    const status = enabled === false ? "off" : unavailable || unconfigured || failed || ["partial", "unavailable"].includes(aggregate.status) ? "incomplete" : attempted ? "ok" : "unknown";
    return { enabled, status, attempted, completed, unavailable, unconfigured, skipped, sources };
  }
  // These are counts of platforms with returned email evidence, never a count
  // of accounts owned by a person. Server aggregation is authoritative for new
  // reports; the fallback keeps older exports usable without inventing matches.
  function emailPlatforms(data = {}) {
    data = data && typeof data === "object" ? data : {};
    const supplied = data.platform_summary || data.evidence_report?.platform_summary;
    const platforms = new Map();
    const add = (name, kind, basis = "") => {
      const platform = canonicalPlatform(name);
      if (!platform) return;
      let row = platforms.get(platform.id);
      if (!row) {
        row = { ...platform, profile: false, registration: false, historical: false, declared: false, linked: false };
        platforms.set(platform.id, row);
      }
      const historical = kind === "breach" || kind === "historical" || ["historical_commit", "historical_public_link", "historical_breach"].includes(basis);
      const declared = kind === "declared" || ["owner_declared", "public_link", "historical_public_link"].includes(basis);
      row.profile ||= kind === "profile";
      row.registration ||= kind === "registration";
      row.historical ||= historical;
      row.declared ||= declared;
      row.linked ||= kind === "registration" || (kind === "profile" && ["exact_public_email", "public_email", "provider_email", "email_hash"].includes(basis));
    };
    if (supplied && typeof supplied === "object" && Array.isArray(supplied.platforms)) {
      rows(supplied.platforms).forEach(row => {
        const kinds = Array.isArray(row.kinds) ? row.kinds : [];
        const basis = Array.isArray(row.basis) ? row.basis : [];
        const hasEvidence = row.status === "found" || row.historical || row.owner_declared;
        if (!hasEvidence) return;
        kinds.forEach(kind => add(row.name || row.id, kind, basis.find(v => ["historical_commit", "historical_public_link", "historical_breach", "owner_declared", "public_link"].includes(v)) || ""));
        if (row.historical) add(row.name || row.id, "historical");
        if (row.owner_declared) add(row.name || row.id, "declared");
        const platform = canonicalPlatform(row.name || row.id);
        if (!platform || !platforms.has(platform.id)) return;
        const entry = platforms.get(platform.id);
        // The server may have both current and historical evidence for one
        // platform. Its basis array preserves that overlap.
        if (basis.some(v => ["provider_email", "public_email", "exact_public_email", "email_hash"].includes(v))) entry.linked = true;
        if (typeof row.linked === "boolean") entry.linked = row.linked;
      });
    } else {
      [...rows(data.evidence_report?.profiles), ...rows(data.profile_enrichment?.profiles)].forEach(p => {
        add(p.platform, "profile", p.basis);
        rows(p.provenance).forEach(observation => add(p.platform, "profile", observation.basis));
      });
      [...rows(data.evidence_report?.registrations), ...rows(data.profile_enrichment?.registrations)].forEach(r => {
        if (!r.status || r.status === "found") add(r.service || r.platform || r.domain, "registration");
      });
      rows(data.registration_checks?.services).forEach(r => { if (r.status === "found") add(r.service || r.domain, "registration"); });
      rows(data.linked_services?.services).forEach(r => {
        if (["profile", "registration", "breach"].includes(r.kind)) add(r.service, r.kind, r.basis);
        if (r.registration_status === "found") add(r.service, "registration");
        rows(r.historical_evidence).forEach(() => add(r.service, "breach", "historical_breach"));
      });
      const github = data.github || {};
      if (!data.evidence_report && (!github.status || github.status === "found") &&
          ((typeof github.username === "string" && github.username.trim()) || (typeof github.url === "string" && /^https?:\/\//.test(github.url)))) {
        add("GitHub", "profile", github.basis || "historical_commit");
      }
      if (!data.evidence_report && data.gravatar?.exists) add("Gravatar", "profile", "email_hash");
    }
    const list = [...platforms.values()].sort((a, b) => a.name.localeCompare(b.name));
    const counts = supplied?.counts || {};
    const sum = (key) => list.filter(p => p[key]).length;
    const total = count(counts.total_platforms) ?? list.length;
    const linked = count(counts.linked_platforms) ?? sum("linked");
    const historical = count(counts.historical_platforms) ?? sum("historical");
    const historicalOnly = count(counts.historical_only_platforms) ?? list.filter(p => p.historical && !p.linked).length;
    const publicProfiles = count(counts.public_profile_platforms) ?? sum("profile");
    const registrationSignals = count(counts.registration_platforms) ?? sum("registration");
    const declared = count(counts.owner_declared_platforms) ?? sum("declared");
    const coverage = platformCoverage(data, supplied?.coverage);
    const label = `${linked} ${linked === 1 ? "platform" : "platforms"} with profile or registration evidence`;
    const detail = `${total} distinct ${total === 1 ? "platform has" : "platforms have"} returned evidence, including ${historical} with historical associations and ${declared} with owner-declared links. Categories overlap. Historical and declared links alone do not confirm a current account. Coverage is limited to the checked sources; this is not the total number of accounts for this email.`;
    return { total, linked, historical, historicalOnly, publicProfiles, registrationSignals, declared, names: list.filter(p => p.linked).map(p => p.name), allNames: list.map(p => p.name), platforms: list, lowerBound: true, label, detail, coverage };
  }
  function emailReviews(profile = {}, data = {}) {
    profile = profile && typeof profile === "object" ? profile : {};
    data = data && typeof data === "object" ? data : {};
    const reviews = rows(profile.reviews);
    const returned = reviews.length;
    const textReturned = reviews.filter(r => typeof r.text === "string" && r.text.trim()).length;
    const supplied = profile.review_coverage && typeof profile.review_coverage === "object" ? profile.review_coverage : {};
    const contributor = String(supplied.contributor_id || profile.fields?.ID || profile.fields?.["Google ID"] || "");
    const sources = sourceRows(data).filter(s => /review|contributor/i.test(s.name || "") && /google|maps|contributor/i.test(s.name || "")
      && (!s.contributor_id || !contributor || String(s.contributor_id) === contributor));
    const states = sources.map(s => s.status);
    const status = supplied.status || profile.review_status || (states.includes("partial") ? "partial" : states.includes("ok") ? "ok" : states[0] || "unknown");
    const totalReported = count(supplied.total_reported) ?? count(profile.stats?.Reviews) ?? count(profile.stats?.reviews);
    const ratingsReported = count(supplied.ratings_reported) ?? count(profile.stats?.Ratings) ?? count(profile.stats?.ratings);
    const contributionsReported = count(supplied.contributions_reported) ?? (totalReported !== null && ratingsReported !== null ? count(totalReported + ratingsReported) : null);
    const limit = count(supplied.limit) ?? count(profile.review_limit) ?? sources.map(s => count(s.limit)).find(v => v !== null) ?? null;
    const source = supplied.source || profile.review_source || profile.field_sources?.reviews?.source || (sources.length ? sources.map(s => [s.provider, s.name].filter(Boolean).join(" · ")).join("; ") : profile.source || "Source not specified");
    const failed = !["ok", "found", "partial", "no_reviews", "no_match"].includes(status);
    // The collection may include rating-only contributions. Reviews alone
    // cannot be compared with the number of returned review/rating items.
    const contradictory = contributionsReported !== null && contributionsReported < returned;
    const limited = supplied.limited === true || status === "partial" || (totalReported !== null && totalReported > returned) || (contributionsReported !== null && contributionsReported > returned) || (limit !== null && limit > 0 && returned >= limit);
    const partial = failed || limited || contradictory;
    let state;
    if (returned) state = limited ? "limited" : "found";
    else if (status === "private" || status === "inaccessible") state = "private";
    else if (["unconfigured", "disabled", "skipped"].includes(status)) state = "unconfigured";
    else if (["unavailable", "timeout", "rate_limited", "authentication_required", "credits_exhausted", "blocked", "error"].includes(status)) state = "unavailable";
    else if (status === "ok" && totalReported === 0 && (ratingsReported === null || ratingsReported === 0)) state = "no_reviews";
    else if (limited) state = "limited";
    else state = "not_returned";
    const reported = (totalReported !== null ? ` Source reports ${totalReported} ${totalReported === 1 ? "review" : "reviews"}${ratingsReported !== null ? ` and ${ratingsReported} ${ratingsReported === 1 ? "rating" : "ratings"}` : ""}.` : " The source did not provide a total review count.")
      + (totalReported === null && ratingsReported !== null ? ` Source reports ${ratingsReported} ${ratingsReported === 1 ? "rating" : "ratings"}.` : "");
    const label = returned ? `${returned} ${returned === 1 ? "review item" : "review items"} returned${totalReported !== null ? ` · ${totalReported} source-reported` : ""}`
      : { no_reviews: "Source reports no public reviews", private: "Public reviews are inaccessible", unconfigured: "Review source is not connected", unavailable: "Review source unavailable", limited: "Review details not returned", not_returned: "Review details not returned" }[state];
    const detail = returned
      ? `${textReturned} returned ${textReturned === 1 ? "item includes" : "items include"} review text.${reported}${partial ? " The collection is incomplete or its coverage could not be verified." : " These are the public items returned by this source."}`
      : `${state === "no_reviews" ? "The completed source reports zero public reviews." : state === "private" ? "The source marks this public collection as private or inaccessible." : state === "unconfigured" ? "Connect a supported review source to retrieve public review details." : state === "unavailable" ? "The review source could not complete this check." : "No readable review items were returned."}${reported} An empty collection does not establish that this account has never posted a review.`;
    return { returned, textReturned, totalReported, ratingsReported, contributionsReported, source, limit, limited, state, partial, label, detail, sources };
  }
  emailOutcome.platforms = emailPlatforms;
  emailOutcome.reviews = emailReviews;
  if (typeof module !== "undefined" && module.exports) module.exports = emailOutcome;
  else root.MyReconEmailOutcome = emailOutcome;
})(typeof window !== "undefined" ? window : globalThis);
