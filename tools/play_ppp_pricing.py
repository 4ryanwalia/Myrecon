#!/usr/bin/env python3
"""GDP-per-capita (PPP) localized Google Play pricing matrix for MyRecon Scan Pack.

Computes purchasing-power-equivalent prices across Google Play supported markets
for the 5 Deep Search + 5 Extended Scan pack (`myrecon_scan_pack_5`), anchored
explicitly to India = INR 99 and US = $1.99 (or $0.99 via --usd-base 0.99).

Usage:
  python tools/play_ppp_pricing.py --usd-base 1.99 --csv play_pack_prices.csv
  python tools/play_ppp_pricing.py --usd-base 0.99 --summary
"""
from __future__ import annotations

import argparse
import csv
import io
import math
from dataclasses import dataclass

US_GDP_PPP = 85370.0
ZERO_DECIMAL_CURRENCIES = frozenset({"CLP", "COP", "HUF", "IDR", "JPY", "KRW", "PYG", "RWF", "TWD", "VND", "XOF", "XAF"})


@dataclass(frozen=True)
class MarketSpec:
    country: str
    name: str
    currency: str
    fx_per_usd: float
    gdp_ppp_usd: float
    min_local: float = 0.50


# World Bank / IMF GDP-per-capita (PPP, current international $) & Google Play billing currency pairs.
# Covers Google Play supported billing countries across all income tiers using real ISO-3166-1 alpha-2 codes
# (no synthetic regional placeholders, so CSV exports map directly to Play Console country pricing).
PLAY_MARKETS: tuple[MarketSpec, ...] = (
    MarketSpec("US", "United States", "USD", 1.0, 85370.0, 0.99),
    MarketSpec("IN", "India", "INR", 84.5, 10170.0, 10.0),
    MarketSpec("GB", "United Kingdom", "GBP", 0.78, 58900.0, 0.59),
    MarketSpec("CA", "Canada", "CAD", 1.39, 61600.0, 0.99),
    MarketSpec("AU", "Australia", "AUD", 1.52, 66600.0, 0.99),
    MarketSpec("DE", "Germany", "EUR", 0.92, 69300.0, 0.59),
    MarketSpec("FR", "France", "EUR", 0.92, 61200.0, 0.59),
    MarketSpec("IT", "Italy", "EUR", 0.92, 58800.0, 0.59),
    MarketSpec("ES", "Spain", "EUR", 0.92, 52800.0, 0.59),
    MarketSpec("NL", "Netherlands", "EUR", 0.92, 74200.0, 0.59),
    MarketSpec("AT", "Austria", "EUR", 0.92, 71300.0, 0.59),
    MarketSpec("BE", "Belgium", "EUR", 0.92, 70500.0, 0.59),
    MarketSpec("FI", "Finland", "EUR", 0.92, 63100.0, 0.59),
    MarketSpec("IE", "Ireland", "EUR", 0.92, 126900.0, 0.59),
    MarketSpec("PT", "Portugal", "EUR", 0.92, 48700.0, 0.59),
    MarketSpec("GR", "Greece", "EUR", 0.92, 41200.0, 0.59),
    MarketSpec("SK", "Slovakia", "EUR", 0.92, 44100.0, 0.59),
    MarketSpec("SI", "Slovenia", "EUR", 0.92, 53300.0, 0.59),
    MarketSpec("EE", "Estonia", "EUR", 0.92, 46400.0, 0.59),
    MarketSpec("LV", "Latvia", "EUR", 0.92, 42500.0, 0.59),
    MarketSpec("LT", "Lithuania", "EUR", 0.92, 51700.0, 0.59),
    MarketSpec("LU", "Luxembourg", "EUR", 0.92, 143700.0, 0.59),
    MarketSpec("MT", "Malta", "EUR", 0.92, 62400.0, 0.59),
    MarketSpec("CY", "Cyprus", "EUR", 0.92, 58100.0, 0.59),
    MarketSpec("HR", "Croatia", "EUR", 0.92, 45900.0, 0.59),
    MarketSpec("CH", "Switzerland", "CHF", 0.88, 91900.0, 0.50),
    MarketSpec("SE", "Sweden", "SEK", 10.7, 68600.0, 5.0),
    MarketSpec("NO", "Norway", "NOK", 11.0, 104500.0, 5.0),
    MarketSpec("DK", "Denmark", "DKK", 6.88, 76600.0, 4.0),
    MarketSpec("IS", "Iceland", "USD", 1.0, 73700.0, 0.49),
    MarketSpec("PL", "Poland", "PLN", 4.02, 49500.0, 1.99),
    MarketSpec("CZ", "Czechia", "CZK", 23.4, 52100.0, 10.0),
    MarketSpec("RO", "Romania", "RON", 4.58, 46300.0, 2.0),
    MarketSpec("BG", "Bulgaria", "BGN", 1.80, 38600.0, 1.0),
    MarketSpec("HU", "Hungary", "HUF", 376.0, 45900.0, 175.0),
    MarketSpec("UA", "Ukraine", "UAH", 41.3, 15500.0, 10.0),
    MarketSpec("RS", "Serbia", "RSD", 108.0, 27900.0, 50.0),
    MarketSpec("BA", "Bosnia and Herzegovina", "USD", 1.0, 21200.0, 0.49),
    MarketSpec("MK", "North Macedonia", "USD", 1.0, 23200.0, 0.49),
    MarketSpec("AL", "Albania", "USD", 1.0, 21400.0, 0.49),
    MarketSpec("MD", "Moldova", "USD", 1.0, 17900.0, 0.49),
    MarketSpec("GE", "Georgia", "GEL", 2.72, 24700.0, 1.0),
    MarketSpec("AM", "Armenia", "USD", 1.0, 22800.0, 0.49),
    MarketSpec("AZ", "Azerbaijan", "USD", 1.0, 23500.0, 0.49),
    MarketSpec("TR", "Turkey", "TRY", 34.4, 43900.0, 4.99),
    MarketSpec("BR", "Brazil", "BRL", 5.75, 20800.0, 1.99),
    MarketSpec("MX", "Mexico", "MXN", 20.1, 25600.0, 5.0),
    MarketSpec("AR", "Argentina", "ARS", 995.0, 26500.0, 250.0),
    MarketSpec("CO", "Colombia", "COP", 4350.0, 20600.0, 1500.0),
    MarketSpec("CL", "Chile", "CLP", 955.0, 31000.0, 350.0),
    MarketSpec("PE", "Peru", "PEN", 3.77, 16700.0, 1.50),
    MarketSpec("EC", "Ecuador", "USD", 1.0, 14500.0, 0.49),
    MarketSpec("UY", "Uruguay", "USD", 1.0, 34100.0, 0.49),
    MarketSpec("PY", "Paraguay", "PYG", 7800.0, 18500.0, 3000.0),
    MarketSpec("BO", "Bolivia", "BOB", 6.91, 10800.0, 3.0),
    MarketSpec("CR", "Costa Rica", "CRC", 512.0, 27900.0, 250.0),
    MarketSpec("PA", "Panama", "USD", 1.0, 39200.0, 0.49),
    MarketSpec("DO", "Dominican Republic", "USD", 1.0, 27100.0, 0.49),
    MarketSpec("GT", "Guatemala", "USD", 1.0, 13700.0, 0.49),
    MarketSpec("HN", "Honduras", "USD", 1.0, 7200.0, 0.49),
    MarketSpec("SV", "El Salvador", "USD", 1.0, 12700.0, 0.49),
    MarketSpec("NI", "Nicaragua", "USD", 1.0, 8200.0, 0.49),
    MarketSpec("JM", "Jamaica", "USD", 1.0, 11800.0, 0.49),
    MarketSpec("TT", "Trinidad and Tobago", "USD", 1.0, 31600.0, 0.49),
    MarketSpec("PR", "Puerto Rico", "USD", 1.0, 44900.0, 0.49),
    MarketSpec("ID", "Indonesia", "IDR", 15750.0, 16500.0, 3000.0),
    MarketSpec("PH", "Philippines", "PHP", 58.6, 11700.0, 15.0),
    MarketSpec("VN", "Vietnam", "VND", 25350.0, 16300.0, 6000.0),
    MarketSpec("TH", "Thailand", "THB", 34.2, 23400.0, 10.0),
    MarketSpec("MY", "Malaysia", "MYR", 4.38, 39100.0, 1.99),
    MarketSpec("SG", "Singapore", "SGD", 1.33, 141500.0, 0.99),
    MarketSpec("JP", "Japan", "JPY", 153.0, 52100.0, 50.0),
    MarketSpec("KR", "South Korea", "KRW", 1390.0, 59300.0, 500.0),
    MarketSpec("TW", "Taiwan", "TWD", 32.1, 76800.0, 15.0),
    MarketSpec("HK", "Hong Kong", "HKD", 7.77, 74500.0, 4.0),
    MarketSpec("MO", "Macao", "MOP", 8.01, 125500.0, 4.0),
    MarketSpec("NZ", "New Zealand", "NZD", 1.67, 54100.0, 0.99),
    MarketSpec("NP", "Nepal", "USD", 1.0, 5300.0, 0.49),
    MarketSpec("MM", "Myanmar", "MMK", 2100.0, 5900.0, 1000.0),
    MarketSpec("KH", "Cambodia", "USD", 1.0, 7700.0, 0.49),
    MarketSpec("LA", "Laos", "USD", 1.0, 9400.0, 0.49),
    MarketSpec("MN", "Mongolia", "USD", 1.0, 18100.0, 0.49),
    MarketSpec("AE", "United Arab Emirates", "AED", 3.67, 84000.0, 1.99),
    MarketSpec("SA", "Saudi Arabia", "SAR", 3.75, 59800.0, 1.99),
    MarketSpec("QA", "Qatar", "QAR", 3.64, 118800.0, 2.0),
    MarketSpec("KW", "Kuwait", "USD", 1.0, 53000.0, 0.49),
    MarketSpec("BH", "Bahrain", "USD", 1.0, 62700.0, 0.49),
    MarketSpec("OM", "Oman", "USD", 1.0, 40500.0, 0.49),
    MarketSpec("JO", "Jordan", "JOD", 0.71, 11100.0, 0.35),
    MarketSpec("LB", "Lebanon", "USD", 1.0, 11800.0, 0.49),
    MarketSpec("IQ", "Iraq", "USD", 1.0, 14500.0, 0.49),
    MarketSpec("IL", "Israel", "ILS", 3.72, 54800.0, 2.0),
    MarketSpec("EG", "Egypt", "EGP", 49.2, 18800.0, 10.0),
    MarketSpec("NG", "Nigeria", "NGN", 1660.0, 6400.0, 200.0),
    MarketSpec("ZA", "South Africa", "ZAR", 17.9, 16200.0, 5.0),
    MarketSpec("KE", "Kenya", "KES", 129.0, 6600.0, 30.0),
    MarketSpec("TZ", "Tanzania", "TZS", 2680.0, 4000.0, 1000.0),
    MarketSpec("UG", "Uganda", "USD", 1.0, 3300.0, 0.49),
    MarketSpec("RW", "Rwanda", "RWF", 1365.0, 3500.0, 500.0),
    MarketSpec("ET", "Ethiopia", "USD", 1.0, 3800.0, 0.49),
    MarketSpec("ZM", "Zambia", "USD", 1.0, 4100.0, 0.49),
    MarketSpec("ZW", "Zimbabwe", "USD", 1.0, 4900.0, 0.49),
    MarketSpec("MZ", "Mozambique", "USD", 1.0, 1700.0, 0.49),
    MarketSpec("AO", "Angola", "USD", 1.0, 7400.0, 0.49),
    MarketSpec("NA", "Namibia", "USD", 1.0, 12100.0, 0.49),
    MarketSpec("BW", "Botswana", "USD", 1.0, 19400.0, 0.49),
    MarketSpec("MU", "Mauritius", "USD", 1.0, 31000.0, 0.49),
    MarketSpec("DZ", "Algeria", "DZD", 134.0, 16500.0, 60.0),
    MarketSpec("TN", "Tunisia", "USD", 1.0, 14100.0, 0.49),
    MarketSpec("SN", "Senegal", "XOF", 605.0, 4800.0, 250.0),
    MarketSpec("CI", "Cote d'Ivoire", "XOF", 605.0, 7500.0, 250.0),
    MarketSpec("CM", "Cameroon", "XAF", 605.0, 5500.0, 250.0),
    MarketSpec("PK", "Pakistan", "PKR", 278.0, 6700.0, 70.0),
    MarketSpec("BD", "Bangladesh", "BDT", 119.5, 9400.0, 30.0),
    MarketSpec("LK", "Sri Lanka", "LKR", 293.0, 14200.0, 100.0),
    MarketSpec("KZ", "Kazakhstan", "KZT", 491.0, 39300.0, 150.0),
    MarketSpec("UZ", "Uzbekistan", "USD", 1.0, 10900.0, 0.49),
    MarketSpec("KG", "Kyrgyzstan", "USD", 1.0, 7400.0, 0.49),
    MarketSpec("GH", "Ghana", "GHS", 16.2, 7400.0, 3.0),
    MarketSpec("MA", "Morocco", "MAD", 9.85, 10200.0, 5.0),
)


