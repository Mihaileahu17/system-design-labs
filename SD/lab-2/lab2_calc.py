"""Calculele pentru Laboratorul 2: numarul de Stocks, RPS si stocarea.

Rulare:
    python3 lab2_calc.py            # descarca fisierele Nasdaq Trader
    python3 lab2_calc.py --offline  # foloseste fisierele salvate local

Nu are nevoie de pachete externe, doar Python 3.
"""

import re
import statistics
import sys
import urllib.request
from collections import Counter
from pathlib import Path

HERE = Path(__file__).parent
SOURCES = {
    "nasdaqlisted.txt": "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt",
    "otherlisted.txt": "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt",
}

# Exchange in otherlisted.txt: N = NYSE, A = NYSE American (restul le exclud)
EXCHANGES = {"Nasdaq": "Nasdaq", "N": "NYSE", "A": "NYSE American"}

NOT_A_STOCK = re.compile(
    r"warrant|right|\bunit|preferred|notes? due|debenture|\bpfd|%", re.I
)
ADR = re.compile(r"american depositary|\bads\b", re.I)
COMMON = re.compile(
    r"common stock|ordinary shares|common shares|class a|class b|class c", re.I
)

MIB = 1024**2
GIB = 1024**3


# ---------------------------------------------------------------------------
# 1. Numarul de Stocks
# ---------------------------------------------------------------------------

