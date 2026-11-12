"""Recurring billing lifecycle and separation from legacy/BMC credits."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timezone

import pytest
import config
import app as app_module
from core import subscriptions as sub, paypal, razorpay, plans, store

NOW = 1794432000
SID = "I-TEST12345678"
UID = "dev-test-user"


def iso(seconds):
    return datetime.fromtimestamp(seconds, timezone.utc).isoformat()


@pytest.fixture(autouse=True)
def setup(monkeypatch):
    mem = store._MemoryStore()
    monkeypatch.setattr(store, "store", mem)
    monkeypatch.setattr(plans, "store", mem)
    monkeypatch.setattr(store, "persistent", lambda: True)
    monkeypatch.setattr(sub.time, "time", lambda: NOW)
    monkeypatch.setattr(plans, "_now_ms", lambda: NOW * 1000)
    monkeypatch.setattr(config, "DEV_TEST_ACCOUNT", True)
    monkeypatch.setattr(config, "RATE_LIMIT_ENABLED", False)
    for name, value in {"PAYPAL_CLIENT_ID": "client", "PAYPAL_CLIENT_SECRET": "secret", "PAYPAL_WEBHOOK_ID": "webhook",
                        "PAYPAL_ENV": "sandbox", "RAZORPAY_KEY_ID": "rzp_test_key", "RAZORPAY_KEY_SECRET": "secret",
                        "RAZORPAY_WEBHOOK_SECRET": "hook", "BASIC_RAZORPAY_MONTHLY_PLAN_ID": "plan_basic"}.items():
        monkeypatch.setattr(config, name, value)
    for key in ("MONTHLY_TRIAL", "YEARLY_TRIAL", "MONTHLY_PAID", "YEARLY_PAID"):
        monkeypatch.setattr(config, "BASIC_PAYPAL_" + key + "_PLAN_ID", "P-" + key)


def seed(provider="paypal", plan="monthly", trial=True):
    sid = SID if provider == "paypal" else "sub_TEST123456"
    record = {"id": sid, "provider": provider, "plan": plan, "trial": trial, "status": "pending",
              "binding": "binding", "until": 0, "trial_until": (NOW + 3 * 86400) * 1000}
    store.store.set(sub._user(UID), {"subscription": record})
    store.store.set(sub._path(provider, sid), {**record, "uid": UID, "provider_plan": "provider-plan"})
    return sid


def remote(status="ACTIVE", paid=False, amount="3.99"):
    return {"id": SID, "plan_id": "provider-plan", "custom_id": "binding", "status": status,
            "start_time": iso(NOW), "billing_info": {
                "last_payment": {"time": iso(NOW), "amount": {"currency_code": "USD", "value": amount}} if paid else {},
                "next_billing_time": iso(NOW + (30 if paid else 3) * 86400)}}


def test_catalog_and_fail_closed_without_configuration(monkeypatch):
    assert [(o["amount"], o["scans"]) for o in sub.offers()] == [(399, 10), (1999, 120), (29900, 10), (199900, 120)]
    assert [o["provider"] for o in sub.offers()] == ["paypal", "paypal", "razorpay", "razorpay"]
    assert all(o["trial_days"] == 3 for o in sub.offers())
    monkeypatch.setattr(config, "BASIC_PAYPAL_YEARLY_PAID_PLAN_ID", "")
    assert not sub.enabled("paypal")
    monkeypatch.setattr(config, "RAZORPAY_WEBHOOK_SECRET", "")
    assert not sub.enabled("razorpay")


def test_trial_requires_provider_authorization_then_expires(monkeypatch):
    seed()
    monkeypatch.setattr(paypal, "_call", lambda *a, **k: remote("APPROVAL_PENDING"))
    assert not sub.sync("paypal", SID, UID)["active"]
    monkeypatch.setattr(paypal, "_call", lambda *a, **k: remote())
    assert sub.sync("paypal", SID, UID)["scans_left"] == 3
    assert plans.get_account(UID)["standard_scans_unlimited"]
    assert plans.get_account(UID)["extended_pack_scans_left"] == 0
    monkeypatch.setattr(plans, "_now_ms", lambda: (NOW + 3 * 86400) * 1000)
    assert not plans.get_account(UID)["standard_scans_unlimited"]


@pytest.mark.parametrize("plan,amount,credits", [("monthly", "3.99", 10), ("yearly", "19.99", 120)])
def test_paid_period_and_concurrent_duplicates(monkeypatch, plan, amount, credits):
    seed(plan=plan)
    monkeypatch.setattr(paypal, "_call", lambda *a, **k: remote(paid=True, amount=amount))
    with ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(lambda _: sub.sync("paypal", SID, UID), range(12)))
    assert plans.get_account(UID)["subscription_scans_left"] == credits
    source = plans.consume_extended_scan(UID)
    sub.sync("paypal", SID, UID)
    assert plans.get_account(UID)["subscription_scans_left"] == credits - 1
    plans.refund_full_scan(UID, source)
    assert plans.get_account(UID)["subscription_scans_left"] == credits


def test_wrong_amount_never_grants_paid_period(monkeypatch):
    seed(trial=False)
    monkeypatch.setattr(paypal, "_call", lambda *a, **k: remote(paid=True, amount="0.01"))
    assert not sub.sync("paypal", SID, UID)["active"]


@pytest.mark.parametrize("field,value", [("id", "I-OTHER123456"), ("plan_id", "wrong"), ("custom_id", "other")])
def test_remote_must_match_our_binding(monkeypatch, field, value):
    seed()
    obj = remote(); obj[field] = value
    monkeypatch.setattr(paypal, "_call", lambda *a, **k: obj)
    with pytest.raises(ValueError): sub.sync("paypal", SID, UID)


def test_ownership_checked_before_provider_call(monkeypatch):
    seed()
    monkeypatch.setattr(paypal, "_call", lambda *a, **k: pytest.fail("Must not fetch another account"))
    with pytest.raises(ValueError): sub.sync("paypal", SID, "other")


def test_cancel_keeps_confirmed_trial_and_cannot_reactivate(monkeypatch):
    seed()
    calls = []
    def provider(method, path, **kwargs):
        calls.append((method, path))
        return remote() if method == "GET" else {}
    monkeypatch.setattr(paypal, "_call", provider)
    assert sub.cancel(UID)["status"] == "cancelled"
    assert calls[-1][1].endswith("/cancel")
    assert plans.get_account(UID)["subscription_scans_left"] == 3
    assert sub.sync("paypal", SID, UID)["status"] == "cancelled"
    assert store.store.get(sub._user(UID))["basic_trial_used"] == SID


def test_bmc_pack_survives_subscription_expiry(monkeypatch):
    seed()
    plans.grant_pass(UID, "extended", "bmc:purchase")
    monkeypatch.setattr(paypal, "_call", lambda *a, **k: remote())
    sub.sync("paypal", SID, UID)
    source = plans.consume_extended_scan(UID)
    assert source.startswith("subscription:")
    monkeypatch.setattr(plans, "_now_ms", lambda: (NOW + 4 * 86400) * 1000)
    account = plans.get_account(UID)
    assert account["standard_scans_unlimited"] and account["extended_scans_left"] == 10


def test_renewal_resets_not_stacks_and_old_refund_cannot_add_credits(monkeypatch):
    seed()
    obj = remote(paid=True)
    monkeypatch.setattr(paypal, "_call", lambda *a, **k: obj)
    sub.sync("paypal", SID, UID)
    source = plans.consume_extended_scan(UID)
    obj["billing_info"]["last_payment"]["time"] = iso(NOW + 30 * 86400)
    obj["billing_info"]["next_billing_time"] = iso(NOW + 61 * 86400)
    sub.sync("paypal", SID, UID)
    plans.refund_full_scan(UID, source)
    assert plans.get_account(UID)["subscription_scans_left"] == 10


def test_razorpay_authenticated_trial_and_paid_period(monkeypatch):
    sid = seed("razorpay", "inr_monthly")
    obj = {"id": sid, "plan_id": "provider-plan", "notes": {"binding": "binding"}, "status": "created", "paid_count": 0}
    monkeypatch.setattr(razorpay, "_call", lambda *a, **k: obj)
    assert not sub.sync("razorpay", sid, UID)["active"]
    obj["status"] = "authenticated"
    assert sub.sync("razorpay", sid, UID)["scans_left"] == 3
    obj.update(status="active", paid_count=1, current_start=NOW + 3 * 86400, current_end=NOW + 33 * 86400)
    assert sub.sync("razorpay", sid, UID)["scans_left"] == 10


def test_checkout_consent_auth_and_retired_orders(monkeypatch):
    client = app_module.app.test_client()
    assert client.post("/api/billing/subscriptions", json={"plan": "monthly"}).status_code == 400
    assert client.post("/api/billing/order", json={"plan": "extended"}).status_code == 410
    assert client.post("/api/billing/paypal/order", json={"plan": "extended"}).status_code == 410
    monkeypatch.setattr(config, "DEV_TEST_ACCOUNT", False)
    assert client.post("/api/billing/subscriptions/cancel", json={}).status_code == 401


def test_checkout_server_owns_plan_and_prevents_duplicate(monkeypatch):
    monkeypatch.setattr(sub, "_plan", lambda *a: "server-plan")
    calls = []
    def provider(method, path, **kwargs):
        calls.append(kwargs["json"])
        return {"id": SID, "links": [{"rel": "approve", "href": "https://www.sandbox.paypal.com/webapps/billing/subscriptions?ba_token=x"}]}
    monkeypatch.setattr(paypal, "_call", provider)
    result = sub.checkout(UID, "yearly")
    assert result["amount"] == 1999 and result["trial"]
    assert calls[0]["plan_id"] == "server-plan"
    with pytest.raises(ValueError): sub.checkout(UID, "monthly")
    assert len(calls) == 1


def test_repeat_trial_in_another_subscription_is_rejected(monkeypatch):
    seed()
    store.store.transaction(sub._user(UID), lambda cur: {**cur, "basic_trial_used": "I-PRIOR123456"})
    monkeypatch.setattr(paypal, "_call", lambda *a, **k: remote())
    assert not sub.sync("paypal", SID, UID)["active"]


def test_no_sandbox_sales_or_in_memory_production(monkeypatch):
    monkeypatch.setattr(config, "DEV_TEST_ACCOUNT", False)
    assert not sub.enabled("paypal") and not sub.enabled("razorpay")
    monkeypatch.setattr(config, "PAYPAL_ENV", "live")
    monkeypatch.setattr(config, "RAZORPAY_KEY_ID", "rzp_live_test")
    monkeypatch.setattr(store, "persistent", lambda: False)
    assert not sub.enabled("paypal") and not sub.enabled("razorpay")

@pytest.mark.parametrize('provider,plan', [('paypal','monthly'),('paypal','yearly'),('razorpay','inr_monthly')])
def test_cancelled_trial_expires_at_exact_deadline(monkeypatch,provider,plan):
    sid=seed(provider,plan)
    obj=remote() if provider=='paypal' else {'id':sid,'plan_id':'provider-plan','notes':{'binding':'binding'},'status':'authenticated','paid_count':0}
    module=paypal if provider=='paypal' else razorpay
    monkeypatch.setattr(module,'_call',lambda method,*a,**k: obj if method=='GET' else {})
    assert sub.cancel(UID)['status']=='cancelled'
    deadline=plans.get_account(UID)['subscription_until']
    monkeypatch.setattr(plans,'_now_ms',lambda:deadline-1)
    assert plans.get_account(UID)['subscription_scans_left']==3
    monkeypatch.setattr(plans,'_now_ms',lambda:deadline)
    assert plans.get_account(UID)['subscription_scans_left']==0
    assert not plans.get_account(UID)['standard_scans_unlimited']


def test_razorpay_renewal_failure_and_retry_do_not_stack(monkeypatch):
    sid=seed('razorpay','inr_monthly')
    obj={'id':sid,'plan_id':'provider-plan','notes':{'binding':'binding'},'status':'active','paid_count':1,'current_start':NOW,'current_end':NOW+30*86400}
    monkeypatch.setattr(razorpay,'_call',lambda *a,**k:obj)
    sub.sync('razorpay',sid,UID)
    plans.consume_extended_scan(UID)
    sub.sync('razorpay',sid,UID)
    assert plans.get_account(UID)['subscription_scans_left']==9
    obj.update(status='halted')
    sub.sync('razorpay',sid,UID)
    assert not plans.get_account(UID)['standard_scans_unlimited']

@pytest.mark.parametrize('provider,plan', [('paypal','monthly'),('razorpay','inr_monthly')])
def test_interrupted_checkout_resumes_same_subscription(monkeypatch,provider,plan):
    sid=seed(provider,plan)
    obj=remote('APPROVAL_PENDING') if provider=='paypal' else {'id':sid,'plan_id':'provider-plan','notes':{'binding':'binding'},'status':'created','paid_count':0}
    module=paypal if provider=='paypal' else razorpay
    def provider_call(method,*args,**kwargs):
        assert method=='GET'
        return obj
    monkeypatch.setattr(module,'_call',provider_call)
    result=sub.checkout(UID,plan)
    assert result['id']==sid
    assert result['trial'] is True
    assert plans.get_account(UID)['extended_scans_left']==0


def test_unapproved_paypal_checkout_has_clear_cancellation_message(monkeypatch):
    seed()
    monkeypatch.setattr(paypal,'_call',lambda method,*a,**k:remote('APPROVAL_PENDING'))
    with pytest.raises(ValueError,match='no recurring payment is authorized'):
        sub.cancel(UID)

def test_other_provider_pending_checkout_rejected_before_provider_requests(monkeypatch):
    seed(provider="razorpay", plan="inr_monthly")
    def unexpected(*args, **kwargs):
        pytest.fail("Conflicting checkout must not contact a payment provider")
    monkeypatch.setattr(sub, "_plan", unexpected)
    monkeypatch.setattr(paypal, "_call", unexpected)
    monkeypatch.setattr(razorpay, "_call", unexpected)
    with pytest.raises(ValueError, match="pending checkout"):
        sub.checkout(UID, "monthly")


def _razorpay_fake(remote_status="created", cancel_ok=True, sid="sub_TEST123456"):
    """Fake Razorpay API: tracks calls, supports plan provisioning and cancel."""
    state = {"status": remote_status, "calls": [], "plans": {}, "subs": {}}
    def call(method, path, **kwargs):
        state["calls"].append((method, path, kwargs.get("json")))
        if method == "POST" and path == "/plans":
            plan_id = "plan_YEARLY" + str(len(state["plans"]))
            state["plans"][plan_id] = {"id": plan_id, **kwargs["json"]}
            return state["plans"][plan_id]
        if method == "GET" and path.startswith("/plans/"):
            return state["plans"][path.split("/")[-1]]
        if method == "POST" and path.endswith("/cancel"):
            if not cancel_ok:
                raise razorpay.RazorpayError("HTTP 400 cannot cancel")
            state["status"] = "cancelled"
            return {}
        if method == "POST" and path == "/subscriptions":
            new = "sub_NEWYEARLY" + str(len(state["subs"]))
            state["subs"][new] = kwargs["json"]
            return {"id": new}
        if method == "GET" and path == "/subscriptions/" + sid:
            return {"id": sid, "plan_id": "provider-plan", "notes": {"binding": "binding"},
                    "status": state["status"], "paid_count": 0}
        raise AssertionError("unexpected Razorpay call " + method + " " + path)
    return state, call


def test_razorpay_yearly_offer_is_enabled_and_provisions_verified_plan(monkeypatch):
    offer = next(o for o in sub.offers() if o["id"] == "inr_yearly")
    assert offer["enabled"] and offer["provider"] == "razorpay" and offer["interval"] == "YEAR"
    state, call = _razorpay_fake()
    monkeypatch.setattr(razorpay, "_call", call)
    result = sub.checkout(UID, "inr_yearly")
    assert result["provider"] == "razorpay" and result["amount"] == 199900 and result["trial"]
    created_plan = next(j for m, p, j in state["calls"] if p == "/plans")
    assert created_plan["period"] == "yearly" and created_plan["interval"] == 1
    assert created_plan["item"] == {"name": "MyRecon Pro yearly", "amount": 199900, "currency": "INR"}
    payload = next(iter(state["subs"].values()))
    assert payload["total_count"] == 10 and payload["start_at"] == NOW + 3 * 86400
    # The provisioned plan is cached; a second account reuses it.
    store.store.set(sub._user(UID), {})
    sub.checkout(UID, "inr_yearly")
    assert sum(1 for m, p, j in state["calls"] if p == "/plans") == 1


def test_razorpay_yearly_rejects_mismatched_configured_plan(monkeypatch):
    monkeypatch.setattr(config, "BASIC_RAZORPAY_YEARLY_PLAN_ID", "plan_WRONG")
    monkeypatch.setattr(razorpay, "_call", lambda method, path, **k: {
        "id": "plan_WRONG", "period": "yearly", "interval": 1, "item": {"amount": 29900, "currency": "INR"}})
    with pytest.raises(ValueError, match="does not match"):
        sub.checkout(UID, "inr_yearly")


def test_razorpay_yearly_paid_period_grants_year_of_credits(monkeypatch):
    sid = seed("razorpay", "inr_yearly")
    obj = {"id": sid, "plan_id": "provider-plan", "notes": {"binding": "binding"}, "status": "active",
           "paid_count": 1, "current_start": NOW, "current_end": NOW + 365 * 86400}
    monkeypatch.setattr(razorpay, "_call", lambda *a, **k: obj)
    result = sub.sync("razorpay", sid, UID)
    assert result["scans_left"] == 120 and result["until"] == (NOW + 365 * 86400) * 1000


@pytest.mark.parametrize("target", ["monthly", "yearly", "inr_yearly"])
def test_unauthorized_razorpay_checkout_is_closed_before_switching(monkeypatch, target):
    seed("razorpay", "inr_monthly")
    store.store.transaction(sub._user(UID), lambda cur: {**cur, "subscription": {**cur["subscription"], "status": "created"}})
    state, call = _razorpay_fake()
    monkeypatch.setattr(razorpay, "_call", call)
    paypal_calls = []
    def paypal_call(method, path, **kwargs):
        paypal_calls.append(path)
        return {"id": "I-NEWSUB123456", "links": [{"rel": "approve", "href": "https://www.sandbox.paypal.com/webapps/billing/subscriptions?ba_token=x"}]}
    monkeypatch.setattr(paypal, "_call", paypal_call)
    monkeypatch.setattr(sub, "_plan", lambda provider, key, trial: "server-plan")
    result = sub.checkout(UID, target)
    assert ("POST", "/subscriptions/sub_TEST123456/cancel", {"cancel_at_cycle_end": False}) in state["calls"]
    assert result["provider"] == sub.provider_for(target) and result["id"] != "sub_TEST123456"
    record = store.store.get(sub._user(UID))["subscription"]
    assert record["plan"] == target and record["status"] == "pending"


@pytest.mark.parametrize("remote_status", ["authenticated", "active", "pending"])
def test_authorized_razorpay_subscription_is_never_replaced(monkeypatch, remote_status):
    seed("razorpay", "inr_monthly")
    store.store.transaction(sub._user(UID), lambda cur: {**cur, "subscription": {**cur["subscription"], "status": "created"}})
    state, call = _razorpay_fake(remote_status)
    monkeypatch.setattr(razorpay, "_call", call)
    monkeypatch.setattr(paypal, "_call", lambda *a, **k: pytest.fail("must not create a PayPal subscription"))
    monkeypatch.setattr(sub, "_plan", lambda *a: pytest.fail("must not prepare a new plan"))
    with pytest.raises(ValueError, match="pending checkout"):
        sub.checkout(UID, "monthly")
    assert not any(p.endswith("/cancel") for m, p, j in state["calls"])


def test_failed_close_of_unauthorized_checkout_blocks_new_subscription(monkeypatch):
    seed("razorpay", "inr_monthly")
    store.store.transaction(sub._user(UID), lambda cur: {**cur, "subscription": {**cur["subscription"], "status": "created"}})
    state, call = _razorpay_fake(cancel_ok=False)
    monkeypatch.setattr(razorpay, "_call", call)
    monkeypatch.setattr(paypal, "_call", lambda *a, **k: pytest.fail("must not create a PayPal subscription"))
    monkeypatch.setattr(sub, "_plan", lambda *a: pytest.fail("must not prepare a new plan"))
    with pytest.raises(ValueError, match="could not be closed"):
        sub.checkout(UID, "monthly")
    assert store.store.get(sub._user(UID))["subscription"]["id"] == "sub_TEST123456"


def test_pending_paypal_approval_is_not_replaced_by_razorpay(monkeypatch):
    seed()
    store.store.transaction(sub._user(UID), lambda cur: {**cur, "subscription": {**cur["subscription"], "status": "approval_pending"}})
    monkeypatch.setattr(paypal, "_call", lambda *a, **k: pytest.fail("must not contact PayPal"))
    monkeypatch.setattr(razorpay, "_call", lambda *a, **k: pytest.fail("must not contact Razorpay"))
    monkeypatch.setattr(sub, "_plan", lambda *a: pytest.fail("must not prepare a new plan"))
    with pytest.raises(ValueError, match="pending checkout"):
        sub.checkout(UID, "inr_yearly")


def test_same_razorpay_plan_resumes_instead_of_closing(monkeypatch):
    seed("razorpay", "inr_yearly")
    store.store.transaction(sub._user(UID), lambda cur: {**cur, "subscription": {**cur["subscription"], "status": "created"}})
    state, call = _razorpay_fake()
    monkeypatch.setattr(razorpay, "_call", call)
    assert sub.checkout(UID, "inr_yearly")["id"] == "sub_TEST123456"
    assert [m for m, p, j in state["calls"]] == ["GET"]
