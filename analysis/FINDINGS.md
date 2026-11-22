# Findings from the exploration (2026-11-21)

Every number below comes from the scripts in this folder. Re-run them from the project root:

```
python -I pipeline/claims.py        # ~2 min, writes pipeline/out/claims.csv and hits.pkl
python -I analysis/a1_nfhs.py
python -I analysis/a2_controls.py
python -I analysis/a3_converge.py <path to the 1st-place team's rows.csv>
```

## 1. The facility table barely sees the public sector

- NFHS-5: in the median district, 77% of births that happen in a facility happen in a public one.
- Facility table: 5% of rows are public (8.6% of hospitals). Checked two ways: `operatorTypeId` and facility names. 501 of 9,989 rows are public by either test.
- By state: Madhya Pradesh 91% of facility births are public, 5.7% of table rows are public. Bihar 76% vs 8%. Uttar Pradesh 74% vs 3.4%.
- Consequence: a result list is a ranking of mostly private facilities. Every answer must say so.

## 2. Facility names give free control groups

- Negative controls: 2,613 single-specialty facilities by name (dental, eye, skin, physio, ayurveda/homeopathy). They should not offer dialysis, C-section, NICU, cardiac surgery or burn care.
  - Plain keyword search says 178 of them (6.8%) offer at least one of those.
  - Evidence tier 2 or higher: 45 (1.7%). After the row-trust gate: 28 (1.1%).
  - The control group is not perfectly clean. Reading the misses shows a few true cases, such as a plastic surgery and burns centre. Treat 6.8% and 1.1% as upper bounds and hand-check the 45.
- Positive controls: facilities whose name states the service (65 for dialysis, 181 maternity, 133 children/neonatal, 145 heart, 471 imaging).
  - Dialysis: tier 3 in 38.5% of positives vs 0.25% of negatives, tier 2 26.2% vs 0.25%, tier 1 7.7% vs 0.33%, no text 27.7% vs 99.2%.
  - Likelihood ratios fall in the order strong > medium > weak for dialysis, obstetric, NICU and MRI. This is the data-based reason for the tier order.
  - 28% of facilities named for dialysis or kidneys have no dialysis text at all. "No evidence" must never be shown as "does not offer".
- `specialties` is circular: it contains nephrology for 97% of kidney-named facilities, and for 21% of all the others. It follows the name and adds noise. Treat it as the weakest evidence.

## 3. Independent warning signs point at the same rows

Signs built from different columns:
geo (coordinates, postcode, city disagree), text (a sentence names another place), contact (phone codes from 3+ areas), source (6+ distinct source ids).

- Lift between geo, text and contact is 3.7 to 5.9. Source ids: 1.8 to 2.7.
- Among the 2,613 control facilities, the share with an impossible acute-care claim rises with the number of signs: 0 signs 1.3%, 1 sign 1.1%, 2 signs 2.4%, 3 signs 7.1%, 4 signs 17.9%. Counts are small (45 cases in total).
- The 1st-place team's LLM "claims about another facility" flag (attr_f < 0.7) has lift 0.7 to 1.3 against all of these. It does not agree with the physical signs.

## 4. NFHS shows where the public sector does almost no C-sections

- 49 districts have a public-facility C-section rate under 3% (Bihar 18, Uttar Pradesh 13, Madhya Pradesh 7).
- Bihar median district: 78% of births in a facility, public C-section rate 3.25%, private 40.8%.
- Araria (Bihar): 66% of births in a facility, public C-section rate 4.9%, private 45.2%, zero table facilities matched to the district.
- 113 districts have a private C-section rate of 60% or more.

## 5. Tried and dropped

- Same facility recorded twice as a test-retest check: only 1 pair found.
- Identical sentences filed under different hospitals: the matches are generic template sentences and lab test menus, not stolen facts.
- Coordinates stacked on one point: 13 rows. Not an issue.
- District C-section rate vs count of strong-evidence obstetric facilities: correlated (0.26), but less than plain facility count (0.38). It reflects district size, so it does not validate the tiers.

## Limits

