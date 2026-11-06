# Reproduce the overview's polling-miss scenarios from the frozen inputs, in both directions. Writes scenarios.json.
# The models read the working files, so this first checks that they still match the freeze, and refuses to write unless the
# rerun reproduces the published headline and the published R+2/R+3 numbers exactly.
import hashlib, json, re, sys
from pathlib import Path
H = Path(__file__).resolve().parent.parent; sys.path.insert(0, str(H))
FROZEN = H / "frozen"

# 1. Inputs: every file in the freeze manifest that the models read must be unchanged. The parameter files aren't in the
# manifest, but each frozen model output records the parameters it ran with.
manifest = json.loads((FROZEN / "manifest.json").read_text())["files"]
for f in ("senate_polls.json", "house_polls.json", "gov_polls.json", "house_data.json"):
    if hashlib.sha256((H / f).read_bytes()).hexdigest() != manifest[f]:
        sys.exit(f"{f} differs from the frozen copy; restore it from frozen/ before rerunning.")
for model, params in (("senate_model.json", "model_params.json"), ("house_model.json", "model_params_house.json"),
                      ("gov_model.json", "model_params_gov.json")):
    if json.loads((FROZEN / model).read_text())["params"] != json.loads((H / params).read_text()):
        sys.exit(f"{params} differs from the parameters recorded in frozen/{model}.")

import numpy as np
import governor_model, house_model, senate_model


def median(s): return int(np.percentile(s, 50, method="inverted_cdf"))


def miss(shift):
    races = [senate_model.race(s) for s in sorted(senate_model.config)]
    _, hist = senate_model.simulate(races, shift=shift)
    c = senate_model.control_probs(hist)["separate"]
    di = np.repeat([int(d) + int(i) for k in hist for d, i in [k.split(",")]], [round(v * senate_model.P["sims"]) for v in hist.values()])
    _, seats = house_model.simulate([house_model.district(r) for r in house_model.data], shift=shift)
    _, dg, ig = governor_model.simulate([governor_model.race(s) for s in sorted(governor_model.config)], shift=shift)
    return {"senate": [c["D"], c["R"], median(di), median(100 - di)],
            "house": [float((seats >= house_model.MAJORITY).mean()), float((seats < house_model.MAJORITY).mean()), median(seats), median(435 - seats)],
            "governors": [float((dg >= 26).mean()), float((50 - dg - ig >= 26).mean()), median(dg), median(50 - dg - ig)]}


out = {str(k): miss(k) for k in (-3, -2, 0, 2, 3)}

# 2. Outputs: the no-shift run must equal the frozen headline, and R+2/R+3 must match the frozen overview as published.
sen, hou, gov = (json.loads((FROZEN / f).read_text()) for f in ("senate_model.json", "house_model.json", "gov_model.json"))
base = out["0"]
assert abs(base["senate"][0] - sen["control"]["separate"]["D"]) < 1e-9, "Senate headline not reproduced"
assert abs(base["house"][0] - hou["p_dem_control"]) < 1e-9, "House headline not reproduced"
assert abs(base["governors"][0] - gov["p_d_majority"]) < 1e-9, "Governors headline not reproduced"
pct = lambda p: ">99%" if p >= 0.995 else "<1%" if p <= 0.005 else f"{p:.0%}"
page = (FROZEN / "index.html").read_text()
published = re.findall(r"R\+(\d): (Democrats|Republicans) have a <strong>([^<]+)</strong> chance of [^,]+, with a median of <strong>(\d+)</strong>", page)
assert len(published) == 6, f"expected 6 published R+2/R+3 lines on the frozen overview, found {len(published)}"
for (k, who, p, d), ch in zip(published, ("senate", "senate", "house", "house", "governors", "governors")):
    p_d, p_r, med, _ = out["-" + k][ch]
    mine = ("Democrats", pct(p_d)) if p_d >= p_r else ("Republicans", pct(p_r))
    assert mine == (who, p) and med == int(d), f"{ch} R+{k}: published {who} {p}, median {d}; rerun {mine[0]} {mine[1]}, median {med}"

(H / "scenarios.json").write_text(json.dumps({"_note": "Polling-miss scenarios from the frozen forecast inputs, computed Nov 4, 2026 after the election. Negative = toward Republicans (as published on the overview), positive = toward Democrats.", **out}, indent=1))
print("Inputs match the freeze; headline and published R+2/R+3 reproduced exactly. scenarios.json written.")
for k, v in out.items(): print(k, {c: [round(x, 3) if isinstance(x, float) else x for x in y] for c, y in v.items()})
