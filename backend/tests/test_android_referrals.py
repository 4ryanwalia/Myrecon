"""Attested, server-qualified grants must fail closed and stay idempotent."""
import copy
import time
import jwt
import pytest
from core import android_referrals as r

OWN = "11111111-1111-1111-1111-111111111111"
REF = "22222222-2222-2222-2222-222222222222"
KEY = "a" * 64

class Store:
    backend = "rtdb"
    def __init__(self): self.data = {}
    def get(self, path):
        node = self.data
        for key in path.split("/"):
            if not isinstance(node, dict): return None
            node = node.get(key)
        return copy.deepcopy(node)
    def transaction(self, path, callback):
        self.data[path] = callback(copy.deepcopy(self.data.get(path)))

@pytest.fixture
def setup(monkeypatch):
    store = Store()
    monkeypatch.setattr(r.storage, "store", store)
    monkeypatch.setattr(r.config, "SECRET_KEY", "test-secret-for-referrals-" * 3)
    monkeypatch.setattr(r.config, "FIREBASE_SERVICE_ACCOUNT", "configured-in-test")
    monkeypatch.setenv("ANDROID_REFERRAL_CERT_SHA256", "ab" * 32)
    monkeypatch.setattr(r, "_qualifying_scan", lambda username: None)
    return store

def challenge():
    return r.challenge(dict(own_code=OWN, referrer=REF, claim_key=KEY, username="example"))["challenge"]

def verdict(token):
    return dict(requestDetails=dict(requestPackageName=r.PACKAGE, requestHash=r.request_hash(token),
        timestampMillis=str(int(time.time()*1000))),
        appIntegrity=dict(appRecognitionVerdict="PLAY_RECOGNIZED", packageName=r.PACKAGE,
            versionCode="5", certificateSha256Digest=list(r._certificates())),
        accountDetails=dict(appLicensingVerdict="LICENSED"),
        deviceIntegrity=dict(deviceRecognitionVerdict=["MEETS_DEVICE_INTEGRITY"]))

def test_grant_atomic_idempotent_and_no_query_retention(setup, monkeypatch):
    token = challenge()
    monkeypatch.setattr(r, "_decode_integrity", lambda proof: verdict(token))
    body = dict(challenge=token, integrity_token="proof")
    assert r.redeem(body) == {"claim": "counted"}
    assert r.redeem(body) == {"claim": "already_counted"}
    data = setup.data["android_referrals"]
    assert data["grants"] == {REF: True}
    assert list(data["claims"]) == [KEY]
    assert set(data["claims"][KEY]) == {"referrer", "at"}

@pytest.mark.parametrize("section,field,value", [
    ("requestDetails", "requestHash", "another-request"),
    ("requestDetails", "requestPackageName", "another.app"),
    ("requestDetails", "timestampMillis", "0"),
    ("appIntegrity", "packageName", "another.app"),
    ("appIntegrity", "appRecognitionVerdict", "UNRECOGNIZED_VERSION"),
    ("appIntegrity", "versionCode", "4"),
    ("appIntegrity", "certificateSha256Digest", ["other"]),
    ("appIntegrity", "certificateSha256Digest", "malformed"),
    ("accountDetails", "appLicensingVerdict", "UNLICENSED"),
    ("deviceIntegrity", "deviceRecognitionVerdict", []),
])
def test_invalid_attestation_never_scans_or_writes(setup, monkeypatch, section, field, value):
    token = challenge(); payload = verdict(token); payload[section][field] = value
    monkeypatch.setattr(r, "_decode_integrity", lambda proof: payload)
    monkeypatch.setattr(r, "_qualifying_scan", lambda username: pytest.fail("invalid proof scanned"))
    with pytest.raises(r.Rejected): r.redeem(dict(challenge=token, integrity_token="proof"))
    assert setup.data == {}

def test_server_scan_failure_does_not_consume_invite(setup, monkeypatch):
    token = challenge()
    monkeypatch.setattr(r, "_decode_integrity", lambda proof: verdict(token))
    def fail(username): raise r.Unavailable()
    monkeypatch.setattr(r, "_qualifying_scan", fail)
    with pytest.raises(r.Unavailable): r.redeem(dict(challenge=token, integrity_token="proof"))
    assert setup.data == {}

def test_signed_fields_cannot_be_replaced(setup, monkeypatch):
    token = challenge()
    fields = jwt.decode(token, options={"verify_signature": False}); fields["referrer"] = OWN
    forged = jwt.encode(fields, "wrong-key", algorithm="HS256")
    monkeypatch.setattr(r, "_decode_integrity", lambda proof: pytest.fail("forged challenge decoded"))
    with pytest.raises(r.Rejected): r.redeem(dict(challenge=forged, integrity_token="proof"))
    assert setup.data == {}

def test_duplicate_still_requires_attestation(setup, monkeypatch):
    setup.data["android_referrals"] = {"claims": {KEY: {"referrer": REF}}}
    token = challenge()
    monkeypatch.setattr(r, "_decode_integrity", lambda proof: {})
    with pytest.raises(r.Rejected): r.redeem(dict(challenge=token, integrity_token="invalid"))

def test_legacy_claim_not_recredited(setup, monkeypatch):
    setup.data["claims"] = {KEY: {"referrer": REF}}
    token = challenge()
    monkeypatch.setattr(r, "_decode_integrity", lambda proof: verdict(token))
    monkeypatch.setattr(r, "_qualifying_scan", lambda username: pytest.fail("legacy claim rescanned"))
    assert r.redeem(dict(challenge=token, integrity_token="proof")) == {"claim": "already_counted"}
    assert "android_referrals" not in setup.data

def test_memory_and_missing_cert_fail_closed(setup, monkeypatch):
    setup.backend = "memory"
    with pytest.raises(r.Unavailable): challenge()
    setup.backend = "rtdb"; monkeypatch.delenv("ANDROID_REFERRAL_CERT_SHA256")
    with pytest.raises(r.Unavailable): challenge()

@pytest.mark.parametrize("changes", [{"referrer": OWN}, {"claim_key": "invalid"}, {"own_code": "invalid"}])
def test_invalid_capture_rejected(setup, changes):
    body = dict(own_code=OWN, referrer=REF, claim_key=KEY, username="example"); body.update(changes)
    with pytest.raises(r.Rejected): r.challenge(body)
