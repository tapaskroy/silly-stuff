# Party-wing rules (wings.html)

The brief given to research agents classifying 2026 nominees. The same rules place winners (house_incoming.json, senate_incoming.json),
departing members and losing nominees (losers.json).

## Recorded votes decide first, where a member has them

- House Democrats: the Jul 15, 2026 Massie amendment to strip Israel military aid (clerk 2026 roll 243). Yea = critical of the aid.
  Progressive = economically left AND not supporting Israel aid; everyone else Mainstream.
- House Republicans: Aye on the Jul 18, 2025 Greene amendment barring Ukraine aid (2025 roll 209) = Nationalist; otherwise Yea on the
  Apr 2024 Ukraine supplemental H.R. 8035 (2024 roll 151) = Mainstream; mixed or no record: placed on policies as below.
  combine_house.py applies these to the House research.
- Senate Republicans: the Apr 23, 2024 H.R. 815 Ukraine vote. On Voteview that is S118 rollnumber 506 (clerk 118-2 #154): Voteview numbers
  roll calls per Congress, so never look up the clerk number as a Voteview rollnumber.

## Agent brief (losers; also used for newcomers with no record)


Each input entry is a 2026 House or Senate general-election nominee (a loser, or a winner with no voting record).
Classify each into a wing of their own party, judged by their actual policies (platform, statements, record, caucus, endorsements), not by Trump endorsement alone.

Democrats (and independents running against a Republican, e.g. Osborn, Bodnar, Achilles, Bengs: classify them on the Democratic scheme):
- Progressive: left economics (Medicare for All, Green New Deal, CPC membership or would-join, Justice Democrats / WFP / DSA / Our Revolution / Sanders / AOC / PCCC endorsement, anti-corporate populist left) AND not pro-Israel.
- Mainstream: everyone else. Support for Israel (AIPAC/DMFI backing, opposing conditions on Israel aid, "unwavering support") puts a Democrat in Mainstream even if economically left. Blue Dog, New Dem, Problem Solvers, moderate, pro-business = Mainstream.

Republicans:
- Nationalist: America First / MAGA-movement policy: opposes Ukraine aid, Freedom Caucus or would-join, restrictionist immigration as a central theme (mass deportation, ending birthright citizenship), Christian-nationalist themes, election denial (objected to 2020 electors), anti-establishment populist. Not necessarily hardline.
- Mainstream: establishment/business/defense hawk, supports Ukraine aid, Problem Solvers / Main Street, governing-conservative. A Trump endorsement does not by itself make someone Nationalist; go by policies.
- Former members of Congress: use their record (2024 Ukraine aid H.R. 8035 / H.R. 815, the 2025 Greene amendment barring Ukraine aid, Jan 6 2021 objections, Israel votes).

Research each with web searches (campaign site, Ballotpedia, local news, endorsement lists). When fetching with curl use: curl -sL -A "Mozilla/5.0". Never put any email address or personal identifier in any request.
If evidence is thin, make your best call from what exists and set confidence "low".

Output: write a JSON array to the output path given, one object per input entry, keeping the input fields and adding:
  "full_name", "wing" ("Progressive"|"Mainstream"|"Nationalist"), "confidence" ("high"|"medium"|"low"),
  "signals": {for D: "economic": "left"|"center"|"right"|"unknown", "israel": "supports"|"critical"|"neutral"|"unknown"; for R: "ukraine_aid": "supports"|"opposed"|"unknown", "immigration": "restrictionist"|"moderate"|"unknown"},
  "evidence": one or two sentences, "sources": [urls].
Then reply with just a count by wing and any entries you found odd (e.g. wrong candidate, withdrawn).
