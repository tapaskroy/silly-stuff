# Uniform-swing seat projection from each national generic-ballot poll vs our frozen forecast, on AP-called races.
# Usage: python3 analysis/natseats.py   (the national polls are the final releases per pollster, Oct 13 - Nov 3, 2026)
import json
from pathlib import Path
H=str(Path(__file__).resolve().parent.parent)+"/"
J=lambda f: json.load(open(H+f))
RES=J("results.json")
POLLS=[("Verasight/The Argument",11),("NYT/Siena",11),("RMG/Napolitan",11),("Tufts/YouGov",12),("Verasight/SIN",12),("Prolific",10.7),("Big Data Poll",12.3),("TIPP",10),("Emerson",10),("CNN/SSRS",10),("Honest Poll",13),("YouGov pre-election",9),("AtlasIntel",14.1),("Reuters/Ipsos",8),("Cygnal",8),("CBS/YouGov",8),("Clarity",8),("Bedrock",8),("Marist",8),("ABC/WaPo/Ipsos",8),("Morning Consult",7.9),("Focaldata/FT",7.4),("NBC (Hart/POS)",7),("ActiVote",7),("CNBC (Hart/POS)",7),("Zogby",6),("Ipsos mail study",6),("Rasmussen",6),("Leger",6),("Echelon/NetChoice",5),("Echelon omnibus",5),("Harvard-Harris",4),("Penn State/YouGov",4),("Targoz",3)]
NAT24=-1.5
def parties(c):
    (a,pa),(b,pb)=[(s.rsplit(" (",1)[0],s.rsplit("(",1)[1].rstrip(")")) for s in c.split(" vs ")]
    return {a:pa,b:pb}
def rows():
    out={"senate":[],"house":[],"governors":[]}
    sp,gp=J("frozen/senate_polls.json"),J("frozen/gov_polls.json")
    for r in J("frozen/senate_model.json")["races"]:
        out["senate"].append((r["state"],sp[r["state"]]["fundamentals"].get("pres_2024_margin_D"),r["p_challenger"],r["challenger"],None))
    for r in J("frozen/gov_model.json")["races"]:
        out["governors"].append((r["state"],gp.get(r["state"],{}).get("fundamentals",{}).get("pres_2024_margin_D"),r["p_challenger"],r["challenger"],None))
    for r in J("frozen/house_model.json")["races"]:
        if r.get("fixed"): continue
        out["house"].append((r["district"],r["pres"],r["p_dem"],r["dn"],r.get("dem")))
    return out
R=rows()
def score(ch,swing=None):
    """Returns (right, called, D-side wins predicted, missing-pres count) on called races."""
    right=n=dpred=miss=0
    for key,pres,p,a,_ in R[ch]:
        x=RES[ch].get(key) or {}
        w=x.get("winner")
        if not w: continue
        par=parties(x["candidates"]); wp=par[w]
        nonr = [k for k,v in par.items() if v!="R"]  # the D (or non-Republican) side
        if swing is None:
            fav = a if p>=0.5 else [k for k in par if k!=a][0]
            predD = par[fav]!="R"
        else:
            if pres is None: miss+=1; predD = p>=0.5 if par[a]!="R" else p<0.5  # no presidential margin: fall back to our call
            else: predD = pres+swing>0
        actD = wp!="R"
        n+=1; right+= predD==actD; dpred+=predD
    return right,n,dpred,miss
actual={ch:sum(1 for k,_,_,_,_ in R[ch] if (RES[ch].get(k) or {}).get("winner") and parties(RES[ch][k]["candidates"])[RES[ch][k]["winner"]]!="R") for ch in R}
for ch in R:
    r,n,d,_=score(ch)
    print(f"\n== {ch}: {n} called races; non-R winners actual {actual[ch]}")
    print(f"  OUR MODEL              right {r}/{n}  non-R predicted {d} (err {d-actual[ch]:+d})")
    res=[]
    for name,m in POLLS:
        rr,nn,dd,miss=score(ch,m-NAT24)
        res.append((rr,name,m,dd,miss))
    for rr,name,m,dd,miss in sorted(res,reverse=True):
        tag="BETTER" if rr>r else "tie" if rr==r else ""
        print(f"  {name:22} D+{m:<5} right {rr}/{n}  non-R predicted {dd} (err {dd-actual[ch]:+d}) {tag}{'  pres missing '+str(miss) if miss else ''}")
