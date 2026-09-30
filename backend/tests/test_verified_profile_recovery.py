"""Account recovery must reject the same site's missing and ambiguous pages."""
import json
from pathlib import Path
import sys
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))
from modules.profile_identity import profile_identity, reddit_identity
from modules.sweep import CATALOGUE, Sweep
from modules.username_checker import UsernameChecker

HANDLE = "4ryanwalia"
BMC_URL = f"https://buymeacoffee.com/{HANDLE}"
OSM_URL = f"https://www.openstreetmap.org/user/{HANDLE}"


def creator_page(**changes):
    account = {"slug": HANDLE, "user_id": 846596, "project_id": 846673,
               "active": 1, "deleted": False}
    account.update(changes)
    app = {"component": "Home/HomeLayout", "props": {"creator_data": {"data": account}}}
    return '<title>Aryan Walia is Artist</title><script type="application/json" data-page="app">' + json.dumps(app) + '</script>'


def osm_page(handle=HANDLE, uid="22551468", frame_handle=None):
    frame_handle = handle if frame_handle is None else frame_handle
    return (f'<title>{handle} | OpenStreetMap</title><body class="users users-show">'
            f'<turbo-frame id="user_{uid}_heatmap" src="/user/{frame_handle}/heatmap"></turbo-frame>')


def response(body, url, status=200):
    resp = Mock(status_code=status, encoding="utf-8", url=url, text=body)
    resp.__enter__ = Mock(return_value=resp)
    resp.__exit__ = Mock(return_value=False)
    encoded = body.encode("utf-8")
    resp.iter_content.return_value = iter(encoded[i:i + 16384] for i in range(0, len(encoded), 16384))
    return resp


@pytest.fixture
def sweep():
    instance = Sweep(HANDLE)
    yield instance
    instance.session.close()


def platform(name):
    return next(p for p in CATALOGUE if p["name"] == name)


def test_bmc_exact_active_creator_object_is_supported():
    assert profile_identity("Buymeacoffee", creator_page(), BMC_URL, HANDLE)


@pytest.mark.parametrize("changes", [
    {"slug": "other"}, {"slug": None}, {"user_id": "846596"},
    {"user_id": True}, {"user_id": 0}, {"user_id": -1}, {"user_id": None},
    {"project_id": "846673"}, {"project_id": True}, {"project_id": 0},
    {"active": 0}, {"active": True}, {"active": "1"},
    {"deleted": True}, {"deleted": None}, {"deleted": 0},
])
def test_bmc_untyped_or_inactive_creator_is_never_supported(changes):
    assert not profile_identity("Buymeacoffee", creator_page(**changes), BMC_URL, HANDLE)


@pytest.mark.parametrize("raw", [
    '<script type="application/json" data-page="app">{broken}</script>',
    creator_page()[:-20],
    creator_page().replace('"Home/HomeLayout"', '"Error"'),
    creator_page().replace('data-page="app"', 'data-page="another"'),
    creator_page().replace('"creator_data"', '"unrelated_data"'),
    f'<title>{HANDLE}</title><link rel="canonical" href="{BMC_URL}"><meta property="og:type" content="profile">',
])
def test_bmc_shell_wrong_object_and_truncated_json_cannot_confirm(raw):
    assert not profile_identity("Buymeacoffee", raw, BMC_URL, HANDLE)


@pytest.mark.parametrize("url", [
    "https://buymeacoffee.com/other", "https://buymeacoffee.com/login",
    f"https://buymeacoffee.com/{HANDLE}/posts", f"https://elsewhere.test/{HANDLE}",
    f"http://buymeacoffee.com/{HANDLE}",
])
def test_bmc_account_object_on_wrong_destination_is_not_supported(url):
    assert not profile_identity("Buymeacoffee", creator_page(), url, HANDLE)


def test_osm_title_and_numeric_account_frame_confirm_exact_profile():
    assert profile_identity("OpenStreetMap", osm_page(), OSM_URL, HANDLE)


@pytest.mark.parametrize("raw", [
    f'<title>{HANDLE} | OpenStreetMap</title><body class="users users-show">',
    osm_page(handle="other"), osm_page(uid="0"), osm_page(uid="arbitrary"),
    osm_page(frame_handle="other"),
    osm_page().replace(f'/user/{HANDLE}/heatmap', f'https://elsewhere.test/user/{HANDLE}/heatmap'),
    '<title>No such user | OpenStreetMap</title><body class="users users-show">',
])
def test_osm_title_echo_shared_class_or_mismatched_frame_are_not_identity(raw):
    assert not profile_identity("OpenStreetMap", raw, OSM_URL, HANDLE)


def test_osm_exact_markup_on_different_profile_destination_is_rejected():
    assert not profile_identity("OpenStreetMap", osm_page(), "https://www.openstreetmap.org/user/other", HANDLE)


