"""Synthetic public Maps response contracts; no personal targets or network."""
import copy
import json
from datetime import datetime, timezone

import pytest
import requests

from modules import email_maps_public as maps

CONTRIBUTOR = "100000000000000000001"
OTHER = "100000000000000000002"
MICROS = 1_577_836_800_123_456  # 2020-01-01 00:00:00.123456 UTC


def review(review_id="fixture-review", comment="Example public review", rating=4, micros=MICROS):
    body = [None] * 16
    body[0], body[15] = [rating], [[comment]] if comment is not None else None
    row = [None] * 5
    row[1] = [[None, "ChIJExamplePlace"]]
    row[2] = [review_id, [None, None, None, micros], body]
    row[4] = [[None, None, 10, 20], None, "Example Cafe", "Example Street"]
    return row


def payload(rows=None, reviews=1, ratings=0, token=None):
    context = [None] * 9
    context[0], context[1] = "Example Contributor", f"https://www.google.com/maps/contrib/{CONTRIBUTOR}/reviews"
    counts = []
    for name, count in (("Reviews", reviews), ("Ratings", ratings), ("Answers", 7)):
        counts.append([None, None, None, None, None, None, name, count])
    context[8] = [counts]
    data = [None] * 46
    data[16], data[45] = context, [[review()] if rows is None else rows, token]
    return data


class Reply:
    def __init__(self, document=None, status=200, chunks=None):
        self.status_code, self.closed = status, False
        self.chunks = chunks if chunks is not None else [b")]}'\n" + json.dumps(document).encode()]

    def iter_content(self, size):
        assert size == 8192
        yield from self.chunks

    def close(self):
        self.closed = True


def test_projects_review_rating_exact_utc_and_source_links():
    result = maps.normalize_public_maps_reviews(payload(), CONTRIBUTOR)
    assert result["status"] == "ok" and result["returned"] == 1
    assert result["stats"] == {"Reviews": 1, "Ratings": 0, "Answers": 7}
    assert result["display_name"] == "Example Contributor"
    assert result["limited"] is False
    item = result["reviews"][0]
    assert item["date"] == "2020-01-01T00:00:00.123456Z"
    assert item["rating"] == 4 and item["latitude"] == 10 and item["longitude"] == 20
    assert item["source_url"] == f"https://www.google.com/maps/contrib/{CONTRIBUTOR}/place/ChIJExamplePlace"
    assert "query_place_id=ChIJExamplePlace" in item["maps_url"]
    assert item["text"] == "Example public review"


def test_rating_only_records_count_as_ratings():
    result = maps.normalize_public_maps_reviews(payload([review(comment=None)], reviews=0, ratings=1), CONTRIBUTOR)
    assert result["status"] == "ok" and result["returned"] == 1
    assert "text" not in result["reviews"][0]


@pytest.mark.parametrize("broken", [None, {}, [], [None], [None, None]])
def test_missing_or_malformed_review_section_remains_unknown(broken):
    data = payload()
    data[45] = broken
    result = maps.normalize_public_maps_reviews(data, CONTRIBUTOR)
    assert result["status"] == "unknown" and result["returned"] == 0
    assert "private" not in result and result["limited"]


def test_zero_requires_explicit_zero_review_and_rating_counts():
    assert maps.normalize_public_maps_reviews(payload([], 0, 0), CONTRIBUTOR)["status"] == "ok"
    for data in (payload([], 1, 0), payload([], 0, 2)):
        assert maps.normalize_public_maps_reviews(data, CONTRIBUTOR)["status"] == "unknown"
    data = payload([], 0, 0)
    data[16][8] = None
    assert maps.normalize_public_maps_reviews(data, CONTRIBUTOR)["status"] == "unknown"


@pytest.mark.parametrize("context", [None, [], [None], [False], [123]])
def test_requires_readable_public_contributor_context(context):
    data = payload()
    data[16] = context
    assert maps.normalize_public_maps_reviews(data, CONTRIBUTOR)["status"] == "unknown"


@pytest.mark.parametrize("exposed", [f"https://www.google.com/maps/contrib/{OTHER}/reviews", {"contributor_id": OTHER}, {"gaia_id": OTHER}, {"personId": OTHER}])
def test_explicit_contributor_mismatch_is_rejected(exposed):
    data = payload()
    data[16][1] = exposed
    result = maps.normalize_public_maps_reviews(data, CONTRIBUTOR)
    assert result["status"] == "unknown" and result["reviews"] == []
    assert "did not match" in result["reason"]