def load(name, offline):
    path = HERE / name
    if not offline:
        req = urllib.request.Request(SOURCES[name], headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            path.write_bytes(resp.read())
    lines = path.read_text().strip().splitlines()
    header = lines[0].split("|")
    rows = [dict(zip(header, line.split("|"))) for line in lines[1:-1]]
    created = lines[-1].split("|")[0]  # "File Creation Time: MMDDYYYYHH:MM"
    return rows, created


def classify(name):
    if NOT_A_STOCK.search(name):
        return None
    if ADR.search(name):
        return "ADR"
    if COMMON.search(name):
        return "Common"
    return None


def count_stocks(offline):
    nasdaq, created_n = load("nasdaqlisted.txt", offline)
    other, created_o = load("otherlisted.txt", offline)

    selected = []  # (bursa, tip, simbol, denumire)
    for r in nasdaq:
        selected.append(("Nasdaq", r, r["Symbol"]))
    for r in other:
        selected.append((r["Exchange"], r, r["ACT Symbol"]))

    counts = Counter()
    symbols, names = [], []
    for exchange, r, symbol in selected:
        if exchange not in EXCHANGES or r["Test Issue"] == "Y" or r["ETF"] == "Y":
            continue
        kind = classify(r["Security Name"])
        if kind is None:
            continue
        counts[(EXCHANGES[exchange], kind)] += 1
        symbols.append(symbol)
        names.append(r["Security Name"])

    print("== 1. Stocks acceptate ==")
    print(f"nasdaqlisted.txt -> {created_n}")
    print(f"otherlisted.txt  -> {created_o}")
    print(f"{'Bursa':<15}{'Common':>8}{'ADR':>6}")
    for ex in EXCHANGES.values():
        print(f"{ex:<15}{counts[(ex, 'Common')]:>8}{counts[(ex, 'ADR')]:>6}")
    common = sum(v for (_, k), v in counts.items() if k == "Common")
    adr = sum(v for (_, k), v in counts.items() if k == "ADR")
    print(f"{'Total':<15}{common:>8}{adr:>6}   => {common + adr} Stocks")

    company = [re.split(r" - | Common Stock| Ordinary Shares| Class [ABC]| American Deposit", n)[0].strip()
               for n in names]
    print(f"simbol: medie {statistics.mean(map(len, symbols)):.1f}, max {max(map(len, symbols))} caractere")
    print(f"nume companie: medie {statistics.mean(map(len, company)):.1f} caractere")
    print(f"denumire titlu: medie {statistics.mean(map(len, names)):.1f} caractere")
    print()


# ---------------------------------------------------------------------------
# 2-3. RPS
# ---------------------------------------------------------------------------

# citire: (pondere, actiuni, secunde)
READS = {
    "Overview": (0.70, 1, 30),
    "Filter": (0.50, 3, 60),
    "Stock price": (0.20, 1, 1),
    "History": (0.20, 1, 300),
    "Watchlist": (0.60, 1, 60),
    "Search": (0.10, 3, 60),
}
TIERS = [300, 3_000, 30_000]


def rps():
    print("== 2. RPS in regim stabil ==")
    print(f"{'Citire':<13}" + "".join(f"{t:>12,}" for t in TIERS))
    steady = {t: 0.0 for t in TIERS}
    for read, (share, actions, seconds) in READS.items():
        values = [t * share * actions / seconds for t in TIERS]
        for t, v in zip(TIERS, values):
            steady[t] += v
        print(f"{read:<13}" + "".join(f"{v:>12,.2f}" for v in values))
    print(f"{'Total':<13}" + "".join(f"{steady[t]:>12,.2f}" for t in TIERS))
    share_price = READS["Stock price"][0] / (steady[TIERS[0]] / TIERS[0])
    print(f"Stock price = {share_price:.1%} din traficul stabil")
    print()

    print("== 3. RPS la deschiderea pietei ==")
    print(f"{'Calcul':<22}" + "".join(f"{t:>12,}" for t in TIERS))
    rows = {"Trafic stabil": [], "Overview suplimentar": [], "Watchlist suplimentar": [],
            "Subtotal": [], "Marja 10%": [], "Tinta (rotunjit sus)": []}
    for t in TIERS:
        overview = t * 0.30 / 10
        watchlist = t * 0.30 * 0.60 / 10
        subtotal = steady[t] + overview + watchlist
        margin = subtotal * 0.10
        # round() inainte de ceil ca 10296.000000001 sa nu devina 10297
        target = -(-round(subtotal + margin, 6) // 1)
        for key, v in zip(rows, [steady[t], overview, watchlist, subtotal, margin, target]):
            rows[key].append(v)
    for key, values in rows.items():
        print(f"{key:<22}" + "".join(f"{v:>12,.2f}" for v in values))
    print()


# ---------------------------------------------------------------------------
# 4. Stocare
# ---------------------------------------------------------------------------

STOCKS = 6_000           # valoare de planificare (~5,614 observate)
BARS_PER_DAY = 390 // 5  # bare de 5 minute intr-o sesiune de 390 minute
INTRADAY_DAYS = 21       # 30 de zile calendaristice
DAILY_DAYS = 5 * 252     # backfill 5 ani
SPLITS_PER_YEAR = 550    # StockAnalysis: 530 in 2025, rotunjit in sus
NEW_LISTINGS_YEAR = 730  # ~2 pe zi (350 IPO in 2025 + alte listari)


def storage():
    datasets = [
        ("Referinta Stock", STOCKS, 160),
        ("Ultimele preturi", STOCKS, 81),
        ("History intraday", STOCKS * BARS_PER_DAY * INTRADAY_DAYS, 56),
        ("History zilnic", STOCKS * DAILY_DAYS, 60),
        ("Calendar", 6 * 365, 24),
        ("Split-uri", 5 * SPLITS_PER_YEAR, 32),
    ]
    print("== 4. Stocare bruta ==")
    total = 0
    for name, records, size in datasets:
        raw = records * size
        total += raw
        print(f"{name:<18}{records:>12,} x {size:>3} B = {raw:>15,} B  ({raw / MIB:9.2f} MiB)")
    print(f"{'Total initial':<18}{'':>22}{total:>15,} B  ({total / MIB:9.2f} MiB, {total / GIB:.2f} GiB)")

    intraday_day = STOCKS * BARS_PER_DAY * 56
    daily_day = STOCKS * 60
    print(f"scris intraday pe zi: {intraday_day:,} B ({intraday_day / MIB:.1f} MiB), crestere neta ~0")
    print(f"crestere neta zilnica (bare zilnice): {daily_day:,} B ({daily_day / MIB:.2f} MiB)")

    year = 252 * daily_day + NEW_LISTINGS_YEAR * 160 + SPLITS_PER_YEAR * 32 + 365 * 24
    print(f"crestere pe an: {year:,} B ({year / MIB:.1f} MiB)")
    print(f"total dupa 1 an: {total + year:,} B ({(total + year) / MIB:.1f} MiB, {(total + year) / GIB:.2f} GiB)")


if __name__ == "__main__":
    count_stocks(offline="--offline" in sys.argv)
    rps()
    storage()
