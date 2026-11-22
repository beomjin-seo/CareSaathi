# r-writeups: participant and winner write-ups, Virtue Foundation x Databricks hackathons

Research date: 2026-11-21. Every claim is tied to a URL that was actually opened (Devpost pages via curl, GitHub raw files, one blog rendered in a browser pane).

Note on quoting: a content-reproduction limit applies to this session, so this report carries one verbatim prose quote (section 1.2). Everything else is paraphrase plus short literal locator strings in backticks (badge labels, identifiers, figures, formula terms) that can be found on the cited page with a text search. Items marked INFERENCE are my reading, not something a page states.

## 0. Bottom line

- The DAIS 2026 event is the Databricks Apps & Agents for Good Hackathon 2026 (Devpost slug `dais-for-good-2026`), Jun 15-16 2026, San Francisco, 362 participants, 122 gallery entries, $17,500 in prizes. Same 10,000-row / 51-column India dataset and the same core requirements as the CMU brief. CMU's task is essentially its Track 3 (Referral Copilot) with explanation made the pass/fail rule.
- Winners by Devpost badge: 1st Data Readiness Desk (Track 4), 2nd Asclepius (all four tracks in one app), 3rd CareSignal (procedure + location ranking with a trust card).
- Published DAIS judging criteria, unweighted: Product judgment, Evidence and Uncertainty, Technical Execution, Ambition. A later Hack-Nation run of the same challenge, as transcribed in a participant repo, weights them 35 / 30 / 25 / 10 with Evidence & Trust first.
- No judge commentary was found anywhere. The "what separated winners" section is inferred from winners' own write-ups against non-winners' write-ups.

## 1. CONFIRMED about the DAIS 2026 event

