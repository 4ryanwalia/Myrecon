"""Standardized JSON envelopes so every endpoint responds consistently."""

from flask import jsonify


def ok(data: dict, status: int = 200):
    payload = {"status": "ok", **data}
    return jsonify(payload), status


def error(message: str, status: int = 400, code: str = "bad_request"):
    return jsonify({"status": "error", "code": code, "error": message}), status