@pytest.mark.parametrize("contributor_id", [None, 123, True, "fixture@example.com", "123", CONTRIBUTOR + "/reviews", CONTRIBUTOR + "\n", "１" * 21])
def test_invalid_id_never_starts_request(monkeypatch, contributor_id):
    monkeypatch.setattr(maps.requests, "get", lambda *a, **k: pytest.fail("No guessed IDs"))
    result = maps.fetch_public_maps_reviews(contributor_id)
    assert result["status"] == "unknown" and result["contributor_id"] == ""


@pytest.mark.parametrize("micros", [None, True, "1577836800000000", -1, 0, 1, 10 ** 40, 10 ** 18, float("nan"), 1.5])
def test_malformed_or_future_dates_are_omitted(micros):
    result = maps.normalize_public_maps_reviews(payload([review(micros=micros)]), CONTRIBUTOR)
    assert result["returned"] == 1 and "date" not in result["reviews"][0]


def test_dates_do_not_invent_relative_time_labels():
    timestamp = int(datetime(2021, 2, 3, tzinfo=timezone.utc).timestamp()) * 1_000_000
    item = maps.normalize_public_maps_reviews(payload([review(micros=timestamp)]), CONTRIBUTOR)["reviews"][0]
    assert item["date"] == "2021-02-03T00:00:00Z" and "date_label" not in item


@pytest.mark.parametrize("rating", [True, 0, 6, 3.5, "4", float("nan"), float("inf"), 10 ** 1000])
def test_bad_ratings_are_not_forwarded(rating):
    item = maps.normalize_public_maps_reviews(payload([review(rating=rating)]), CONTRIBUTOR)["reviews"][0]
    assert "rating" not in item


@pytest.mark.parametrize("coords", [(True, 20), (10, False), (91, 20), (10, -181), (float("nan"), 20), (10, float("inf")), ("10", 20)])
def test_coordinate_pair_must_be_finite_valid_numbers(coords):
    row = review()
    row[4][0][2:4] = coords
    item = maps.normalize_public_maps_reviews(payload([row]), CONTRIBUTOR)["reviews"][0]
    assert "latitude" not in item and "longitude" not in item


def test_no_unvalidated_place_url_or_private_fields_are_exported():
    row = review()
    row[1][0][1] = "https://evil.example/PRIVATE"
    row[4][0][2:4] = [None, None]
    row.append({"password": "PRIVATE", "email": "PRIVATE", "cookies": "PRIVATE"})
    result = maps.normalize_public_maps_reviews(payload([row]), CONTRIBUTOR)
    assert "PRIVATE" not in json.dumps(result)
    assert "maps_url" not in result["reviews"][0]
    assert result["reviews"][0]["source_url"] == f"https://www.google.com/maps/contrib/{CONTRIBUTOR}/reviews"


def test_specific_contributor_place_link_and_stable_public_review_id():
    item = maps.normalize_public_maps_reviews(payload([review("CiExample_Public-Review")]), CONTRIBUTOR)["reviews"][0]
    assert item["id"] == "CiExample_Public-Review"
    assert item["source_url"] == f"https://www.google.com/maps/contrib/{CONTRIBUTOR}/place/ChIJExamplePlace"


@pytest.mark.parametrize("review_id", ["<invalid PRIVATE>", "x" * 501, "id\x00value"])
def test_unreadable_review_id_is_omitted_without_losing_public_review(review_id):
    item = maps.normalize_public_maps_reviews(payload([review(review_id)]), CONTRIBUTOR)["reviews"][0]
    assert "id" not in item and "PRIVATE" not in json.dumps(item)
    assert item["text"] == "Example public review"


def test_duplicates_are_removed_by_review_id_then_canonical_fields():
    first, second = review(), review("", "Second public review")
    data = payload([first, copy.deepcopy(first), second, copy.deepcopy(second)], 2, 0)
    result = maps.normalize_public_maps_reviews(data, CONTRIBUTOR)
    assert result["returned"] == 2 and result["status"] == "ok"


@pytest.mark.parametrize("change", ["token", "unknown_total", "larger_total", "bad_row"])
def test_partial_reasons_keep_readable_records(change):
    data = payload()
    if change == "token": data[45][1] = "example-page-token"
    if change == "unknown_total": data[16][8] = None
    if change == "larger_total": data[16][8][0][0][7] = 10
    if change == "bad_row": data[45][0].append({"broken": True})
    result = maps.normalize_public_maps_reviews(data, CONTRIBUTOR)
    assert result["status"] == "partial" and result["limited"] is True and result["returned"] == 1


