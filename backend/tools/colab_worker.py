"""Manually started Colab worker. No server, tunnel, keepalive UI or cloud keys.

This process uses only a dedicated Render worker token, never Firebase,
Google search or payment credentials. Stop the notebook cell to shut it down.
"""
import getpass
import os
import secrets
import sys
import threading
import time
from urllib.parse import urlsplit

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services import scan_engine  # noqa: E402


class LeaseLost(Exception):
    pass


class Worker:
    def __init__(self, api_url, token, concurrency=16, http=None):
        parts = urlsplit(api_url)
        if (parts.scheme != "https" or not parts.hostname or parts.username or parts.password
                or parts.query or parts.fragment or parts.path not in ("", "/")):
            raise ValueError("Use the HTTPS origin of your Render API")
        if len(token) < 32:
            raise ValueError("Use a dedicated worker token of at least 32 characters")
        self.url = api_url.rstrip("/")
        self.token = token
        self.concurrency = max(1, min(32, concurrency))
        self.worker_id = secrets.token_hex(16)
        self.http = http or requests.Session()
        self.catalogues = {scope: scan_engine.fingerprint(scope) for scope in ("standard", "full", "extended")}
        self.catalogues["standard:deep"] = scan_engine.fingerprint("standard", True)

    def call(self, action, payload):
        # Redirects are refused so a worker credential never follows another
        # host. Neither response bodies nor exception URLs are logged.
        for attempt in range(3):
            try:
                response = self.http.post(self.url + "/api/scan-worker/" + action,
                    json=payload, headers={"Authorization": "Bearer " + self.token},
                    timeout=(10, 25), allow_redirects=False)
                if response.status_code == 409:
                    raise LeaseLost()
                if response.status_code in (401, 403, 404, 422):
                    raise ValueError("Worker configuration or payload was refused (HTTP "
                                     + str(response.status_code) + ")")
                if response.status_code == 429 or response.status_code >= 500:
                    if attempt < 2:
                        time.sleep(2 ** attempt)
                        continue
                response.raise_for_status()
                if 300 <= response.status_code < 400:
                    raise ValueError("API redirects are not allowed")
                return response.json()
            except requests.RequestException:
                if attempt == 2:
                    raise RuntimeError("Render could not be reached") from None
                time.sleep(2 ** attempt)

    def execute(self, job):
        if job["fingerprint"] != scan_engine.fingerprint(job["scope"], job["deep"]):
            raise ValueError("Worker bundle does not match the deployed scanner")
        lease = {"job_id": job["id"], "lease_token": job["token"]}
        stop, lost = threading.Event(), threading.Event()

        def renew():
            while not stop.wait(10):
                try:
                    self.call("heartbeat", lease)
                except Exception:
                    lost.set()
                    return

        monitor = threading.Thread(target=renew, daemon=True)
        monitor.start()
        batch, sequence, flushed = [], 0, time.monotonic()
        deadline = {"standard": 120, "full": 300, "extended": 1800}[job["scope"]]
        try:
            for rows in scan_engine.enumerate_batches(job["username"], job["scope"], job["deep"],
                    job.get("names", []), self.concurrency, deadline, lost.is_set):
                # No binary metadata or arbitrary nested data crosses the wire.
                for row in rows:
                    row.pop("profile_pic_data", None)
                batch.extend(rows)
                while len(batch) >= 32:
                    self.call("checkpoint", {**lease, "sequence": sequence, "rows": batch[:32]})
                    del batch[:32]
                    sequence += 1
                    flushed = time.monotonic()
                if batch and time.monotonic() - flushed >= 10:
                    self.call("checkpoint", {**lease, "sequence": sequence, "rows": batch})
                    batch, sequence, flushed = [], sequence + 1, time.monotonic()
                if lost.is_set():
                    raise LeaseLost()
            if batch:
                self.call("checkpoint", {**lease, "sequence": sequence, "rows": batch})
            if lost.is_set():
                raise LeaseLost()
            self.call("complete", lease)
            print("Platform checks uploaded. Render will finish the report.")
        except KeyboardInterrupt:
            try:
                self.call("release", lease)
            except Exception:
                pass
            raise
        except LeaseLost:
            print("Lease ended. The coordinator will handle this job.")
        except Exception:
            try:
                self.call("release", lease)
            except Exception:
                pass
            raise
        finally:
            stop.set()
            monitor.join(timeout=1)

    def run(self, duration_minutes=60):
        end = time.monotonic() + max(1, min(240, duration_minutes)) * 60
        print("CPU worker started for this session. Stop the cell to disconnect.")
        try:
            while time.monotonic() < end:
                response = self.call("claim", {"worker_id": self.worker_id,
                    "catalogues": self.catalogues, "protocol": scan_engine.PROTOCOL})
                job = response.get("job")
                if job:
                    print("Running a " + job["scope"] + " scan.")
                    self.execute(job)
                else:
                    time.sleep(10)
        finally:
            self.http.close()
            self.token = ""
            print("Worker stopped. New scans use Render's bounded fallback.")


if __name__ == "__main__":
    url = input("Render API origin (https://...): ").strip()
    credential = getpass.getpass("Dedicated worker token (not saved): ").strip()
    worker = Worker(url, credential)
    credential = ""
    worker.run()
