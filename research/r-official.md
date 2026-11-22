# r-official: official record of the DAIS 2026 hackathon that used the Virtue Foundation India facility dataset

Researched 2026-11-21. Everything below is paraphrased from pages actually opened (URLs given). Prose quoting is deliberately limited to one short excerpt; other "exact strings" are titles, labels, numbers and formulas as they appear on the page.

## Bottom line

- The event exists and is fully identifiable: **Databricks Apps & Agents for Good Hackathon 2026** (the rules PDF and MLH call it "Databricks Apps & Agents Hackathon for Good"), June 15-16 2026, Marriott Marquis, San Francisco, part of Data + AI Summit, partnered with OpenAI, administered by Major League Hacking, submissions on Devpost.
- The CMU "Find the right care" brief is, almost word for word, **Track 3 (Referral Copilot)** of that hackathon plus its Core Requirements. The CMU requirement bullets (Free Edition, provided dataset, non-technical workflow, cite facility text, communicate uncertainty) are the first five of the DAIS six; the sixth DAIS requirement (persist user actions) and the "must be a Databricks App on Lakebase" requirement are not in the CMU brief.
- Winners are published on Devpost: 1st **Data Readiness Desk**, 2nd **Asclepius**, 3rd **CareSignal**.
- Judging used **four named dimensions with no published weights** (hackathon site + Devpost). The legal rules PDF lists a different, boilerplate set of five "equally weighted" criteria. No judge commentary on why the winners won was found anywhere.

---

## PART 1 - Confirmed about the specific event

