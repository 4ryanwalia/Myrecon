/**
 * MyRecon worker health monitor for the owner-only Apps Script project.
 *
 * Set these Script Properties in Project Settings before running
 * installWorkerHealthMonitor():
 *   MYRECON_SCAN_STATUS_TOKEN  - the separate Render status token
 *   MYRECON_ALERT_EMAIL        - the inbox that should receive alerts
 *
 * The token stays server-side in Script Properties. It is never returned to
 * the launcher HTML, Colab notebook, or installed web app.
 */
const MYRECON_WORKER_STATUS_URL = "https://myrecon.onrender.com/api/operator/scan-workers";
const MYRECON_WORKER_STATE_PROPERTY = "MYRECON_WORKER_HEALTH_STATE";

function installWorkerHealthMonitor() {
  const triggers = ScriptApp.getProjectTriggers();
  triggers.filter((trigger) => trigger.getHandlerFunction() === "runWorkerHealthCheck")
    .forEach((trigger) => ScriptApp.deleteTrigger(trigger));
  ScriptApp.newTrigger("runWorkerHealthCheck").timeBased().everyMinutes(5).create();
  runWorkerHealthCheck();
}

function removeWorkerHealthMonitor() {
  ScriptApp.getProjectTriggers()
    .filter((trigger) => trigger.getHandlerFunction() === "runWorkerHealthCheck")
    .forEach((trigger) => ScriptApp.deleteTrigger(trigger));
}

function runWorkerHealthCheck() {
  const properties = PropertiesService.getScriptProperties();
  const token = properties.getProperty("MYRECON_SCAN_STATUS_TOKEN");
  const recipient = properties.getProperty("MYRECON_ALERT_EMAIL");
  if (!token || !recipient) {
    throw new Error("Set MYRECON_SCAN_STATUS_TOKEN and MYRECON_ALERT_EMAIL in Script Properties first.");
  }

  const prior = readState(properties);
  let body;
  try {
    const response = UrlFetchApp.fetch(MYRECON_WORKER_STATUS_URL, {
      headers: { Authorization: "Bearer " + token },
      muteHttpExceptions: true,
    });
    if (response.getResponseCode() !== 200) throw new Error("status endpoint returned " + response.getResponseCode());
    body = JSON.parse(response.getContentText());
    if (body.status !== "ok" || !Array.isArray(body.workers)) throw new Error("unexpected status response");
  } catch (error) {
    const next = { api: "unavailable", workers: prior.workers || {} };
    properties.setProperty(MYRECON_WORKER_STATE_PROPERTY, JSON.stringify(next));
    if (prior.api !== "unavailable") {
      send(recipient, "MyRecon worker monitor cannot reach Render", "The health monitor could not read the worker status. Render or the monitor endpoint may be unavailable. It will retry automatically.");
    }
    return;
  }

  const nextWorkers = {};
  const alerts = [];
  for (const worker of body.workers) {
    const label = String(worker.label || "Colab worker");
    const state = String(worker.state || "offline");
    const previous = prior.workers && prior.workers[label];
    nextWorkers[label] = state;
    if (isDown(state) && previous && !isDown(previous)) {
      alerts.push(label + " is " + state + ". Render last heard from it " + worker.age_seconds + " seconds ago and will use the fallback.");
    } else if (!isDown(state) && previous && isDown(previous)) {
      alerts.push(label + " is back: " + state + ".");
    }
  }
  for (const label in prior.workers || {}) {
    if (!(label in nextWorkers)) {
      nextWorkers[label] = "offline";
      if (!isDown(prior.workers[label])) alerts.push(label + " is no longer reporting and is treated as offline.");
    }
  }
  properties.setProperty(MYRECON_WORKER_STATE_PROPERTY, JSON.stringify({ api: "ok", workers: nextWorkers }));
  if (prior.api === "unavailable") alerts.unshift("Render worker monitoring is reachable again.");
  if (alerts.length) send(recipient, "MyRecon worker health update", alerts.join("\n\n"));
}

function sendWorkerHealthTest() {
  const recipient = PropertiesService.getScriptProperties().getProperty("MYRECON_ALERT_EMAIL");
  if (!recipient) throw new Error("Set MYRECON_ALERT_EMAIL in Script Properties first.");
  send(recipient, "MyRecon worker health test", "The MyRecon Apps Script health monitor can send alerts to this inbox.");
}

function readState(properties) {
  try {
    const state = JSON.parse(properties.getProperty(MYRECON_WORKER_STATE_PROPERTY) || "{}");
    return { api: state.api || "new", workers: state.workers || {} };
  } catch (_) {
    return { api: "new", workers: {} };
  }
}

function isDown(state) {
  return state === "offline" || state === "stopped";
}

function send(recipient, subject, body) {
  MailApp.sendEmail({ to: recipient, subject: subject, body: body, name: "MyRecon Worker Monitor" });
}
