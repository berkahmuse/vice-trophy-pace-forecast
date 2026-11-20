"""Trophy rarity forecaster: count-space pooled-pace model.

Idea: a printed earn rate is a ratio, earners / players_tracked. The two
sides of that ratio move for different reasons -- the denominator grows as
Exophase picks up new players, the numerator grows as players progress --
so this program forecasts the two counts separately and divides at the
end, instead of extrapolating the ratio itself.

Method, per case:
  1. Collapse the history to distinct page states (consecutive reads that
     show the same players_tracked and the same rates are one state:
     Exophase had not refreshed between them, so they carry no new
     information and would overweight the flat stretches).
  2. Put time on a log scale, x = ln(1 + hours since the first state).
     Launch-week growth is fast early and bends, and log time straightens
     it enough for a least-squares line.
  3. Fit ln(players) against x. Fit ln(earners + 0.5) against x for every
     trophy, then shrink each trophy's slope toward the median slope of
     all trophies (the page-wide pace): a trophy with a handful of earners
     has a noisy slope of its own, and the pooled pace is the better bet
     until its own counts say otherwise.
  4. Read both fits at the target's x, divide, clamp to the printable
     range. The spread on the logit scale grows with the log-time
     distance travelled, with 1/sqrt(earners) (small counts jump around),
     and with a floor for the refresh timing nobody can see.

With fewer than two distinct states there is no pace to measure: the page
is one frozen snapshot and a refresh is coming that will mostly dilute
the rates (a flood of new players who have earned little yet), so the
fallback shifts each median down on the logit scale by a dilution term
that grows with the horizon and gives the forecast a wide spread.

Standard library only, deterministic, reads every *.in in the input
directory and writes one *.out per case.
"""

import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))

LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
Z = [-1.644854, -0.674490, 0.0, 0.674490, 1.644854]

# How hard a trophy's own slope is shrunk toward the pooled pace: the
# shrinkage weight is earners / (earners + EARNERS_TRUST), so a trophy
# needs a few hundred earners before its own slope dominates.
EARNERS_TRUST = 220.0
# Smoothing added to earner counts before taking logs, so a trophy nobody
# has earned yet still gets a finite (tiny) forecast instead of a crash.
COUNT_SMOOTH = 0.5


def clamp_rate(x):
    return min(99.99, max(0.01, x))


def logit_of(pct):
    p = clamp_rate(pct) / 100.0
    return math.log(p / (1.0 - p))


def rate_of(logit):
    if logit >= 0:
        return 100.0 / (1.0 + math.exp(-logit))
    e = math.exp(logit)
    return 100.0 * e / (1.0 + e)


def round4(x):
    scaled = x * 10000.0
    whole = math.floor(scaled)
    if scaled - whole >= 0.5:
        whole += 1
    value = whole / 10000.0
    return int(value) if float(value).is_integer() else value


def parse_time(text):
    return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)


def fit_line(xs, ys):
    """Least-squares (slope, intercept); slope 0 when x never moves."""
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx <= 1e-12:
        return 0.0, my
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    slope = sxy / sxx
    return slope, my - slope * mx


def median(values):
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    if n % 2:
        return ordered[mid]
    return 0.5 * (ordered[mid - 1] + ordered[mid])


def distinct_states(case):
    """History collapsed to the moments the page actually changed."""
    states = []
    for read in case["history"]:
        rates = read["rates"]
        key = (read["players_tracked"], tuple(rates))
        if states and states[-1][0] == key:
            continue
        states.append((key, parse_time(read["at"]), read["players_tracked"], rates))
    return [(when, players, rates) for _, when, players, rates in states]


def last_known(rates_series, idx):
    for rates in reversed(rates_series):
        value = rates[idx]
        if value is not None:
            return value
    return 0.0