### 1.1 Event facts
Source: https://dais-for-good-2026.devpost.com/
- Dates `Jun 15 – 16, 2026`, San Francisco, invite only, `$17,500 in cash`, `Participants (362)`, teams of 2 to 4.
- Target users named in the brief: non-technical healthcare planner, NGO coordinator, analyst.
- Tracks: `Track 1: Facility Trust Desk`, `Track 2: Medical Desert Planner`, `Track 3: Referral Copilot`, `Track 4: Data Readiness Desk`.
- Track 3 examples are the same two the CMU-style briefs use: dialysis near Jaipur, emergency surgery near Patna. Output is an evidence-attached shortlist.
- Core requirements match the CMU list (Free Edition app, provided dataset, non-technical workflow, cite facility text for any important claim/score/ranking, communicate uncertainty) plus one more: persist user actions (notes, overrides, shortlists, scenarios, review decisions).
- Judging criteria labels: `Product judgment`, `Evidence and Uncertainty`, `Technical Execution`, `Ambition`. Sub-questions ask whether the user is clear, whether outputs are grounded in citations, whether uncertainty is handled honestly, whether the app works reliably live.
- Submission: Git repo, live Databricks App, three-minute demo.
- Track 3 minimum workflow (https://developers.databricks.com/hackathon/challenge, read via summarizer): ranked candidates, each showing distance, matching evidence, missing or suspicious evidence, and a save-to-shortlist action.
- Gallery (https://dais-for-good-2026.devpost.com/project-gallery, pages 1-6 parsed): 122 entries, three with a winner flag.

### 1.2 1st place: Data Readiness Desk (Track 4)
Sources:
- Devpost https://devpost.com/software/project-cavallo (badge `1st Place Gift Card`; three team members)
- Winner blog https://cavallotechnologies.ca/news/fix-the-foundation-how-we-won-the-databricks-hackathon-2026 (dated 2026-07-06)
- Repo https://github.com/sundarep-ai/databricks-for-good-hackathon (README.md, ABOUT.md, hackathon_task.md presenter guide, databricks/facility_claim_evidence.sql)

Why they chose the track. The blog says a few hours of exploration plus a conversation with the person who assembled the dataset exposed conflated records. The one verbatim quote in this report, from that blog: "a single record often represented data from several distinct hospitals merged together". They concluded all four tracks depend on fixing this first.

Approach:
- Unit of trust is the (facility, specialty) claim, not the row. About 10k facilities become about 118k claims (locator: `118,211`).
- Formula (locator: `0.45·E + 0.15·A + 0.15·I + 0.15·S + 0.10·R`), multiplied by coherence C.
  - C coherence asks whether the row is one real place. It multiplies the whole score, so a likely-merged row lowers every claim on it. C = state factor x spread factor x dispersion factor x attribution factor.
    - State factor: agreement between the state implied by coordinates, by PIN code, and by address (all agree 1.0; three distinct 0.2).
    - Spread factor: distance from coordinates to PIN centroid (<50 km 1.0, <200 0.8, <500 0.5, else 0.2).
    - Dispersion factor: distinct source domains (<=8 gives 1.0, falling to 0.6 at >=25).
    - Attribution factor: share of the row's claims whose evidence is about this facility, floored at 0.3.
    - `merge_flag = coherence < 0.5`.
  - E evidence tier: 0 list-only (0.10), 1 asserted in prose (0.40), 2 named procedure or service (0.70), 3 named equipment and procedure (0.95).
  - A source authority (source type weights, government-domain bonus, penalty for off-topic domains such as real-estate, insurance, travel, marketplace).
  - I independent corroboration = min(1, mentions / 3), forced to 0 when tier is 0 or the evidence is about another facility.
  - S India Post consistency checks. R recency with a 5-year decay, 0.30 when undated.
- LLM is used only to extract evidence. One `ai_query` call per facility (locator: `databricks-claude-sonnet-4`, `failOnError => false`, json_schema response) returns per specialty a tier, verbatim spans, and a `same_facility` boolean. A lexical fallback exists.
- Badges: Verified >= 0.75, Likely >= 0.50, Claimed >= 0.25, else Unsupported; Disputed overrides when evidence points to another facility. A ceiling ties the badge to the tier: tier 0 cannot exceed Claimed, tier 1 cannot exceed Likely.
- A separate confidence band (high / med / low) from five indicators, kept apart from trust.
- Two headline numbers on purpose: readiness `73.61` and review burden `43.33`, so a good readiness score cannot hide the backlog.
- Reported data facts: `10,077` distinct facilities after dedup, `2,249` likely-merged records, `88` schema-shifted rows, `40.38 %` of claims with no supporting text, `13.39 %` disputed claims, `124` records without usable coordinates.
- Review queue ranked by leverage = sum of issue severity weights x (1 + claims affected). Decisions (accept, reject, needs-split, fix-field, defer) are stored per issue in Lakebase.
- Assistant: OpenAI `gpt-4.1` agent with web search and a Genie tool; the UI shows the SQL Genie ran.
- Stack: pandas pipeline, Delta / Unity Catalog, Genie, Lakebase, FastAPI + React Databricks App, mock CSV backend for local runs.
- Demo preparation committed to the repo: 60-second pitch, click-by-click script, anticipated Q&A (the first anticipated question is whether the score is a black box), numbers cheat sheet.
- Stated pivots: they first tried letting the LLM judge claims and withdrew that; they found list-only claims reaching Likely through repetition and gated corroboration to stop it.

Judge praise: not published. The blog attributes the win to fixing the data foundation first.

### 1.3 2nd place: Asclepius (all four tracks)
Sources:
- Devpost https://devpost.com/software/asclepius-mdbkwl (badge `2nd Place Gift Card`; three team members)
- Repo https://github.com/fulks89-hub/Databricks-2026-Hackathon-Devon (data/CLEANING_REPORT.md, docs/AI_GROUNDING.md, SQL files)

Devpost description:
- One rule across the product: a weak claim is never shown as fact.
- Referral Copilot: location + need gives an evidence-attached shortlist; a grounded assistant answers in plain language and Hindi using facility text.
- Citation guard (locator: `literal-substring citation guard`): Llama 3.3 70B output is checked so each quote is re-anchored to the real source text, and ungroundable statements are refused.
- Desert planner over 706 districts. Their first score put every unmapped district at maximum scarcity; they rebuilt it to separate `189` unknown-supply districts from true gaps.
- Missing data bridged with labelled proxies: NFHS-5 prevalence for demand, an LLM symptom-to-specialty map.
- Stack: AppKit (React/TypeScript + Node), Lakebase, Unity Catalog medallion, Vector Search, SQL warehouse, MapLibre.
- Free Edition constraints they hit (locator: `a 3-app cap, 24h auto-stop`), plus the SQL warehouse being disabled mid-event.
- Their lesson: treat communicating uncertainty as a feature.

Repo detail. docs/AI_GROUNDING.md is a design spec; how much of it shipped cannot be confirmed from the page.
- A citation is `{unique_id, field, char_start, char_end, quote}` and the quote must be a literal substring of the named field; otherwise the response is `INSUFFICIENT_EVIDENCE`.
- Chunks never cross a field boundary, are roughly 350-600 characters, and keep character offsets. Hybrid Vector Search with a SQL keyword fallback on timeout.
- Uncertainty chip 0-100 = 100 x (0.45 retrieval similarity + 0.35 model support + 0.20 field coverage) x trust multiplier, minus penalties for sparse fields, weak coordinate source, unmapped district and degraded retrieval. Components are returned so the UI can show the breakdown.
- Single-facility retrieval filter so a citation cannot come from another facility's text.

Cleaning report (data/CLEANING_REPORT.md):
- `10,088` rows in, `10,077` out; the 11 removed were byte-identical duplicates. `88` rows have a non-UUID id from column-shift corruption; kept and flagged with `id_valid`. A heading records that the presenters said the ids were imperfect.
- Coordinates validated against an India bounding box; 35 rows backfilled from PIN code with a `coord_source` marker; 89 nulled. Outliers nulled (capacity up to 200,000, doctor count up to 15,000).
- `state_norm` derived from the PIN directory because the raw state field had 253 distinct messy values.
- Policy: corrupted rows flagged rather than repaired; no imputation.

### 1.4 3rd place: CareSignal (closest in shape to the CMU task)
Sources:
- Devpost https://devpost.com/software/caresignal-c1o837 (badge `3rd Place Gift Card`; two team members)
- Repo https://github.com/aerkothalanka/caretrust (README.md, backend/scoring.py, docs/IMPLEMENTATION_BRIEF.md)
- Project site https://care-signal.dev/ (states Databricks announced it as 3rd place)

Approach:
- Demo story in the implementation brief: search a procedure, view top facilities, open a trust card, ask the assistant, play the voice assistant, submit a human verification, see the ranking change.
- Score out of 10 from keyword rules, ten labelled components (locator: `SCORE_ALLOCATION`): specialties match 1.5, procedure match 1.5, equipment support 1.0, capability support 1.0, description support 1.0, source URL relevance 1.0, contactability 0.75, location completeness 0.5, human verification 1.5 (rejected gives -1.5), freshness 0.25. Explicit penalties each add a plain-language uncertainty flag (no source URL, no contact, sparse support, service inferred from related text only).
- Seven fixed procedures (eye care, cardiac surgery, ICU, dialysis, oncology, maternity, emergency/trauma), each with term, equipment and capability keyword lists.
- Trust card lists each component with the matched terms, up to five snippets (field label plus the first 240 characters) and the source URL.
- Human verification persists and moves the score. A voice call-assistant concept explains rankings aloud.
- Framed as decision support rather than automated decision-making.
- Nothing in the README, Devpost text or scoring.py handles merged records or contradictory locations.

INFERENCE: the simplest scoring of the three winners. It placed on a clear user, a readable breakdown, a human loop that visibly changes the ranking, and polish.

### 1.5 Non-winning DAIS entries with detailed write-ups
None of these carries a winner badge.
- CareRoute (Track 3) https://devpost.com/software/careroute-case-to-facility-referral-navigator: 32-item controlled capability vocabulary with refusal when nothing fits; three extraction passes then an LLM verification pass over `12,096` keyword-only claims (1,105 promoted, 10,991 deleted); two badges, verified by free text vs call to confirm; says so when the nearest option is far (example `~159 km`); Spatial SQL + H3; input in any major Indian language; offline dataset plus one cheap parse call and deterministic ranking at query time.
- Referral Copilot, solo https://devpost.com/software/referral-copilot-find-care-nearby-backed-by-evidence: two separately labelled signals, a facility-level evidence score (0-12) and a per-need signal (cited, listed, or free-text mention only); city reference point is the median of facility coordinates after the mean was pulled about 20 km off by outliers; LLM parses the query and does nothing else.
- SOS https://devpost.com/software/referral-copilot: `ai_query` standardisation into a gold index; need-specific relevance so a hand fracture does not match dental oral surgery; tells the user when a requested preference (ratings, equipment age) is not in the dataset.
- MatchCare https://devpost.com/software/matchcare: 26 regex attribute flags, a what's-missing section per result, a 5-node LangGraph chain removed because it added 8-12 seconds per query; conclusion that precomputed signals served a short demo on a cold warehouse better than live reasoning.
- Trust Desk (DAIS entry) https://devpost.com/software/trust-desk: LLM handles language only, a deterministic seven-dimension engine scores; 129 unit tests; weights renormalised over the dimensions that could be scored; returns insufficient data rather than a guess.
- Phantom Census https://devpost.com/software/phantom-census: blocked record linkage for duplicates; measured that `16,388 of 19,561` PIN codes span more than one post office, so PIN-centroid distance wrongly flagged about 19% of facilities and they switched to nearest post office; a founding-year check wrongly flagged real 17th-century hospitals; raw vs adjusted map toggle; no LLM in the verdict path.
- GIFT Gauge https://devpost.com/software/gift-gauge-governance-integrity-facility-trust-gauge: SQL score from 45% supporting ratio, 25% evidence breadth, 30% facility match confidence; Splink merge recommendations approved by a human; hit the output-token rate limit (429) on a roughly 3,900-row batch.
- Indie Referral Pilot https://devpost.com/software/indie-referral-pilot: when no verified local facility exists it says so and gives a safe next action (PHC/CHC, ASHA/ANM, 104, 108 ambulance); Telugu input.
- TrustRoute AI https://devpost.com/software/trustroute-ai-s2aep7: Claude for intake and plan text, deterministic rules for matching, a data-trust/debug panel exposing the trace to judges.
- ArogyaTrust https://devpost.com/software/arogyatrust: weighted keyword engine plus Llama per-capability verdicts (true / false / unclear) with supporting phrases; ranks by trust and proximity.
- Rearc participant blog https://rearc.io/blog/dais-2026-hackathon (read via summarizer; the noop.app mirrors were unreachable): Track 2 team, Haversine accessibility plus a linear-regression risk score registered in MLflow, Lakebase sync, map UI. The author reports not winning.

## 2. ADJACENT: earlier and later Virtue Foundation x Databricks challenges

### 2.1 Hack-Nation, Feb 7-8 2026, Bridging Medical Deserts (Ghana)
- 2nd place (self-reported): https://github.com/pidoxy/hacknation (locator: `2nd place — Databricks challenge`); also listed on the author's page https://www.pidoxy.com/awards. 797 cleaned Ghana facilities from 1,003 raw rows. GPT-4o-mini extraction with per-field confidence that the README itself says is uncalibrated; LangGraph supervisor and sub-agents over FAISS with tracing and row-level citations; dedup by merging on id and unioning list fields; 43 anomalies flagged; 16-region x 10-capability gap matrix; Leaflet map; ElevenLabs voice in and out.
- 3rd place (self-reported): https://janchen.xyz/ (locator: `3rd Place in Databricks Track`) and https://github.com/sharckhai/neo-command. OpenAI Agents SDK supervisor with analyst, verifier, planner and RAG agents over a NetworkX knowledge graph of 742 facilities; advocate / skeptic / judge debate giving a 0-100 confidence and one of four verdicts; rule-based five-step extraction with row-level citations; retrieval filter that drops aspirational and referral-only language before the agent sees it; planner scoring Coverage 40 / Readiness 30 / Equity 30.
- Placement not stated: https://github.com/FarahBaraket-03/MedBridgeAI (six LangGraph agents, reciprocal rank fusion over three vectors per facility, negation detection, IQR anomaly thresholds); https://github.com/EmmaSampietro/Bridging-Medical-Deserts.
- 1st place for this track: not found.

### 2.2 Hack-Nation 5th Global AI Hackathon, Apr 25-26 2026, Challenge 03 Serving A Nation (India 10k)
- Rubric as transcribed by a participant, https://github.com/amaan784/pramana-care-ai: Discovery and Verification 35%, Intelligent Document Parsing 30%, Social Impact and Utility 25%, User Experience and Transparency 10%; stretch goals for agentic traceability, self-correction loops and a crisis map. Placement not stated.
- https://github.com/babar-ai/CareMap: three-agent chain (query, vector search, validator). Trust score starts at 100 and subtracts for six contradiction rules (for example ICU claimed without ventilator or monitor, minus 25). Outcome `9,320` of 10,000 green, mean `91.6/100`. Placement not stated. INFERENCE: a penalty-only score barely separates facilities on this data, which contrasts with the 1st-place DAIS finding that about 40% of claims have no supporting text.
- Winners: not found.

### 2.3 Hack-Nation 6th Global AI Hackathon, Challenge 04 (same four tracks as DAIS)
Source: https://github.com/vahekhumaryan/trust-desk (README.md, docs/challenge.md, docs/pitch.md). Placement not stated.
- Evaluation as transcribed in docs/challenge.md: `Evidence & Trust 35%`, `Product Judgment 30%`, `Technical Execution 25%`, `Ambition 10%`. Product judgment is glossed as a real decision problem rather than technology behind a chat box.
- The brief's own example: an advanced-surgery claim with no anesthesiologist listed must rank below one corroborated across fields.
- Open research questions in the brief: confidence without ground truth, claims versus evidence, data desert versus medical desert.
- The brief shipped the prompts and pydantic models used to generate the dataset (docs/starter/*.py). The author designed the scorer around those extraction failure modes.
- Author's approach: score = corroboration 40 + completeness 20 + web presence 25 + geo validity 15, minus suspicion penalties; each score shown as a range whose width reflects what the record cannot show; about half of high-acuity claims uncorroborated (ICU 51%); self-validation through odds ratios between equipment and procedure corroboration (1.8 ICU, 3.6 maternity, 5.1 dialysis); LLM audit on demand and cached, as a second opinion; 189 no-data districts versus 82 districts with only unverified claims; 14-check pre-demo smoke test; note that Claude, GPT and Gemini endpoints were rate-limited to zero on Free Edition at the time, so `gpt-oss-120b` was used.

### 2.4 Other
- GitHub lists Accenture x Databricks hackathon repos on a Virtue Foundation track (Ghana and India). Winners not found.

## 3. Lessons: what separated winners from the rest

Caveat: no judge commentary exists in what was found, and several non-winners describe similar ideas. These are patterns in what winners emphasised.

1. Lead with one specific, measured finding about the data. 1st: merged records and a coherence gate. 2nd: 189 districts are unknown, not deserts. The 1st-place team got its finding by talking to the person who built the dataset.
2. Score the claim (facility x service), not the facility. Keep two signals apart: is this record one coherent real place, and is this particular service evidenced.
3. LLM extracts, a published formula decides. 1st place dropped an LLM-judge design. Weights sit in one config file and can be shown on screen.
4. Gate by multiplication and cap by evidence tier, so repetition or rich text cannot lift a list-only or merged-row claim.
5. Enforce citations mechanically: literal-substring check, field-bounded spans, refusal when nothing grounds the statement.
6. Make uncertainty structural: tiered badges, a separate confidence band, ranges, unknown kept distinct from absent, bad rows flagged and kept.
7. Close the loop with a persisted human action that changes the output.
8. Product story can outweigh model sophistication. 3rd place used keyword scoring with a named user, a short flow and a readable breakdown.
9. Demo engineering: precompute offline, keep the query path deterministic and fast, keep a fallback backend, rehearse script, Q&A and numbers.
10. Patterns that appear only among non-placing or lower-placing write-ups: long multi-agent chains, debate verifiers, predictive risk models without row-level evidence, penalty-only scores that rate almost everything green.

## 4. Relevance to the CMU build

- Minimum per recommendation: distance, matching evidence quoted with its field name, missing or suspicious evidence, and how the score was computed.
- Proven design to reuse: evidence tiers 0-3 per (facility, service); coherence gate from coordinate-state vs PIN-state vs address-state, coordinate-to-PIN distance, source-domain dispersion and an LLM same-facility flag; badge ceilings; separate confidence band.
- Geography pitfalls others measured: PIN centroid is a poor reference (use nearest post office); use the median for a city reference point; raw state field is dirty (use PIN-derived state); 88 column-shifted rows; 11 exact duplicate rows; out-of-India coordinates; absurd capacity and doctor counts.
- Honest outputs write-ups valued: saying the nearest option is far and to call first, refusing needs outside the vocabulary, a call-to-confirm tier, stating which requested preferences the data cannot answer.
- Free Edition risks reported: daily compute limits, 24-hour app auto-stop, cold starts of warehouse, model serving and Lakebase, output-token 429s on bulk LLM runs, a 25 MiB inline result cap, some foundation-model endpoints unavailable at times, a SQL warehouse disabled mid-event.
- DAIS additionally required persisted user actions. The CMU brief does not list it, but all three winners had it.

## 5. NOT FOUND

- Any judge praise or criticism of a DAIS 2026 project.
- The Databricks LinkedIn / X winner announcement itself (seen only as relayed on care-signal.dev).
- LinkedIn posts by winners (LinkedIn returned HTTP 999).
- Medium, Substack, dev.to, Reddit or X write-ups about the DAIS event.
- YouTube demo videos for DAIS winners. The Hack-Nation 2nd-place README links two YouTube videos that were not opened.
- 1st place of the Hack-Nation Feb 2026 Databricks track; winners of the Hack-Nation 5th and 6th Databricks challenges; Accenture x Databricks Virtue Foundation track winners.
- A finalist shortlist for DAIS beyond the top three.
- Asclepius root README (404) and live app URL.
- Independent confirmation of the Hack-Nation rubric weights beyond participants' transcriptions.
- Any prior CMU Data Science Club x Databricks datathon write-up.