def test_caps_public_records_and_marks_limit_partial():
    data = payload([review(str(n)) for n in range(101)], 101, 0)
    result = maps.normalize_public_maps_reviews(data, CONTRIBUTOR)
    assert result["returned"] == result["limit"] == 100 and result["status"] == "partial"


def test_anonymous_single_bounded_request_and_response_close(monkeypatch):
    response = Reply(payload())
    calls = []
    def get(endpoint, **kwargs):
        calls.append(endpoint)
        assert endpoint == maps.ENDPOINT
        assert kwargs["params"]["pb"].startswith("!1s" + CONTRIBUTOR + "!")
        assert "!1i100!2m9" in kwargs["params"]["pb"]
        assert kwargs["params"]["authuser"] == 0
        assert kwargs["allow_redirects"] is False and kwargs["stream"] is True
        assert kwargs["timeout"] == (3, 12)
        assert "cookies" not in kwargs and "Authorization" not in kwargs["headers"]
        prepared = requests.Request("GET", endpoint, headers={"Cookie": "PRIVATE", "Authorization": "PRIVATE"}).prepare()
        assert not kwargs["auth"](prepared).headers.get("Cookie")
        assert not prepared.headers.get("Authorization")
        return response
    monkeypatch.setattr(maps.requests, "get", get)
    assert maps.fetch_public_maps_reviews(CONTRIBUTOR)["status"] == "ok"
    assert calls == [maps.ENDPOINT] and response.closed


@pytest.mark.parametrize("status,expected", [(302, "unavailable"), (401, "unavailable"), (403, "rate_limited"), (429, "rate_limited"), (500, "unavailable")])
def test_transport_status_is_not_zero_reviews(monkeypatch, status, expected):
    response = Reply({"password": "PRIVATE"}, status)
    monkeypatch.setattr(maps.requests, "get", lambda *a, **k: response)
    result = maps.fetch_public_maps_reviews(CONTRIBUTOR)
    assert result["status"] == expected and result["reviews"] == [] and response.closed
    assert "PRIVATE" not in json.dumps(result)


@pytest.mark.parametrize("error,expected", [(requests.Timeout("PRIVATE"), "timeout"), (requests.ConnectionError("PRIVATE"), "unavailable")])
def test_request_errors_do_not_export_exceptions(monkeypatch, error, expected):
    def get(*args, **kwargs):
        raise error
    monkeypatch.setattr(maps.requests, "get", get)
    result = maps.fetch_public_maps_reviews(CONTRIBUTOR)
    assert result["status"] == expected and "PRIVATE" not in json.dumps(result)


@pytest.mark.parametrize("document", [b"<html>PRIVATE</html>", b"garbage []", b")]}'\n{", b"[NaN]", b"\xff"])
def test_invalid_success_body_stays_unknown(monkeypatch, document):
    response = Reply(chunks=[document])
    monkeypatch.setattr(maps.requests, "get", lambda *a, **k: response)
    result = maps.fetch_public_maps_reviews(CONTRIBUTOR)
    assert result["status"] == "unknown" and response.closed
    assert "PRIVATE" not in json.dumps(result)


def test_decoded_response_byte_limit_closes_response(monkeypatch):
    monkeypatch.setattr(maps, "MAX_BYTES", 10)
    response = Reply(chunks=[b"[         ", b" ]"])
    monkeypatch.setattr(maps.requests, "get", lambda *a, **k: response)
    assert maps.fetch_public_maps_reviews(CONTRIBUTOR)["status"] == "unknown" and response.closed


def test_deadline_includes_time_waiting_for_headers(monkeypatch):
    response = Reply(payload())
    ticks = iter([100, 121])
    monkeypatch.setattr(maps.time, "monotonic", lambda: next(ticks))
    monkeypatch.setattr(maps.requests, "get", lambda *a, **k: response)
    assert maps.fetch_public_maps_reviews(CONTRIBUTOR)["status"] == "timeout" and response.closed


def test_deadline_checked_after_final_chunk(monkeypatch):
    response = Reply(payload())
    ticks = iter([100, 101, 121])
    monkeypatch.setattr(maps.time, "monotonic", lambda: next(ticks))
    monkeypatch.setattr(maps.requests, "get", lambda *a, **k: response)
    assert maps.fetch_public_maps_reviews(CONTRIBUTOR)["status"] == "timeout" and response.closed