@pytest.mark.parametrize("name,body,url", [
    ("Buymeacoffee", "<!--" + "padding " * 8000 + "-->" + creator_page(), BMC_URL),
    ("OpenStreetMap", osm_page(), OSM_URL),
], ids=["creator_beyond_old_peek", "osm_account_frame"])
def test_sweep_recovers_exact_profile_without_differential_fallback(sweep, name, body, url):
    sweep._html_get = Mock(return_value=response(body, url))
    sweep._control_shape = Mock(side_effect=AssertionError("Exact identity needs no heuristic control"))
    hit = sweep.probe(platform(name))
    assert hit["verdict"] == "found"
    assert hit["reason_code"] == "profile_markup"
    assert hit["confidence"] == "high"


@pytest.mark.parametrize("name,body,url", [
    ("Buymeacoffee", creator_page(), BMC_URL),
    ("OpenStreetMap", osm_page(), OSM_URL),
])
@pytest.mark.parametrize("status,prefix,redirect,reason", [
    (403, "", None, "blocked"), (429, "", None, "blocked"),
    (200, "checking your browser", None, "challenge"),
    (200, "sign in to continue", None, "login_wall"),
    (200, "", "/login", "login_wall"),
])
def test_sweep_walls_and_blocks_outrank_embedded_account(sweep, name, body, url, status, prefix, redirect, reason):
    final_url = url if redirect is None else url.rsplit("/", 1)[0] + redirect
    sweep._html_get = Mock(return_value=response(prefix + body, final_url, status))
    hit = sweep.probe(platform(name))
    assert hit["verdict"] == "unknown"
    assert hit["exists"] is False
    assert hit["reason_code"] == reason


@pytest.mark.parametrize("name,url", [("Buymeacoffee", BMC_URL), ("OpenStreetMap", OSM_URL)])
def test_sweep_explicit_absence_stays_absent(sweep, name, url):
    sweep._html_get = Mock(return_value=response("<title>No such user</title>", url, 404))
    assert sweep.probe(platform(name))["verdict"] == "not_found"


@pytest.mark.parametrize("name,body,url", [
    ("Buymeacoffee", f'<title>{HANDLE}</title><meta property="og:type" content="profile">', BMC_URL),
    ("OpenStreetMap", f'<title>{HANDLE} | OpenStreetMap</title>', OSM_URL),
    ("Buymeacoffee", creator_page(slug="other"), BMC_URL),
])
def test_sweep_ambiguous_identity_never_falls_back_to_generic_positive(sweep, name, body, url):
    sweep._html_get = Mock(return_value=response(body, url))
    sweep._control_shape = Mock(side_effect=AssertionError("Do not manufacture a differential hit"))
    hit = sweep.probe(platform(name))
    assert hit["verdict"] == "unknown"
    assert hit["reason_code"] == "ambiguous"


def reddit_payload(**changes):
    account = {"name": HANDLE, "id": "abc123"}
    account.update(changes)
    return json.dumps({"kind": "t2", "data": account})


def test_reddit_exact_typed_account_confirms_handle():
    assert reddit_identity(reddit_payload(), HANDLE)


@pytest.mark.parametrize("body", [
    reddit_payload(name="other"), reddit_payload(id=123), reddit_payload(id=""),
    reddit_payload(id="t2_abc123"), '{broken}', 'null', '[]',
    json.dumps({"kind": "Listing", "data": {"name": HANDLE, "id": "abc123"}}),
    json.dumps({"unrelated": {"name": HANDLE, "id": "abc123"}}),
])
def test_reddit_nested_echo_wrong_account_or_untyped_id_cannot_confirm(body):
    assert not reddit_identity(body, HANDLE)


@pytest.mark.parametrize("body,supported", [(reddit_payload(), True), (reddit_payload(name="other"), False)])
def test_sweep_reddit_api_requires_exact_account(sweep, body, supported):
    sweep.session.get = Mock(return_value=response(body, f"https://www.reddit.com/user/{HANDLE}/about.json"))
    hit = sweep._probe_api(platform("Reddit"), HANDLE)
    if supported:
        assert hit["verdict"] == "found"
        assert hit["reason_code"] == "api_user"
    else:
        assert hit is None


@pytest.mark.parametrize("body,status,supported", [
    (creator_page(), 200, True),
    (f'<title>{HANDLE}</title><link rel="canonical" href="{BMC_URL}"><meta property="og:type" content="profile">', 200, False),
    (creator_page(), 403, False),
    ("checking your browser" + creator_page(), 200, False),
    ("sign in to continue" + creator_page(), 200, False),
])
def test_quick_checker_bmc_requires_exact_creator_and_unblocked_response(monkeypatch, body, status, supported):
    monkeypatch.setattr("modules.username_checker.requests.get", Mock(return_value=response(body, BMC_URL, status)))
    hit = UsernameChecker(delay=0)._check_platform("Buymeacoffee", BMC_URL, 200, HANDLE)
    assert hit["exists"] is supported
    if supported:
        assert hit["confidence"] == "high"