- District matching is by name: 498 of 706 NFHS districts matched, 8,833 of 9,989 facilities assigned. Zero-facility counts by district are inflated by name mismatches. State-level numbers do not depend on this.
- Likelihood ratios come from small groups and from controls chosen by name. Use the order, not the exact values.
- Warning-sign inputs for geo, text, contact and source come from the earlier draft tables in `research/data_work/`. Their code was lost with the temp folder and needs to be rebuilt in `pipeline/`.

## 6. District indicators do not tell us which hospitals are capable (tested, mostly negative)

Idea tested: if a district scores above average on an NFHS indicator, its hospitals look more capable in the table.
NFHS has one row per district, from a household survey. It has no hospital-level values, so the test is district against district.

- Full scan (`a4_scan.py`): 83 indicators x 28 facility-side measures, 202 districts with 5+ hospitals, 2,324 tests. 39 pass a 5% false-discovery threshold. 19 remain after removing district size and the general development axis. Largest correlation is 0.35.
- Median split on every indicator: districts above the median on development-type indicators (4+ antenatal visits, schooling, C-section rate) have about 0.3 more services with evidence per hospital, on a base of 2.6. Deprivation indicators (underweight, unmet need) go the other way. Only 11% of indicators reach p < 0.05.
- Pairs that should be linked are not (`a5_sector.py`): district C-section rate vs share of hospitals with obstetric evidence, rho -0.01. Blood sugar vs dialysis evidence, -0.01. Cancer screening vs chemotherapy evidence, -0.04.
- Sector-specific check: private hospitals show obstetric evidence in 12.6% / 13.3% / 14.5% of cases across low / mid / high terciles of the district's private C-section rate (p = 0.20, districts permuted).
- Examples of the gap: Karimnagar (Telangana) has an 82% C-section rate and 0 of 7 table hospitals with obstetric evidence. Ernakulam has 61 hospitals in the table, 5% with obstetric evidence, and a 51% C-section rate.

Reading: text evidence in the table measures how well a facility is documented online. It does not measure how much care is delivered. Use NFHS as district context on the result card and as a blind-spot warning. Do not use it to score individual facilities.

Row reliability differs a lot by state: rows flagged as mixed are 19.6% in Uttar Pradesh, 17% in Maharashtra, Gujarat, Andhra Pradesh and Madhya Pradesh, and 1.2% in Delhi (India 13.1%).

## 7. Trust formula with data-derived weights (`pipeline/trust.py`)

```
odds  = BASE x E x C            trust = 100 * odds / (1 + odds)
E = tier multiplier x 13.8 ^ (share of co-requirements found)     tier: weak 1, medium 4.3, strong 5.3
C = product over warning signs: location cells disagree 0.49, sentence names another place 0.55,
    phone codes from 3+ areas 0.32, 6+ distinct source ids 0.57
BASE = 0.84
```

- Fitted by logistic regression on 744 silver-labelled claims (517 likely real, 227 likely false) from 7 services that have both kinds. Labels come from facility names; names are not a feature.
- Cross-validated AUC 0.80 with facilities kept whole across folds. Every multiplier's 90% bootstrap range excludes 1.
- Bands from out-of-fold scores: high >= 94 (95% of silver claims above it are likely real), low < 76 (half or more below it are likely false). All 24,906 claims: 1,909 high, 11,201 medium, 11,796 low.
- Negative controls, 12 acute services: 424 keyword claims, of which 4 end in the high band, 95 medium, 325 low.
- Known miss: Aravind Eye Hospital's dialysis claim scores 81.9 (medium). Evidence text is strong (E x19.5) and only two signs fire (C x0.28). The formula alone does not remove it. A separate hard rule is needed: a single-specialty facility claiming an acute service outside its specialty is excluded and shown with the reason. That rule cannot be a fitted weight because the labels are built from the same name information.
- Trust is an index for ranking and banding, not a calibrated probability. The silver positives are specialty-named facilities, so scores for general hospitals are an extrapolation until hand labels check them.

## District size

From post office coordinates in the PIN directory: in the median district, half of the post offices lie within 24 km of the centre and 90% within 52 km, so a district is roughly 100 km across. Median 189 post offices and 22 PIN codes per district. Districts that appear in the facility table have a median of 5 facilities.

## 8. Round 2 (2026-11-21 evening to 11-22): leaks fixed, labels read, formula refit, app built

