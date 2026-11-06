"""Shared pieces of the Senate and House models: poll weighting, the polling average, and rating tiers."""
import math
from datetime import date


def poll_weight(poll, later_same_pollster, W, as_of):
    end = date.fromisoformat(poll["end"])
    age = max((as_of - end).days, 0)
    w = 0.5 ** (age / W["half_life_days"])
    n = poll.get("n") or W["default_n"]
    w *= math.sqrt(min(n, W["n_cap"]) / W["default_n"])
    w *= W["pop"].get(poll.get("pop") or "null", W["pop"]["null"])
    if poll.get("partisan"):
        w *= W["partisan_sponsor"]
    if not poll.get("verified", True):
        w *= W["unverified"]
    # A pollster's older releases are mostly superseded by its newest one: count them at a fraction
    # so a frequent pollster doesn't dominate the average.
    w *= W["superseded"] ** later_same_pollster
    return w


def adjusted_margin(poll, m, W):
    """Remove the expected lean of sponsored / one-party pollsters (subtract their bias toward their side)."""
    side = poll.get("partisan") or poll.get("lean")
    if not side:
        return m, 0.0
    adj = W["partisan_shift"] if poll.get("partisan") else W["lean_shift"]
    adj = -adj if side == "D" else adj
    return m + adj, adj


def average(polls, margin_of, W, as_of, window_start):
    """Weighted polling average of challenger-minus-R margins. margin_of(poll) returns the margin or None."""
    cutoff = date.fromisoformat(window_start)
    usable = [p for p in polls if p.get("end") and date.fromisoformat(p["end"]) <= as_of]
    recent = [p for p in usable if date.fromisoformat(p["end"]) >= cutoff]
    if len(recent) < W["min_recent_polls"]:
        recent = usable  # thin races: fall back to all 2026 polls, heavily discounted by age
    recent.sort(key=lambda p: p["end"], reverse=True)
    seen, rows = {}, []
    for p in recent:
        m = margin_of(p)
        if m is None:
            continue
        key = p["pollster"].lower()
        k = seen.get(key, 0)
        seen[key] = k + 1
        w = poll_weight(p, k, W, as_of)
        am, adj = adjusted_margin(p, m, W)
        rows.append({"pollster": p["pollster"], "sponsor": p.get("sponsor"), "partisan": p.get("partisan"),
                     "lean": p.get("lean"), "end": p["end"], "n": p.get("n"), "pop": p.get("pop"),
                     "results": p["results"], "raw_margin": round(m, 1), "adj": adj,
                     "margin": round(am, 1), "undecided": p.get("undecided"), "weight": w,
                     "verified": p.get("verified", True), "url": p.get("source_url")})
    if not rows:
        return None
    tw = sum(r["weight"] for r in rows)
    for r in rows:
        r["share"] = r["weight"] / tw
    mean = sum(r["margin"] * r["share"] for r in rows)
    n_eff = tw ** 2 / sum(r["weight"] ** 2 for r in rows)
    und = [r["undecided"] for r in rows if r["undecided"] is not None]
    # Undecided: if not reported, infer from what the toplines leave unallocated.
    if not und:
        und = [max(0, 100 - sum(v for v in r["results"].values() if isinstance(v, (int, float)))) for r in rows]
    raw_mean = sum(r["raw_margin"] * r["share"] for r in rows)
    return {"mean": mean, "raw_mean": raw_mean, "n_eff": n_eff, "n_polls": len(rows),
            "undecided": sum(und) / len(und), "polls": rows}


def tier(p, tiers):
    q = max(p, 1 - p)
    for name, cut in tiers:
        if q >= cut:
            return name
    return "Toss-up"
