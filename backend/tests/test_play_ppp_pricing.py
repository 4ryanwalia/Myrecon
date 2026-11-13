"""Tests for GDP/PPP Play Console localized pricing matrix."""
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, os.fspath(ROOT / "tools"))

import play_ppp_pricing as ppp  # noqa: E402


def test_anchors_us_and_india_for_both_usd_bases():
    rows_199 = {r["country"]: r for r in ppp.build_matrix(usd_base=1.99)}
    assert rows_199["US"]["price"] == 1.99
    assert rows_199["IN"]["price"] == 99.0

    rows_099 = {r["country"]: r for r in ppp.build_matrix(usd_base=0.99)}
    assert rows_099["US"]["price"] == 0.99
    assert rows_099["IN"]["price"] == 99.0


def test_emerging_markets_pay_lower_usd_equivalent_than_high_income():
    rows = {r["country"]: r for r in ppp.build_matrix(usd_base=1.99)}
    specs = {s.country: s for s in ppp.PLAY_MARKETS}

    ng_usd = rows["NG"]["price"] / specs["NG"].fx_per_usd
    id_usd = rows["ID"]["price"] / specs["ID"].fx_per_usd
    gb_usd = rows["GB"]["price"] / specs["GB"].fx_per_usd

    assert ng_usd < gb_usd
    assert id_usd < gb_usd
    assert rows["JP"]["price"] == int(rows["JP"]["price"])
    assert rows["ID"]["price"] == int(rows["ID"]["price"])
    for spec in ppp.PLAY_MARKETS:
        assert rows[spec.country]["price"] >= spec.min_local


def test_csv_export_includes_header_and_all_markets():
    rows = ppp.build_matrix(usd_base=1.99)
    csv_text = ppp.to_csv(rows)
    lines = [ln for ln in csv_text.strip().splitlines() if ln]
    assert lines[0] == "Country,Market,Currency,Price,PriceMicros,GDP_PPP_USD"
    assert len(lines) == len(ppp.PLAY_MARKETS) + 1


def test_real_iso_codes_no_synthetic_markets_and_matches_kotlin_preview():
    codes = [spec.country for spec in ppp.PLAY_MARKETS]
    assert len(codes) >= 120
    assert len(codes) == len(set(codes))
    assert "EU_OTHER" not in codes
    for code in codes:
        assert re.fullmatch(r"[A-Z]{2}", code), "Invalid ISO code: " + code
    for euro in ("DE", "FR", "IT", "ES", "NL", "AT", "BE", "FI", "IE", "PT", "GR"):
        assert euro in codes

    kt_path = ROOT / "app" / "src" / "main" / "java" / "com" / "aryan" / "myrecon" / "billing" / "PppPricing.kt"
    kt_text = kt_path.read_text(encoding="utf-8")
    pairs = dict(re.findall(r'"([A-Z]{2})"\s+to\s+"([^"]+)"', kt_text))
    assert len(pairs) == len(codes)

    prefixes = {
        "USD": "$", "INR": "₹", "GBP": "£", "CAD": "CA$", "AUD": "A$", "EUR": "€",
        "PLN": "zł ", "UAH": "₴", "TRY": "₺", "BRL": "R$", "MXN": "MX$",
        "IDR": "Rp ", "PHP": "₱", "VND": "₫", "THB": "฿", "MYR": "RM ",
        "SGD": "S$", "JPY": "¥", "KRW": "₩", "TWD": "NT$", "HKD": "HK$",
        "NZD": "NZ$", "EGP": "E£", "NGN": "₦", "ZAR": "R", "PKR": "Rs ", "BDT": "৳",
    }
    specs = {s.country: s for s in ppp.PLAY_MARKETS}
    for row in ppp.build_matrix(usd_base=1.99):
        c = row["country"]
        assert c in pairs
        spec = specs[c]
        prefix = prefixes.get(spec.currency, spec.currency + " ")
        price = float(row["price"])
        if spec.currency in ppp.ZERO_DECIMAL_CURRENCIES or price.is_integer():
            num_str = f"{int(round(price)):,}"
        else:
            num_str = f"{price:,.2f}"
        expected = prefix + num_str
        assert pairs[c] == expected, f"Mismatch for {c}: kt={pairs[c]} py={expected}"