This section supersedes the numbers in section 7.

- Two leaks fixed in `pipeline/claims.py`: a service word inside the facility's own name no longer counts as evidence; false friends are excluded (dental "delivery unit", retinal angiography as cath lab, skin phototherapy as NICU, EECP as heart surgery).
- Labels: two independent readers labelled all 227 likely-false claims (97% agreement: about 190 false, 31 unclear, 4 to 7 real); one reader labelled 120 likely-real and 120 general-hospital claims. Files in `analysis/labels/`.
- Formula now (`pipeline/trust.py`, 605 labelled claims): tier some x4.8, strong x9.2, all co-requirements x25.5, own-site page x2.9; row signs: map point, postcode and city all differ x0.13, text names 2+ towns over 60 km away x0.19, built from 2+ other organisations' websites x0.46. Cross-validated AUC 0.88 overall and 0.88 within hospitals.
- Bands used by the app: strong >= 90, some >= 70, weak below. Share real on labelled claims: 98% / 82% / 44%. Independent reader on general hospitals: strong 53 real, 7 unclear, 1 false; some 20 / 9 / 1; weak 2 / 26 / 0.
- Aravind Eye Hospital dialysis claim: 27.5 (41.4 when that record is left out of fitting), and excluded by the single-specialty rule. Web check confirmed its text belongs to Delhi government hospitals (Indira Gandhi Hospital Dwarka, GTB, Lok Nayak); aravind.org lists no Hyderabad hospital.
- Tested and rejected as trust inputs: number of doctors, followers, likes, engagements, likes per follower, social count, affiliation, public/private (gain between -0.002 and +0.003), sentence counts and specificity (specialist proxy), service bundles, other-state URLs.
- External lists saved in `research/external/web/finer-official/`: NABH dialysis-listed hospitals (1,743), PMNDP public dialysis centres (1,981, used in the app), e-RaktKosh blood centres (4,686), LaQshya certified public maternity facilities.
- App: `app/index.html` (single page, data inlined by `pipeline/export_app.py`), `app/app.py` + `app.yaml` + `requirements.txt` for Databricks Apps. Picture tiles, Hindi/English, listen button, emergency vs planned ranking, district context from NFHS, exclusions shown with reasons.

## 9. App ranking rule and location handling (2026-11-22, supersedes the km exchange rule in section 8)

- Ranking: first remove weak-evidence claims and rule exclusions. Emergency: nearest first. Planned: highest trust first inside the local area. The area starts at 25 km and widens (50, 100/150, 200/300) until 5 places are found. Five results are shown.
- Location per facility comes from three signals (coordinates, postcode via the cleaned PIN lookup, stated city). 9,989 rows: all agree 7,932; coordinates differ 811 (placed by postcode); postcode differs 196 and city differs 140 (placed by coordinates); all three differ 199 (placed by postcode in 189); two usable signals that differ 211 (placed by postcode in 198); two agree and third missing 496; cannot tell 4. Overall the map point is used for 8,745 rows, the postcode centre for 1,233, the city for 11.
- Raw coordinates sit more than 10 km from the postcode centre in 2,336 rows and more than 100 km in 1,096; comparing to the nearest post office of the same PIN and to the district removes most of the first group as false alarms.
- App: Leaflet map with OpenStreetMap tiles (a post-office dot backdrop if tiles cannot load), numbered pins, "use my location", per-card WHY in the brief's three questions, per-card score equation, doctor sentences from the record plus a link to the facility's own site. `app/build.py` assembles `app/index.html`.

## 10. Ladder card, LLM reading check, must-have rule (2026-11-22 morning)

### Would an LLM grade the sentences differently? (`analysis/labels/llm_vs_regex.csv`)

300 claims (100 per regex tier, 9 services) were graded again by an LLM reader that saw only the sentences, with the same 0 to 3 scale.