### 1.1 Identity, dates, scale
| Item | What the page says | Source |
|---|---|---|
| Name | Databricks Apps & Agents for Good Hackathon 2026 | https://dais-for-good-2026.devpost.com/ , https://developers.databricks.com/hackathon/ |
| Partner / admin | Hosted in partnership with OpenAI; sponsor Databricks; administrator Major League Hacking | developers page; rules PDF (https://bit.ly/4d0Gj7w -> Google Drive) |
| Where / when | Marriott Marquis SF; June 15 8:00am-4:00pm PT opening + hacking; June 16 Hacker's Corner 11-5; judging + awards June 16 6-9pm PT | developers page; https://events.mlh.com/events/13878-databricks-apps-agents-hackathon-for-good |
| Rules PDF timing | Project period Jun 15 8:00am PT to Jun 16 2:30pm PT; judging period 2:30-6:00pm PT Jun 16; winners announced around 6pm | rules PDF sec. 1 |
| Eligibility | In-person DAIS attendees only; teams of 2-4 (rules PDF also allows solo); application-screened; capped at 500 entrants | developers page; rules PDF sec. 3-4 |
| Scale | Devpost shows 362 participants; project gallery shows 122 submissions | https://dais-for-good-2026.devpost.com/project-gallery |
| Prizes | $17,500 total: $10,000 / $5,000 / $2,500 gift cards, one winner each, plus a project highlight at the Summit | Devpost overview; rules PDF sec. 8 |
| Showcase | Winning and selected projects shown at Hacker's Corner on Jun 17 (community post says Jun 17-18) | MLH page; https://community.databricks.com/t5/learning-events/dais-registrants-apply-for-the-apps-amp-agents-for-good/ev-p/156927 |

### 1.2 Challenge statement (https://developers.databricks.com/hackathon/challenge, mirrored on Devpost)
Paraphrase: teams get 10,000 messy India healthcare facility records (structured location/specialty fields plus uneven free text about claimed capabilities, procedures, equipment, services) and must build a Databricks App that lets a non-technical planner, NGO coordinator or analyst turn that into decisions they can trust. The app should extract structure, show evidence, be honest about uncertainty, and let users save or revise work.

**Core requirements (six):** run as a Databricks App on Free Edition; use the provided facility dataset; clear non-technical workflow; cite underlying facility text for any important claim/recommendation/score/ranking; communicate uncertainty rather than presenting weak evidence as fact; persist user actions (notes, overrides, shortlists, scenarios, review decisions).

**Dataset description on the challenge page:** 10,000 records x 51 columns. All have name, state, city, lat/long, controlled specialties, description, source URLs; 9,996 have a postcode. Coverage: description 100%, capability 99.7%, procedure 92.5%, equipment 77.0%, numberDoctors 36.4%, capacity 25.2%, yearEstablished 47.8%. The page tells teams to treat the extracted fields as claims to verify, not ground truth. Evidence is spread across description, capability, procedure, equipment, specialties, source_urls.

**Marketplace listing id** (from the "Open in Databricks" link on the hackathon page): `19326b3d-db63-4627-abc0-cf4e8131a305`. The 3rd-place repo README names the catalog/tables: `databricks_virtue_foundation_dataset_dais_2026.virtue_foundation_dataset.{facilities, india_post_pincode_directory, nfhs_5_district_health_indicators}` - i.e. the same three tables the CMU brief describes.

### 1.3 The four tracks (pick one)
| Track | Question | Minimum workflow stated on the challenge page |
|---|---|---|
| 1 Facility Trust Desk | Can the facility do what it claims? | Planner picks capability + region, sees ranked facilities, expands one to inspect citations, can override with a note. Trust signal levels suggested: strong / partial / weak-or-suspicious / no claim |
| 2 Medical Desert Planner | Where are the highest-risk care gaps, and how sure are we they are real? | Pick capability + geography, see regional coverage, drill to the facility records behind an aggregate, save a scenario. Must separate real gaps from data-poor regions |
| **3 Referral Copilot** | Where should a patient or coordinator actually go? | **Location + need in; ranked candidates out; each candidate shows distance, matching evidence, missing or suspicious evidence; can be saved to a shortlist.** Example queries given: dialysis near Jaipur, emergency surgery near Patna |
| 4 Data Readiness Desk | What must be fixed before the data can be trusted for planning? | Show completeness/quality issues, a flagged-record review queue, persisted reviewer decisions |

### 1.4 Judging criteria
**On the hackathon site and Devpost (four dimensions, no weights or percentages shown):**
1. Product judgment - is the user clear; are workflow and tradeoffs thoughtful
2. Evidence and uncertainty - "Are outputs grounded in citations? Is uncertainty handled honestly?" (developers.databricks.com/hackathon)
3. Technical execution - does it work reliably in a live demo; are Databricks capabilities used well
4. Ambition - did the team go meaningfully beyond the minimum workflow

**In the official rules PDF (sec. 6) - a different list.** Stage One is pass/fail on submission completeness (public repo works, video <= 3 min, demo accessible). Stage Two scores five criteria the PDF calls equally weighted: Business Applicability, Data Relevance, Creativity, Thoroughness, Well-Architected. The section ends with a stray closing bracket and reads like template text; it does not match the four dimensions the organisers published on the event site. Ties are broken criterion by criterion in listed order, then by judge vote.

Net: the only weighting statement anywhere is "equally weighted" in the legal PDF; the four site dimensions carry no weights.

**Judges:** Devpost lists a single named judge (Elise Hollowed, who is also listed as an MLH event host). The rules PDF says the panel may be Databricks employees or third parties, with at least one independent judge. No full panel list found.

**Submission format:** Git repo + project description + live Databricks App; three-minute demo covering user, workflow, technical approach and key tradeoffs (Devpost). Rules PDF additionally asks for a public open-source-licensed repo and a <= 3 min video.

### 1.5 Winners (Devpost gallery JSON-LD + project pages)
| Place | Project | Team (as listed on Devpost) | Track | Repo |
|---|---|---|---|---|
| 1st ($10k) | Data Readiness Desk | 3 people; team wrote it up on the Cavallo Technologies site | Track 4 | https://github.com/sundarep-ai/databricks-for-good-hackathon |
| 2nd ($5k) | Asclepius | 3 people | All four in one app per Devpost (its own judge guide pitches three: T1, T2, T4) | https://github.com/fulks89-hub/Databricks-2026-Hackathon-Devon |
| 3rd ($2.5k) | CareSignal | 2 people | Not stated explicitly; README calls it a facility trust desk with discovery by procedure and location | https://github.com/aerkothalanka/caretrust |

No "finalist" list is published. Devpost only marks the three winners.

### 1.6 What each winning project did

**1st - Data Readiness Desk** (https://devpost.com/software/project-cavallo ; team write-up https://cavallotechnologies.ca/news/fix-the-foundation-how-we-won-the-databricks-hackathon-2026 ; repo README)
- Reasoning for track choice: after exploring the data and talking with the person who assembled it, they found the dominant defect was conflated rows (one row fusing several real hospitals, with contradictory locations and borrowed capabilities). All four tracks depend on that foundation, so they fixed the foundation.
- Unit of trust is the **(facility, specialty) claim, not the row**: ~10k facilities x ~11 specialties each -> ~118k claims.
- LLM is used only as an **evidence extractor** (Databricks `ai_query` returns an evidence tier, verbatim citation spans and a same-facility flag). It never emits a trust number. Final score is transparent rules.
- Formula: `trust = C x (0.45 E + 0.15 A + 0.15 I + 0.15 S + 0.10 R)` where C = row coherence (is this one real place: pin/lat-long/address agreement + number of distinct sources) acting as a multiplicative gate, E = evidence in other columns, A = source authority (official/gov boosted), I = independent corroboration, S = spatial consistency vs India Post, R = recency. All weights in one config file.
- Badges: Verified >= 0.75, Likely >= 0.5, Claimed >= 0.25, Unsupported < 0.25, plus Disputed (evidence about a different facility or contradictory geography).
- Issue rules: merged_record (coherence < 0.5), geo_conflict, disputed_claims, sparse_evidence (>= 60% of claims with no supporting text), missing_geo, future_date, offtopic_source (real-estate/insurance/travel domains).
- Review queue ranked by **leverage** = sum of issue severity weights x (1 + claims affected), scaled 0-100.
- Readiness score 0-100 = 35% coherent share + 30% (1 - dispute rate) + 20% (1 - no-evidence rate) + 15% mean coherence.
- Stack: Unity Catalog bronze -> scoring pipeline -> six analytical tables synced to Lakebase; reviewer decisions in a writable Lakebase table; Genie space over the tables; an OpenAI-powered assistant with two tools (Genie + web search) that shows the SQL it ran; FastAPI + React Databricks App.
- Their own stated lessons: picking the right unit of analysis was most of the battle; coherence gating turned "looks sketchy" into a precise signal; use the LLM only where it is strong (reading messy text) and keep scoring math transparent. Hardest part: keeping the score auditable and stopping unsupported list-only claims from scoring as trustworthy.

**2nd - Asclepius** (https://devpost.com/software/asclepius-mdbkwl ; repo docs/AI_GROUNDING.md and docs/JUDGE_STUDY_GUIDE.html)
- One app, several personas (patient, clinician, hospital, planner). Stated single rule: never present a weak claim as fact.
- Track 3 piece: patient enters location + need, gets an evidence-attached shortlist; grounded assistant answers in plain language and Hindi, citing verbatim facility text.
- **Citation guard**: retrieve chunks (Vector Search over field-bounded 350-600 char chunks with char offsets) -> LLM proposes a quote -> server independently checks the quote is a literal substring of the named source field (exact, then whitespace-normalised) -> otherwise escalates once to a stronger model and then returns INSUFFICIENT_EVIDENCE. Displayed quote is sliced from source bytes, never the model's text. Unanchored sentences are stripped.
- **Uncertainty chip** per answer: `score = clamp(100 x (0.45 sim + 0.35 llm + 0.20 cov) x trust_mult - 100 x (sparse + coord + crosswalk + throttle))`, bands high >= 75, medium >= 50, else low; trust_mult 1.0 / 0.90 / 0.75; message chip = minimum over its cited claims. Components shipped to the UI for hover breakdown.
- Four claim tiers: authority-verified / corroborated / self-reported / conflicting. They pulled the NABH accreditation registry as an independent authority tier (~16% of facilities matched) and refuse to average verified and self-reported into one number.
- **Positive-only corroboration**: first pass flagged 83% of claims unsupported; they showed this was an artifact (marketing blurbs do not list commodity equipment), so absence of evidence is displayed as neutral, never as "cannot do it".
- Desert model: per-capita severity = need x proximity (distance bands), NFHS-5 as demand proxy, Census 2011 population; **data-poor vs real-gap split** - a district with zero mapped facilities is flagged "unknown supply" (they cite 182-189 such districts) rather than scored as maximum scarcity.
- Stack: Databricks App (AppKit, React/TS + Node), Lakebase for OLTP + synced reads, UC medallion, Foundation Models (Llama 3.3 70B), Mosaic AI Vector Search, SQL warehouse. Free Edition limits they hit: 3-app cap, 24h auto-stop, one Vector Search endpoint, one sync pipeline, daily compute limits.
- Their judge guide is organised under the four published dimensions and opens and closes on "honesty" (what the app does NOT trust). That is the team's own pitch strategy, not judge feedback.

**3rd - CareSignal** (https://devpost.com/software/caresignal-c1o837 ; repo README + backend/scoring.py ; https://care-signal.dev)
- Facility Explorer, Geo Search, Trust Review, Chat Assistant in one dashboard. Positioned as decision support for families/patients, not automated decision-making.
- README features: discovery by procedure and location; trust scoring with explainable score breakdown; evidence snippets and source links; uncertainty flags where data quality is limited; human verification workflow that raises confidence over time; template-based chart assistant; a phone/voice "call the agent" concept.
- scoring.py: a fixed catalogue of procedures (eye care, cardiac surgery, ICU, dialysis, oncology, maternity, emergency/trauma), each with term / equipment / capability keyword lists, and an additive 10-point allocation: specialties match 1.5, procedure match 1.5, equipment 1.0, capability 1.0, description 1.0, source-URL relevance 1.0, contactability 0.75, location completeness 0.5, human-verification boost 1.5, freshness 0.25. Partial credit when the term appears only in weaker fields.
- Stack: React/Vite + FastAPI on Databricks Apps, Lakebase for state, UC tables; built-with list also mentions Google GenAI/Gemini for assistant and voice.

### 1.7 Judge commentary
None found. The Devpost "updates" tab has only the automated winners announcement. No Databricks blog, community post, or video explaining the decisions was located.

---

## PART 2 - Adjacent / related material (not official results)

- **Participant account (non-winner), Rearc blog** https://rearc.io/blog/dais-2026-hackathon : confirms the opening Monday presentation by Virtue Foundation, the rule set (Free Edition, agents, VF dataset from Marketplace, app sourcing from Lakebase), OpenAI credits, that the data came with population health metrics and India Post PIN codes, and a three-minute presentation to the Databricks team. Their Track 2 entry (Haversine accessibility + linear regression score) did not place.
- **Other Track 3 style entries visible in the gallery (no award):** SOS - Source Of Support; Bharosa Care; MatchCare; CareRoute; Virtue Referral Copilot; "Referral Copilot: find care nearby, backed by evidence"; CarePilot (two entries); Jeevan Rekha; Indie Referral Pilot; Care Convoy; CareBridge Referral Copilot; CareTrust India; Suvidha; TrustRoute AI. Useful as a pool of design ideas; none is marked as winner or finalist.
- **CareDelta** (https://devpost.com/software/caredelta, seen only via search summary, not opened): reported to combine query parsing, embeddings in pgvector on Lakebase and LLM re-ranking for its referral feature. Unverified.
- **Databricks for Good x Virtue Foundation blog (May 20 2026)** https://www.databricks.com/blog/databricks-good-and-virtue-foundation-partnering-connect-medical-volunteers-critical-health : describes the upstream pipeline - data from 72 low/lower-middle-income countries, 25M+ web pages through OpenAI GPT models in targeted extraction steps, entity resolution with Splink. Explains why the hackathon fields are LLM-extracted claims and why merged records exist. No mention of the hackathon.
- **Virtue Foundation won the "For Good" award in the 2026 Databricks Customer Awards** - a different programme, surfaced by search only.
- **Earlier 2020 "Hackathon for Social Good"** at Spark + AI Summit is unrelated.

---

## PART 3 - Not found
- An official Databricks recap/blog/press release naming the winners (only Devpost does).
- Any judge commentary or stated reasons for the placings.
- Published numeric weights for the four site judging dimensions.
- A full judge panel list.
- A finalist / honourable-mention list.
- A YouTube recap or recorded winner demos.
- A Virtue Foundation news post about the hackathon.
- The noop.app participant blog (ghost-mislead / gloomy-iron) could not be fetched (connection closed); LinkedIn pages returned HTTP 999.

---

## PART 4 - Implications for the CMU build (inference, labelled as such)
1. Likely rubric: the CMU organisers reused the DAIS brief, so the four DAIS dimensions (product judgment, evidence + uncertainty, technical execution, ambition) are the best available proxy. This is an inference, not something CMU published.
2. All three DAIS winners made trust in the data the product, not search. Common pattern: deterministic, inspectable scoring with weights visible; LLM restricted to reading text / extracting evidence; verbatim cited spans; explicit tier labels rather than one blended number.
3. Specific reusable techniques seen in winning repos:
   - score the (facility, service) claim, not the facility row;
   - a multiplicative coherence gate so merged/contradictory rows can never yield a confident claim;
   - India Post PIN directory as a geographic consistency check (pin vs coords vs state);
   - literal-substring citation guard with an explicit insufficient-evidence outcome;
   - absence of evidence shown as neutral/unknown, never as a negative finding;
   - uncertainty chip with a component breakdown and bands;
   - separating data-poor areas from real gaps;
   - additive score with a per-component breakdown shown to the user (3rd place).
4. Track 3's stated minimum is exactly: distance, matching evidence, missing or suspicious evidence per candidate, plus a shortlist. No DAIS winner was a pure Track 3 entry, so a strong referral tool that borrows the claim-level trust layer is differentiated rather than derivative.
5. Free Edition constraints reported by the 2nd-place team (app cap, 24h auto-stop, single Vector Search endpoint, daily compute limits, Lakebase auto-suspend) are worth planning the demo around.

## Local files saved during research
- /private/tmp/claude-501/-Users-seobeomjin--claude-spares-spare-4GOnH4/3d835f37-379f-4e18-a6c9-f4c2e143bac6/scratchpad/dl_official/rules.txt (text of the official rules PDF)
- /private/tmp/claude-501/-Users-seobeomjin--claude-spares-spare-4GOnH4/3d835f37-379f-4e18-a6c9-f4c2e143bac6/scratchpad/dl_official/challenge.html , devpost.html , devpost_gallery.html , gal_2.html ... gal_6.html
- /private/tmp/claude-501/-Users-seobeomjin--claude-spares-spare-4GOnH4/3d835f37-379f-4e18-a6c9-f4c2e143bac6/scratchpad/dl_official/gh/ (winner READMEs, Asclepius grounding doc and judge guide, CareSignal scoring module)
