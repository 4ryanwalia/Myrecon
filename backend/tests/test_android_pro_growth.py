"""Trust boundaries, concurrent spending, replay, lifecycle, and privacy."""
from concurrent.futures import ThreadPoolExecutor
import json
import time
import uuid
import pytest
from core import android_growth as g, android_pro as p, store

UID = "anonymous-install-1"
REF = "anonymous-install-2"
CODE = "11111111-1111-1111-1111-111111111111"
REFCODE = "22222222-2222-2222-2222-222222222222"


@pytest.fixture
def db(monkeypatch):
    memory = store._MemoryStore()
    monkeypatch.setattr(g.storage, "store", memory)
    return memory


def remote(state="ACTIVE", phase="freeTrial", expiry="2030-01-01T00:00:00Z"):
    return {"subscriptionState": "SUBSCRIPTION_STATE_" + state,
            "externalAccountIdentifiers": {"obfuscatedExternalAccountId": p.account_id(UID)},
            "lineItems": [{"productId": "myrecon_pro_monthly", "expiryTime": expiry,
                           "autoRenewingPlan": {"autoRenewEnabled": True}, "offerPhase": {phase: {}}}]}


@pytest.mark.parametrize("state,active", [("ACTIVE", True), ("IN_GRACE_PERIOD", True), ("CANCELED", True),
    ("ON_HOLD", False), ("PAUSED", False), ("EXPIRED", False), ("PENDING", False)])
def test_lifecycle(state, active):
    assert p.entitlement(remote(state), UID)["isPro"] is active


def test_trial_uses_current_phase_not_old_offer_id():
    paid = remote(phase="basePrice")
    paid["lineItems"][0]["offerDetails"] = {"offerId": "trial-3d"}
    assert p.entitlement(paid, UID)["trialEndsAtMs"] == 0
    assert p.entitlement(remote(), UID)["trialEndsAtMs"] > 0


def test_expired_trial_denied():
    assert not p.entitlement(remote(expiry="2020-01-01T00:00:00Z"), UID)["isPro"]


def test_purchase_bound_to_installation():
    with pytest.raises(ValueError):
        p.entitlement(remote(), "other-install")


def test_no_pii_in_extracted_entitlement():
    response = remote()
    response["subscribeWithGoogleInfo"] = {"emailAddress": "private@example.org"}
    result = p.entitlement(response, UID, now_ms=1_800_000_000_000)
    assert "private" not in json.dumps(result)
    assert result["verifiedUntilMs"] <= 1_800_000_900_000


def test_code_binding_cannot_be_taken_over(db):
    g.initialize(UID, CODE)
    with pytest.raises(g.proof.Rejected):
        g.initialize(REF, CODE)


def test_award_both_parties_and_replay(db):
    g.initialize(UID, CODE)
    g.initialize(REF, REFCODE)
    for _ in range(3):
        g._award(UID, "welcome", referred_by=REFCODE)
        g._award(REF, "receipt-for-install-1", invited=True)
    assert db.get(g._path(UID))["bonusDeepCredits"] == 2
    assert db.get(g._path(REF))["bonusDeepCredits"] == 2
    assert db.get(g._path(REF))["invitesCompleted"] == 1
    with pytest.raises(g.proof.Rejected):
        g._award(UID, "another-welcome", referred_by=CODE)


def test_banked_cap_can_refill_after_spend(db):
    g.initialize(UID, CODE)
    for i in range(20):
        g._award(UID, str(i), invited=True)
    assert db.get(g._path(UID))["bonusDeepCredits"] == 10
    g.consume(UID, str(uuid.uuid4()))
    g._award(UID, "another-referral", invited=True)
    assert db.get(g._path(UID))["bonusDeepCredits"] == 10
    assert db.get(g._path(UID))["invitesCompleted"] == 21


def test_concurrent_last_credit_never_goes_negative(db):
    g.initialize(UID, CODE)
    g._award(UID, "welcome")
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: g.consume(UID, str(uuid.uuid4()))["consumed"], range(20)))
    assert sum(results) == 2
    assert db.get(g._path(UID))["bonusDeepCredits"] == 0


def test_retry_same_debit_is_idempotent(db):
    g.initialize(UID, CODE)
    g._award(UID, "welcome")
    operation = str(uuid.uuid4())
    assert g.consume(UID, operation)["consumed"]
    assert g.consume(UID, operation)["consumed"]
    assert db.get(g._path(UID))["bonusDeepCredits"] == 1


def test_counts_retries_do_not_double_count_or_accept_content(db):
    body = {"counts": {"qr": 1, "url": 2, "extended": 3, "deep": 4}}
    g.sync_counts(UID, body)
    g.sync_counts(UID, body)
    assert g.storage.store.get("android_installs/" + UID + "/counts") == body["counts"]
    with pytest.raises(g.proof.Rejected):
        g.sync_counts(UID, {"counts": {**body["counts"], "query": "forbidden"}})
    with pytest.raises(g.proof.Rejected):
        g.sync_counts(UID, {"counts": {**body["counts"], "deep": True}})


def test_invalid_referrer_proof_cannot_issue_challenge(db):
    g.initialize(UID, CODE)
    g.initialize(REF, REFCODE)
    with pytest.raises(g.proof.Rejected):
        g.challenge(UID, {"referrer": REFCODE, "installReferrer": "ref=" + CODE})


def test_ledger_contains_no_query_data(db):
    g.initialize(UID, CODE)
    g._award(UID, "welcome", referred_by=REFCODE)
    record = db.get(g._path(UID))
    assert set(record) == {"code", "referredBy", "bonusDeepCredits", "invitesCompleted", "awards", "debits"}
    assert set(g._public(record)) == {"code", "referredBy", "bonusDeepCredits", "invitesCompleted"}