- Pass or fail (grade 2+ against grade 0 to 1): the two agree on 88% of claims. Within one grade: 97%.
- The regex "strong" tier has two routes. Route A, a number next to an equipment or unit sentence (1,146 of 5,343 strong claims): the LLM also says strong for 29 of 31. Route B, the service is stated in two or more fields with no number: the LLM says "some" for 56 of 69.
- On the 605 labelled claims the two routes are equally real: route A 90% (n = 30), route B 93% (n = 121), plain "some" 86% (n = 248). Adding a separate flag for the number changes cross-validated AUC from 0.8765 to 0.8751 and its multiplier is x1.14.
- Reading: "strong" means "more likely real", not "more detailed". A number does not add information beyond repetition across fields. The regex tiers stay, because they run on all 24,815 claims in seconds on Free Edition and give the same answer every run. The LLM is used as an audit of the rule, not as the rule.
- Limit: the LLM reader saw at most 8 sentences per claim, cut to 240 characters.

### Ladder on each card (`pipeline/export_app.py`, `app/template.html`)

Each result card shows four steps with the record's own words: department (specialty list), procedure (best sentence that names it), equipment and unit (best sentence that describes the unit, or the sentence for one needed item), this place (location agreement and warning signs). The steps are an explanation of the same evidence the score uses. They are not a second score.

### Must-have rule (`pipeline/musthave.py`)

- A must-have is an item the service cannot run without. If the record does not mention it, trust stops at 89.9 (just under "strong") and the card says to confirm it by phone first. The facility stays on the list.
- An item is used only if (a) a research pass proposed it from standards (MoHFW guidelines, ISCCM, SCAI and others) and a second pass failed to refute it, and (b) at least one in three strong-evidence records for that service mention it. Items that almost no record mentions (oxygen for an ICU 14%, RO water plant for dialysis 4%) are not used: their absence tells us nothing.
- In use (share of strong-evidence records that mention it): C-section: operating theatre (66%). Heart surgery: heart theatre or heart-lung machine (76%), cardiac ICU or ventilator (59%), heart surgeon (36%). Burn: operating theatre (58%). Accident care: operating theatre (48%), surgeon (86%). Angiography: cardiologist (89%). ICU: bedside monitors (42%).
- Refuted by the second pass and not used: dialysis water plant and nephrologist, C-section anaesthesia and blood bank, newborn ventilator and specialist, MRI radiologist, burn skin graft, accident-care blood bank, ICU ventilator. No must-have for dialysis, newborn care or MRI.
- Effect: 2,020 of 8,592 strong claims move to "some" (accident care 920, ICU 632, C-section 221, heart surgery 164 of 186, angiography 53, burn 30).
- The rule does not make the strong band more accurate on the labels we have: labelled strong claims with all must-haves found are real 97.8% of the time (n = 183), those missing one 98.6% (n = 69). It is a medical precaution that tells the user what to confirm by phone. It is not a fitted weight and is reported separately from the score.
- Not reviewed by a clinician.

## 11. Honesty pass (2026-11-22, 10:30)

- What AUC 0.88 means here: there is no ground truth on service delivery. The 605 labels are proxies: 387 from the facility name alone, 218 set by an AI reader of the record. AUC says how well the score orders "likely real" above "likely false" claims on facilities held out from fitting. It does not say the service exists.
- Out-of-fold band shares (thresholds 90 / 70): strong 98% likely real (n = 228), some 84% (n = 159), weak 44% (n = 218). The app now prints these, computed at export time, in place of hard-coded in-sample values.
- Per service, out-of-fold AUC: angiography 0.94, dialysis 0.94, C-section 0.88, newborn 0.88, heart surgery 0.76 (weakest). Leave-one-service-out gives the same picture (0.76 to 0.95).
- Baselines: tier alone 0.72, co-requirement share alone 0.73, evidence features 0.79, warning signs alone 0.60, all seven 0.88.
- Record length: likely-false labelled claims come from longer records (median 2,822 characters against 1,764). With log record length added as a control, co-requirement share rises from x25.5 to x37.7 (not a length artefact), "built from 2+ other organisations' websites" weakens from x0.46 to x0.79 (partly a length proxy), "names 2+ far towns" from x0.19 to x0.29. Length itself is not used as a feature: "longer record, less trust" has no causal reading outside this label set.
- Card wording changed: the score is called a ranking index, not odds that the claim is real. Label sources and "nobody visited or phoned" are stated on every card's math panel and in "How we decide".
- An independent six-part audit workflow was started and did not finish (session ended); the checks above were run directly.
