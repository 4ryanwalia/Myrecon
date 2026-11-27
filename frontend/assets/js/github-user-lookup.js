/* GitHub user lookup for /find/github-profile.
 * Calls GitHub's public REST API (GET /users/{username}) directly from the
 * visitor's browser. Nothing is sent to MyRecon. GitHub documents an
 * unauthenticated limit of 60 requests per hour per IP address.
 */
(function () {
  "use strict";
  var form = document.getElementById("gh-lookup-form");
  if (!form) return;
  var input = document.getElementById("gh-lookup-input");
  var out = document.getElementById("gh-lookup-result");
  var button = form.querySelector("button");

  function el(tag, text, cls) {
    var node = document.createElement(tag);
    if (text != null) node.textContent = text;
    if (cls) node.className = cls;
    return node;
  }

  function show(nodes) {
    out.replaceChildren.apply(out, nodes);
    out.hidden = false;
  }

  function utcDate(value) {
    var d = new Date(value);
    if (isNaN(d.getTime())) return "not shown";
    return d.toISOString().slice(0, 10) + " (UTC)";
  }

  function row(label, value) {
    var tr = el("tr");
    tr.appendChild(el("th", label));
    var td = el("td");
    if (value instanceof Node) td.appendChild(value); else td.textContent = value;
    tr.appendChild(td);
    return tr;
  }

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    var name = (input.value || "").trim().replace(/^@/, "").replace(/^https?:\/\/(www\.)?github\.com\//i, "").split(/[/?#]/)[0];
    if (!/^[A-Za-z0-9-]{1,39}$/.test(name)) {
      show([el("p", "Enter a GitHub username: letters, numbers and hyphens, up to 39 characters.")]);
      return;
    }
    button.disabled = true;
    show([el("p", "Asking GitHub about " + name + "...")]);
    fetch("https://api.github.com/users/" + encodeURIComponent(name), {
      headers: { Accept: "application/vnd.github+json" },
      credentials: "omit",
      referrerPolicy: "no-referrer"
    }).then(function (res) {
      var remaining = res.headers.get("x-ratelimit-remaining");
      if (res.status === 404) {
        show([el("p", "GitHub returned 404: there is no public account called " + name + " right now. The name may be free, renamed or deleted; GitHub does not say which.")]);
        return null;
      }
      if (res.status === 403 || res.status === 429) {
        var reset = Number(res.headers.get("x-ratelimit-reset"));
        var when = reset ? new Date(reset * 1000).toISOString().slice(11, 16) + " UTC" : "later";
        show([el("p", "GitHub's hourly limit for your network has been used up (" + (remaining || "0") + " requests left). Try again after " + when + ", or open github.com/" + name + " directly.")]);
        return null;
      }
      if (!res.ok) {
        show([el("p", "GitHub answered with HTTP " + res.status + ", so no result is shown.")]);
        return null;
      }
      return res.json().then(function (u) { return { u: u, remaining: remaining }; });
    }).then(function (data) {
      if (!data) return;
      var u = data.u;
      var link = el("a", "github.com/" + u.login);
      link.href = u.html_url;
      link.rel = "noopener noreferrer";
      link.target = "_blank";
      var table = el("table");
      var body = el("tbody");
      [
        row("Profile", link),
        row("Account type", u.type || "not shown"),
        row("Display name", u.name || "none set"),
        row("Account created", utcDate(u.created_at)),
        row("Last profile update", utcDate(u.updated_at)),
        row("Public repositories", String(u.public_repos)),
        row("Followers / following", u.followers + " / " + u.following)
      ].forEach(function (r) { body.appendChild(r); });
      table.appendChild(body);
      var note = el("p", "Source: GitHub REST API, requested from your browser just now. A matching username is a lead, not proof of who runs the account." + (data.remaining ? " Requests left this hour on your network: " + data.remaining + "." : ""), "gh-lookup-note");
      show([table, note]);
    }).catch(function () {
      show([el("p", "Could not reach api.github.com from this browser. An extension or network filter may be blocking it.")]);
    }).then(function () { button.disabled = false; });
  });
})();