def test_integrity_failure_cannot_award(db, monkeypatch):
    import jwt
    g.initialize(UID, CODE)
    g.initialize(REF, REFCODE)
    monkeypatch.setattr(g.config, "SECRET_KEY", "test-key-" * 8)
    now = int(time.time())
    token = jwt.encode({"purpose": "growth-referral", "uid": UID, "referrerUid": REF,
        "referrer": REFCODE, "username": "example", "iat": now, "exp": now + 180}, g.config.SECRET_KEY, algorithm="HS256")
    monkeypatch.setattr(g.proof, "_decode_integrity", lambda token: {})
    monkeypatch.setattr(g.proof, "_verify_integrity", lambda *args: (_ for _ in ()).throw(g.proof.Rejected()))
    with pytest.raises(g.proof.Rejected):
        g.redeem(UID, {"challenge": token, "integrity_token": "bad-proof"})
    assert db.get(g._path(UID))["bonusDeepCredits"] == 0
    assert db.get(g._path(REF))["bonusDeepCredits"] == 0


def test_partial_award_failure_recovers_without_duplicate_or_query_storage(db, monkeypatch):
    import jwt
    g.initialize(UID, CODE)
    g.initialize(REF, REFCODE)
    monkeypatch.setattr(g.config, "SECRET_KEY", "test-key-" * 8)
    monkeypatch.setattr(g.proof, "_decode_integrity", lambda token: {})
    monkeypatch.setattr(g.proof, "_verify_integrity", lambda *args: None)
    scans = []
    monkeypatch.setattr(g.proof, "_qualifying_scan", lambda query: scans.append(query))
    now = int(time.time())
    token = jwt.encode({"purpose": "growth-referral", "uid": UID, "referrerUid": REF,
        "referrer": REFCODE, "username": "private-handle", "iat": now, "exp": now + 180}, g.config.SECRET_KEY, algorithm="HS256")
    real_award = g._award
    def fail_referrer(uid, *args, **kwargs):
        if uid == REF:
            raise RuntimeError("simulated network failure")
        return real_award(uid, *args, **kwargs)
    monkeypatch.setattr(g, "_award", fail_referrer)
    with pytest.raises(RuntimeError):
        g.redeem(UID, {"challenge": token, "integrity_token": "valid"})
    monkeypatch.setattr(g, "_award", real_award)
    g.redeem(UID, {"challenge": token, "integrity_token": "valid"})
    assert scans == ["private-handle"]
    assert db.get(g._path(UID))["bonusDeepCredits"] == 2
    assert db.get(g._path(REF))["bonusDeepCredits"] == 2
    assert "private-handle" not in json.dumps(db._data)


@pytest.fixture
def pro_client(db, monkeypatch):
    from flask import Flask, request
    from core import responses
    app = Flask(__name__)
    db.backend = "rtdb"
    def identity(token):
        if token != "test-auth":
            raise p.AuthError("bad token")
        return {"sub": UID, "firebase": {"sign_in_provider": "anonymous"}}
    monkeypatch.setattr(p, "verify_id_token", identity)
    monkeypatch.setattr(p.config, "SECRET_KEY", "testing-secret-" * 8)
    p.register_routes(app, lambda: request.get_json(silent=True) or {}, responses)
    return app.test_client()


def test_verify_requires_authenticated_install(pro_client):
    assert pro_client.post("/api/android/pro/verify", json={"purchaseToken": "x"}).status_code == 401


def test_client_cannot_assert_restore_or_pro(pro_client, monkeypatch):
    calls = []
    def verify(uid, token, allow_restore=False):
        calls.append(allow_restore)
        return {"isPro": False}
    monkeypatch.setattr(p, "verify_purchase", verify)
    response = pro_client.post("/api/android/pro/verify", headers={"Authorization": "Bearer test-auth"},
        json={"purchaseToken": "x", "isPro": True, "allow_restore": True})
    assert response.json["isPro"] is False
    assert calls == [False]


def test_restore_proof_must_bind_purchase_and_uid(pro_client, monkeypatch):
    import jwt
    monkeypatch.setattr(p, "verify_purchase", lambda *args, **kwargs: pytest.fail("must not call publisher"))
    now = int(time.time())
    signed = jwt.encode({"purpose": "play-restore", "uid": "another-install", "purchaseHash": "a" * 64,
        "iat": now, "exp": now + 180}, p.config.SECRET_KEY, algorithm="HS256")
    response = pro_client.post("/api/android/pro/verify", headers={"Authorization": "Bearer test-auth"},
        json={"purchaseToken": "x", "challenge": signed, "integrity_token": "y"})
    assert response.status_code == 403


def test_legitimate_restore_requires_verified_integrity(pro_client, monkeypatch):
    import hashlib
    import jwt
    now = int(time.time())
    signed = jwt.encode({"purpose": "play-restore", "uid": UID, "purchaseHash": hashlib.sha256(b"x").hexdigest(),
        "iat": now, "exp": now + 180}, p.config.SECRET_KEY, algorithm="HS256")
    monkeypatch.setattr(p.integrity, "_decode_integrity", lambda token: {"verified": True})
    monkeypatch.setattr(p.integrity, "_verify_integrity", lambda payload, expected: None)
    calls = []
    def verify(uid, token, allow_restore=False):
        calls.append(allow_restore)
        return {"isPro": True}
    monkeypatch.setattr(p, "verify_purchase", verify)
    response = pro_client.post("/api/android/pro/verify", headers={"Authorization": "Bearer test-auth"},
        json={"purchaseToken": "x", "challenge": signed, "integrity_token": "y"})
    assert response.status_code == 200
    assert calls == [True]