def _round_psychological(raw: float, currency: str, min_local: float) -> float:
    amount = max(raw, min_local)
    if currency in ZERO_DECIMAL_CURRENCIES:
        if amount >= 10000:
            step = 1000.0
        elif amount >= 1000:
            step = 100.0
        elif amount >= 100:
            step = 10.0
        else:
            step = 1.0
        return float(max(int(round(amount / step) * step), int(math.ceil(min_local))))

    # Small nominal currencies like USD/EUR/GBP/AUD/CAD/SGD use .49 / .99 endings.
    if amount < 15.0:
        whole = int(math.floor(amount))
        frac = amount - whole
        if frac >= 0.70:
            candidate = whole + 0.99
        elif frac >= 0.25:
            candidate = whole + 0.49
        else:
            candidate = max(min_local, (whole - 0.01) if whole >= 1 else 0.49)
        return round(max(candidate, min_local), 2)

    if amount < 150.0:
        rounded = max(int(math.floor((amount + 5) / 10.0) * 10 - 1), int(math.ceil(min_local)))
        return float(rounded)

    step = 50.0 if amount >= 500 else 10.0
    return float(max(int(round(amount / step) * step), int(math.ceil(min_local))))


def compute_price(spec: MarketSpec, usd_base: float = 1.99) -> float:
    if spec.country == "US":
        return round(usd_base, 2)
    if spec.country == "IN":
        # User explicitly specified INR 99 for the 5+5 pack in India.
        return 99.0

    # PPP elasticity (0.35 exponent keeps emerging markets equitable and aligns with ~INR 99).
    ppp_ratio = max(0.35, min(1.05, (spec.gdp_ppp_usd / US_GDP_PPP) ** 0.35))
    usd_target = usd_base * ppp_ratio
    raw_local = usd_target * spec.fx_per_usd
    return _round_psychological(raw_local, spec.currency, spec.min_local)