# Synthetic preview photos. The image path mimics the shape of a Maps photo
# URL; no real image, place or contributor is referenced.
IMAGE = "https://lh3.googleusercontent.com/gps-cs/" + "A" * 40


def photo(uploader=CONTRIBUTOR, photo_id="fixture-photo", image=IMAGE + "=w461-h260-k-no", year=2020, month=1):
    post = [None] * 22
    post[0], post[6] = photo_id, [image]
    meta = [None] * 9
    meta[3] = [None] * 8
    meta[4] = [None, [[["Example Contributor"], "//maps.google.com/maps/contrib/" + uploader, None, None, None, uploader]]]
    # Photo-level coordinates live here; the parser must never emit them.
    meta[5] = [[1, [[None, None, 11.5, 22.5]]]]
    meta[6] = [None] * 9
    meta[6][7] = [year - 1, month, 1]
    meta[6][8] = [year, month, 2]
    post[21] = meta
    venue = [None] * 19
    venue[2], venue[3], venue[18] = "Example Viewpoint", "Example Road", "ChIJExamplePhotoPlace"
    return [post, venue]


def with_photos(rows, photos=3):
    data = payload()
    data[16][8][0].append([None, None, None, None, None, None, "Photos", photos])
    data[22] = [None, rows, 99]
    return data


def test_preview_photos_project_venue_month_and_thumbnail_only():
    result = maps.normalize_public_maps_reviews(with_photos([photo()]), CONTRIBUTOR)
    assert result["status"] == "ok"  # Review status is independent of photo coverage.
    item = result["photos"][0]
    assert item == {"image_url": IMAGE + maps.PHOTO_SIZE, "name": "Example Viewpoint", "address": "Example Road",
                    "date": "2020-01", "id": "fixture-photo",
                    "source_url": f"https://www.google.com/maps/contrib/{CONTRIBUTOR}/photos",
                    "maps_url": "https://www.google.com/maps/search/?api=1&query=Example+Viewpoint&query_place_id=ChIJExamplePhotoPlace"}
    assert "11.5" not in json.dumps(result["photos"]) and "22.5" not in json.dumps(result["photos"])
    coverage = result["photo_coverage"]
    assert coverage["status"] == "partial" and coverage["returned"] == 1 and coverage["total_reported"] == 3
    assert result["stats"]["Photos"] == 3


def test_photo_from_another_uploader_or_foreign_host_is_dropped():
    rows = [photo(uploader=OTHER), photo(photo_id="b", image="https://evil.example/gps-cs/" + "A" * 40),
            photo(photo_id="c", image="javascript:alert(1)")]
    result = maps.normalize_public_maps_reviews(with_photos(rows, photos=3), CONTRIBUTOR)
    assert result["photos"] == []
    assert result["photo_coverage"]["status"] == "unknown"


def test_full_photo_set_is_ok_and_duplicates_collapse():
    result = maps.normalize_public_maps_reviews(with_photos([photo(), photo()], photos=1), CONTRIBUTOR)
    assert len(result["photos"]) == 1
    # A duplicate row was skipped, not dropped, so the set matches the count.
    assert result["photo_coverage"]["status"] == "ok" and result["photo_coverage"]["limited"] is False


def test_missing_photo_preview_is_unknown_not_zero():
    result = maps.normalize_public_maps_reviews(payload(), CONTRIBUTOR)
    assert result["photos"] == [] and result["photo_coverage"]["status"] == "unknown"
    data = payload()
    data[16][8][0].append([None, None, None, None, None, None, "Photos", 0])
    assert maps.normalize_public_maps_reviews(data, CONTRIBUTOR)["photo_coverage"]["status"] == "ok"


@pytest.mark.parametrize("year,month", [(2004, 5), (2999, 1), (2020, 13), (True, 1)])
def test_implausible_photo_dates_are_omitted(year, month):
    item = maps.normalize_public_maps_reviews(with_photos([photo(year=year, month=month)]), CONTRIBUTOR)["photos"]
    assert item and all("date" not in p or p["date"] == f"{int(year) - 1:04d}-{month:02d}" for p in item)


def test_identity_mismatch_returns_no_photos():
    data = with_photos([photo()])
    data[16][1] = f"https://www.google.com/maps/contrib/{OTHER}/reviews"
    result = maps.normalize_public_maps_reviews(data, CONTRIBUTOR)
    assert result["photos"] == [] and result["status"] == "unknown"
