# Reproduce the overview's polling-miss scenarios from the frozen inputs, in both directions. Writes scenarios.json.
import json, sys
from pathlib import Path
H = Path(__file__).resolve().parent.parent; sys.path.insert(0, str(H))
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
(H / "scenarios.json").write_text(json.dumps({"_note": "Polling-miss scenarios from the frozen forecast inputs, computed Nov 4, 2026 after the election. Negative = toward Republicans (as published on the overview), positive = toward Democrats.", **out}, indent=1))
for k, v in out.items(): print(k, {c: [round(x, 3) if isinstance(x, float) else x for x in y] for c, y in v.items()})