def fallback_rows(case, states):
    """One frozen page state: expect a diluting refresh, spread wide."""
    horizon_days = case["horizon_minutes"] / 1440.0
    _, players, _ = states[-1]
    all_rates = [rates for _, _, rates in states]
    rows = []
    for i, trophy in enumerate(case["trophies"]):
        rate = last_known(all_rates, i)
        earners = rate / 100.0 * players
        # New players arrive having earned almost nothing; the longer the
        # horizon, the more of the tracked crowd they make up. Story-early
        # trophies (already common) are re-earned by newcomers quickly, so
        # they dilute less than rare ones: weight by rarity on a log scale.
        rarity_weight = 0.45 + 0.55 * (1.0 - clamp_rate(rate) / 100.0)
        dilution = rarity_weight * math.log1p(1.35 * horizon_days)
        centre = logit_of(rate) - dilution
        sigma = 0.55 + 0.5 * math.sqrt(horizon_days) + 0.6 / math.sqrt(max(earners, 1.0))
        rows.append((trophy["id"], centre, min(sigma, 2.4)))
    return rows


def paced_rows(case, states):
    """Two or more distinct states: fit counts, shrink slopes, divide."""
    t0 = states[0][0]
    xs = [math.log1p((when - t0).total_seconds() / 3600.0) for when, _, _ in states]
    target = parse_time(case["target"])
    x_target = math.log1p((target - t0).total_seconds() / 3600.0)
    x_last = xs[-1]
    players_series = [players for _, players, _ in states]
    slope_p, _ = fit_line(xs, [math.log(max(p, 1)) for p in players_series])
    # Anchor the player forecast at the last tracked count and walk from
    # there at the fitted pace: a least-squares line can sit above or
    # below the final state, and anchoring removes that level error.
    # Do not let the walk run away either: cap the implied growth over
    # the horizon at a factor of 40 over the last tracked count.
    log_p_target = math.log(max(players_series[-1], 1)) + slope_p * (x_target - x_last)
    log_p_cap = math.log(max(players_series[-1], 1)) + math.log(40.0)
    players_target = math.exp(min(log_p_target, log_p_cap))
    players_target = max(players_target, players_series[-1] * 0.9)

    n_trophies = len(case["trophies"])
    raw_slopes = []
    fits = []
    for i in range(n_trophies):
        counts = []
        for _, players, rates in states:
            rate = rates[i]
            counts.append((rate / 100.0 * players) if rate is not None else None)
        known = [(x, c) for x, c in zip(xs, counts) if c is not None]
        if len(known) >= 2:
            slope, _ = fit_line([x for x, _ in known],
                                [math.log(c + COUNT_SMOOTH) for _, c in known])
        else:
            slope = 0.0
        last_count = known[-1][1] if known else 0.0
        raw_slopes.append(slope)
        fits.append((slope, last_count))
    pooled = median(raw_slopes)

    rows = []
    for i, trophy in enumerate(case["trophies"]):
        slope, earners_last = fits[i]
        trust = earners_last / (earners_last + EARNERS_TRUST)
        slope_used = trust * slope + (1.0 - trust) * pooled
        # Anchored walk from the last observed count, like the players.
        earners_target = (earners_last + COUNT_SMOOTH) * math.exp(
            slope_used * (x_target - x_last)) - COUNT_SMOOTH
        earners_target = max(earners_target, 0.0)
        rate = clamp_rate(100.0 * earners_target / players_target)
        distance = max(x_target - x_last, 0.0)
        sigma = (0.30
                 + 0.42 * distance
                 + 0.85 / math.sqrt(max(earners_last, 1.0))
                 + 0.10 * abs(slope - pooled))
        rows.append((trophy["id"], logit_of(rate), min(max(sigma, 0.22), 2.3)))
    return rows


def forecast_case(case):
    states = distinct_states(case)
    if not states:
        raise ValueError("case has no history")
    span_hours = (states[-1][0] - states[0][0]).total_seconds() / 3600.0
    if len(states) < 2 or span_hours < 1.0:
        centred = fallback_rows(case, states)
    else:
        centred = paced_rows(case, states)
    rows = []
    for trophy_id, centre, sigma in centred:
        qs = [round4(rate_of(centre + z * sigma)) for z in Z]
        qs = sorted(qs)
        rows.append({"id": trophy_id, "q": qs})
    return {"trophies": rows}


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in sorted(INPUT_DIR.glob("*.in")):
        case = json.loads(path.read_text(encoding="utf-8"))
        result = forecast_case(case)
        (OUTPUT_DIR / (path.stem + ".out")).write_text(
            json.dumps(result, separators=(",", ":")) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