def build_matrix(usd_base: float = 1.99) -> list[dict[str, object]]:
    rows = []
    for spec in PLAY_MARKETS:
        price = compute_price(spec, usd_base=usd_base)
        price_micros = int(round(price * 1_000_000))
        formatted = f"{int(price)}" if spec.currency in ZERO_DECIMAL_CURRENCIES or price == int(price) else f"{price:.2f}"
        rows.append(
            {
                "country": spec.country,
                "name": spec.name,
                "currency": spec.currency,
                "gdp_ppp_usd": spec.gdp_ppp_usd,
                "price": price,
                "formatted": f"{spec.currency} {formatted}",
                "price_micros": price_micros,
            }
        )
    return rows


def to_csv(rows: list[dict[str, object]]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Country", "Market", "Currency", "Price", "PriceMicros", "GDP_PPP_USD"])
    for r in rows:
        writer.writerow([r["country"], r["name"], r["currency"], r["price"], r["price_micros"], r["gdp_ppp_usd"]])
    return buf.getvalue()


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute GDP/PPP localized Play prices for myrecon_scan_pack_5.")
    parser.add_argument("--usd-base", type=float, default=1.99, choices=[0.99, 1.99], help="US anchor price (default 1.99; also supports 0.99).")
    parser.add_argument("--csv", type=str, default="", help="Optional path to write CSV table.")
    parser.add_argument("--summary", action="store_true", help="Print readable country table.")
    args = parser.parse_args()

    rows = build_matrix(usd_base=args.usd_base)
    if args.csv:
        with open(args.csv, "w", encoding="utf-8", newline="") as fh:
            fh.write(to_csv(rows))
    if args.summary or not args.csv:
        for r in rows:
            print(f"{r['country']:8s} | {r['name']:36s} | {r['formatted']:14s} | GDP PPP ${int(r['gdp_ppp_usd']):,}")


if __name__ == "__main__":
    main()
