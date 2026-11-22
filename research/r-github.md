# r-github: public GitHub code from Virtue Foundation / Databricks facility-dataset hackathons

Date of research: 2026-11-21. Method: unauthenticated GitHub repository search API (about 30 distinct queries), then README + main scoring code pulled from raw.githubusercontent.com for the most relevant repos. Two web searches added nothing beyond GitHub.

Quoting note: a content-quoting restriction limited this report to one verbatim quote. Every other finding carries a file/section locator and exact numbers instead, so it can be re-checked at the URL. Prize claims are self-reported in READMEs and were NOT verified against an official winners list.

---

## 0. Headline takeaways for our build

1. The exact same dataset (Marketplace "Virtue Foundation Dataset (DAIS 2026)", catalog `databricks_virtue_foundation_dataset_dais_2026.virtue_foundation_dataset`, tables `facilities`, `india_post_pincode_directory`, `nfhs_5_district_health_indicators`) was used at two earlier events with dozens of public repos:
   - Databricks "Apps & Agents for Good" Hackathon at Data + AI Summit, San Francisco, mid-June 2026 (4 tracks; Track 3 "Referral Copilot" is essentially our brief).
   - Hack-Nation 6th Global AI Hackathon, Challenge #04 "Data Legend", 18-19 July 2026, on Databricks Free Edition (same 4 tracks).
2. Two README prize claims on the DAIS event, both for simple, deterministic, explainable designs:
   - `aerkothalanka/caretrust` (CareSignal) says it placed 3rd. Architecture: additive 10-point keyword score with visible per-component breakdown, uncertainty flags, human verification loop.
   - `Shlok1375/referral-copilot` says Top 7 of 122. Architecture: regex query parse, PIN/district geocode, 50 km haversine radius, field-weighted keyword score, evidence snippets, "missing fields" list. No LLM, no embeddings.
3. The pattern nearly every serious repo converged on: deterministic scoring precomputed in SQL/Delta, LLM only at the edges (query parsing, translation, optional second-opinion audit), verbatim substring citations, evidence status bands (strong / partial / claim-only / contradictory / no data), and "absence of data is not absence of care".
4. Free Edition gotchas reported by participants: Claude/GPT/Gemini endpoints rate-limited to 0 (one team fell back to `gpt-oss-120b`; others used `databricks-meta-llama-3-3-70b-instruct`); Vector Search Delta Sync about 1 row/s (use Direct Access index or skip vectors, 10k rows scan fine); Apps stop after a 24 h runtime window; app source file limit about 10 MB; source catalog is read-only so derived tables go to `workspace.<schema>`.
5. Data gotchas reported: all columns are strings; null is the literal string `'null'` (also `''`, `'[]'`); 10,088 rows (about 65 junk/misaligned); capability/procedure/equipment are JSON-array strings of free-text claim sentences; `specialties` is a controlled camelCase vocabulary; `address_stateOrRegion` sometimes holds a district; 6 rows outside the India bbox; one team measured about 8% wrong coordinates (city-median test); one team found India Post centroids unreliable and used median of facility coordinates per city instead; one team found about 15% of facilities contain evidence bullets that look like they belong to another facility (cross-facility contamination); about half of ICU/NICU/oncology/emergency/maternity claims have zero corroboration in other fields; `websites` (plural) is source URLs, not the facility site.

---

## 1. Confirmed about specific events

### 1a. DAIS 2026 "Apps & Agents for Good" hackathon (San Francisco, June 2026) - same India dataset as ours

| Repo | Stars | Prize claim in README | Track | UI | Core technique |
|---|---|---|---|---|---|
| aerkothalanka/caretrust (CareSignal) | 0 | Placed 3rd (README line 4) | Trust desk + discovery by procedure/location | Databricks App, FastAPI + React, Lakebase | 10-pt additive keyword score, breakdown, flags, human verification, optional source-URL crawl |
| Shlok1375/referral-copilot | 0 | "Top 7 of 122 projects, 480+ hackers" (README line 8) | Referral | Databricks App (AppKit React/Express), Lakebase | Regex parse, 50 km haversine, field-weighted keyword match, evidence + missing fields |
| akshaybhan32/referral-copilot and EimisPacheco/referral-copilot-Jevan-Rekha-Lifeline ("Jevan Rekha - Lifeline") | 0 | none | Referral | Databricks App (AppKit), Lakebase pgvector | Multilingual translate-in/out, gte-large-en embeddings, weighted semantic+geo score, coordinate validation, registry verification |
| batistajldm/referral-copilot | 0 | none | Referral (Track 3) | AppKit, SQL Warehouse, Lakebase | LLM parses query only; ranking entirely in one SQL file; two-axis evidence |
| aisdk7/virtue-referral-copilot | 0 | none | Referral | Databricks App, map | Per-query evidence points to HIGH/MEDIUM/LOW; evidence dots; gap callouts |
| Vishnuja06/carepath-ai | 0 | none | Referral + trust | AppKit, Lakebase, optional Genie | Fit score + separate information-trust score; NFHS context; Care Gap Index |
| sairamkannan/CareBridge-Referral-Copilot | 0 | none | Referral | Streamlit Databricks App, Lakebase | Deterministic evidence scoring; memory tables; safety boundaries |
| TimothyVang/caregap-trust-planner | 0 | none | Desert + referral + review | Streamlit Databricks App, Lakebase | Additive trust score with penalties; labels; README maps to judging criteria |
| sachds/dais2026-virtue-healthcare | 0 | none | All 4 tracks | FastAPI Databricks App, Lakebase | LLM-extracted trust signals with exact snippets; governed agent mesh with policy gate in code |
| moganakumaran/carereach | 0 | none | Desert planner (Track 2) | Streamlit Databricks App | Two signals never collapsed (gap x evidence confidence); ai_query extraction; verified/claimed badges |
| ankitranjan-dsai/facility-trust-desk | 0 | none | Trust desk | Streamlit, Free Edition deploy notes | Retrieve-then-judge; verbatim-substring guard; negation detection |
| freeformelm/trust-first-triage-desk | 0 | none | Trust desk | Streamlit Databricks App (Free Edition) | Rules + LLM fallback classifier; polarity detection; 20 hand-labelled eval scenarios |
| abhijha8287/facility-trust-desk | 0 | none | Trust desk | Streamlit | LLM rates 7 capabilities; human review audit table |
| rkaushik2007/CareLenseAI | 0 | none | Desert planner | FastAPI + Next.js Databricks App, Genie | Risk vs confidence axes; deterministic Gold scores; LLM at edges |
| sairajuindukuri/DAIS2026_Hackathon | 0 | none | Explorer | AppKit, Lakebase, Agent Bricks + Genie | Persona switcher (NGO planner / official / patient); precomputed gold |
| ratheswaran/hackathon-DAIS-2026 | 1 | none | Desert planner | Databricks App, DeepAgents, Neo4j, Genie | Agent harness producing essays / decks / notebooks |
| d-padmanabhan/dais-2026-data-readiness-desk | 0 | none | Data readiness (Track 4) | Free Databricks App, read-only cached gold | Medallion pipeline, tunable scoring.yaml |
| madhuparmar108/HealthRefferralCopilot-DAIS2026 | 1 | none | Referral | AppKit | README is unmodified AppKit template; nothing to learn from README |
| rahulsingh-data-ai/matchcare | 0 | none | Referral (Track 3) | apx (FastAPI + React) | README is unmodified apx template |

DAIS judging criteria as reflected by a participant: `TimothyVang/caregap-trust-planner` README has a "Judging Alignment" section with five headings: Business Applicability, Data Relevance, Creativity, Thoroughness, Well-Architected. This is a participant's README, not the official rubric.

Other DAIS repos seen in search but not opened in depth: gwaghmar/dais-2026-apps-agents-for-good, WannaBeNeuralNetwork/virtue-desk, jackjamend/thar, hovanesgasparian/oasis, leandroszikora/dais26-hackaton, sonal0403/facilities-trust-desk-dais2026-hackathon-track1, shwetachandole/*, pradeepsingh87/databricks-hackathon-dais2026, devp-10/carebricks-dais2026, tylerfaulkner/dais-2026-hackathon, TarakMyneni/referral-copilot, Vaishnavicodes/medical-referral-copilot, Rahul-R-18/referral-copilot (1 star, no README), databricks-hackathon-2026/referral-copilot.

### 1b. Hack-Nation 6th Global AI Hackathon, Challenge #04 "Data Legend" (18-19 July 2026) - same India dataset, Free Edition

The brief, as transcribed by a participant in `vahekhumaryan/trust-desk` `docs/challenge.md`: three core requirements (Evidence Engine, Trust Scorer, Planner's Workflow), four tracks (Facility Trust Desk, Medical Desert Planner, Referral Copilot, Data Readiness Desk), stretch goals (agentic traceability with MLflow 3 tracing, self-correction validator, crisis map by PIN inspired by vfmatch.org/explore), and evaluation weights Evidence & Trust 35%, Product Judgment 30%, Technical Execution 25%, Ambition 10%. Submission: repo + live Databricks App + pitch video up to 3 minutes. This is a participant transcription, not the official page.

| Repo | Stars | Prize claim | Track | Notable |
|---|---|---|---|---|
| JanUllmann/MedSatya | 0 | none | Referral Copilot | Band-first ranking; exact-span citations; call-before-travel checklist; PWA with a11y toolbar; public no-login mirror |
| manojarulmurugan/hacknation-referral-copilot | 0 | none | Referral Copilot | Provenance audit, 20-capability taxonomy, WHO SARA-style readiness, composite score with penalties, radius widening |
| vahekhumaryan/trust-desk | 0 | none | Facility Trust Desk | Score ranges, odds-ratio self-validation, Genie + AI/BI dashboard, hybrid Vector Search, all on Free Edition |
| kodeezabdullah/Veridex- | 0 | none | Desert planner | Geo-resolution 60.9% to 98.5%, percentile-calibrated trust, keyword guard, Direct Access Vector Search |
| bhavana6281/sahara | 0 | none | Trust desk + 2 more tabs | Deterministic Spark trust score in Delta; LLM emits validated filter JSON, never SQL |
| Aryan-Techie/the-desert-atlas | 0 | none | Desert planner | not opened in depth |

### 1c. Earlier events (adjacent datasets)

- Hack-Nation 5th Global AI Hackathon, Challenge 03 "Serving A Nation" (April 2026, India 10k facility data): `amaan784/pramana-care-ai` (0 stars), `damsolanke/aarogya-atlas` (2 stars), babar-ai/CareMap, Tanya-garg10/MediMap-India, divine-create/aarogya. Pramana's README records a rubric: Discovery and Verification 35%, Intelligent Document Parsing 30%, Social Impact and Utility 25%, UX and Transparency 10%.
- Hack-Nation "Bridging Medical Deserts" (Feb 7-8, 2026, Virtue Foundation Ghana data): `pidoxy/hacknation` (2 stars) claims 2nd place in the Databricks challenge; also FarahBaraket-03/MedBridgeAI, EmmaSampietro/Bridging-Medical-Deserts, beemnet-bee/VIP-Layer, AmineChr54/Ai_for_global_healthcare_access, arkhangio10/CareBridge.
- Accenture x Databricks hackathon (April-May 2026, Ghana IDP agent): DeePZeeRa/databricks_accenture_hackathon_virtue_foundationtrack, OmSinha07/VirtueAudit-AI-..., sudiptabag2004/CareGap-Intelligence-Agent, prirai007/databricks-accenture-hackathon, Baishnab1708/CareBridge_AI_..., Aman-Anand-Code/medical-desert-agent, and others. Not opened in depth (different dataset, medical-desert framing).

---

## 2. Repo-by-repo architecture notes (repos opened and read)

### aerkothalanka/caretrust - "CareSignal" (DAIS; README claims 3rd place; 0 stars)
Opened: README.md, PROJECT_STORY.md, backend/scoring.py, backend/trust_verifier.py.
- Data: notebooks for bronze-to-silver on facilities and pincode directory; location cache JSON; fallback sample data so it runs without credentials.
- Retrieval/scoring: fixed list of 7 procedure families (eye care, cardiac surgery, ICU, dialysis, oncology, maternity, emergency/trauma), each with term / equipment / capability keyword lists. Score is additive out of 10: specialties match 1.5, procedure match 1.5, equipment 1.0, capability 1.0, description 1.0, source URL relevance 1.0, contactability 0.75, location completeness 0.5, human verification 1.5 (negative if rejected), freshness 0.25; then explicit penalties (no source URL, no contact, sparse support, procedure only inferred).
- Explainability: every component returned as a breakdown item (label, max, score, matched evidence); up to 5 evidence snippets labelled by field; uncertainty flags are plain sentences; even a clean result carries a reminder to verify availability.
- Trust: human verification statuses (verified / needs_review / rejected) feed back into the score; optional live crawl of up to 3 source URLs to check whether the service is still mentioned; optional Agent Bricks review.
- LLM: chat assistant and a "safe, template-based" chart assistant; voice/Twilio call-assistant concept.
- Strong: transparent arithmetic a judge can audit in seconds; human-in-the-loop that visibly changes the score; decision-support framing; polished single dashboard.
- Weak: substring keyword matching only (no negation handling, no synonym coverage beyond the lists); 7 hard-coded procedures; distance is not part of the 10-pt score in scoring.py; no entity resolution.

### Shlok1375/referral-copilot (DAIS; README claims Top 7 of 122; 0 stars)
Opened: README.md, server/routes/referral-routes.ts.
- Parse: regex for 6-digit PIN, else "<need> near|in|at <place>".
- Geocode: PIN to lat/long from India Post directory; else district name match (exact, then LIKE).
- Retrieval: all facilities within 50 km (haversine in SQL).
- Scoring: field weights capability 3, procedure 2, equipment 2, specialties 2, description 1; full-phrase hit counts double, single-keyword hit counts once. Sort by match score, tie-break by distance.
- Explainability: one snippet per matched field (about 30 chars before and 60 after the hit), plus `missing_fields` list for fields that were null.
- Extras: facility directory, NFHS-5 district indicators page, PIN lookup page, shortlist in Lakebase.
- Strong: fully explainable, zero inference cost, unit-tested parser and scorer; README argues the keyword-vs-embedding tradeoff openly.
- Weak (README admits): misses synonyms (dialysis vs renal replacement therapy); no trust/contradiction logic; hard 50 km cut-off with no widening; no LLM validation.

### "Jevan Rekha - Lifeline" (akshaybhan32/referral-copilot; EimisPacheco fork-like copy) (DAIS; 0 stars)
Opened: README.md.
- Multilingual: one LLM call translates input and extracts {need, place, lang}; English pipeline unchanged; one LLM call localises the output; facility names/phones stay literal; browser Web Speech API for voice in/out.
- Retrieval: `databricks-gte-large-en` embeddings in Lakebase pgvector, combined with haversine radius in one SQL function. Score = 0.60 similarity + 0.25 proximity + 0.10 beds + 0.05 doctors.
- Evidence: after ranking, pg_trgm picks the procedures/capabilities most similar to the need to show on each card.
- Location precedence: device GPS, then PIN, then city; city centroid = median of validated facility coordinates; India Post directory marked deprecated for centroids.
- Data cleaning: coordinate validation (inside India and within 80 km of the robust median of its own city; optional Nominatim check within 15 km); reports about 8% wrong coordinates; invalid rows never appear.
- Entity resolution: fuzzy match (name + PIN/city) against PMJAY/NABH registries scraped from a state portal, producing a "Verified" badge for 89 facilities.
- Guardrails: emergency intent surfaces 112/108 first; results under 40% similarity dropped, under 55% labelled "related"; disclaimer; graceful degradation.
- Strong: accessibility (language, voice, WhatsApp share, directions), external corroboration, relevance floor.
- Weak: similarity score is opaque to a non-technical user; beds/doctors in the ranking although those fields are 64-75% null; no explicit claim-vs-corroboration logic.

### batistajldm/referral-copilot (DAIS Track 3; 0 stars)
Opened: README.md, config/queries/facility_search.sql.
- LLM (Llama 3.3 70B) only parses free text into need + city + state; never ranks, never writes evidence.
- All ranking in one parameterised SQL file: facility evidence score 0-12 (capability present 2, source_urls present 2, lat present 1, capacity 1, doctors 1, number of capability claims capped at 5), haversine distance to the median lat/lon of facilities whose city matches; LIKE match across specialties, capability, procedure, equipment, description.
- Two axes on each card: facility documentation strength vs per-need signal (cited / listed / mentioned-only, the last flagged amber).
- README notes judges evaluated live in a 3-minute demo.
- Strong: clean separation of "how well documented" from "evidence for this need"; SQL is auditable.
- Weak: the 0-12 score measures completeness, not correctness; LIKE on raw need string.

### aisdk7/virtue-referral-copilot (DAIS; 0 stars)
Opened: README.md (first third).
- Per-query evidence points: specialties match +3, procedure text +2, equipment text +2, description +1, bed capacity documented +1, doctor count +0.5; tiers HIGH (5+), MEDIUM (2-5), LOW (under 2) with user action per tier (recommend / verify by phone / call first).
- UI: five "evidence dots" per card, explicit data-gap callouts, per-field raw text panel, map, NFHS district context, compare view, PDF export.
- LLM: Llama 3.3 70B writes a structured response (understanding, recommendation, why, confidence).
- Weak: completeness points mixed into a score that is labelled confidence in the capability.

### Vishnuja06/carepath-ai (DAIS; 0 stars)
Opened: README.md.
- Explicitly scores "information trust" (completeness, corroboration, recency, presence), not clinical quality, because the dataset has no outcomes or accreditation column.
- SQL layer: `facilities_silver`, `facility_trust`, `recommend_facilities`, `recommend_by_pincode`; blended fit/trust ranking with visible adjustable weighting.
- NFHS-5 used for district context and a Care Gap Index; Genie optional with a grounded fallback.

### sairamkannan/CareBridge-Referral-Copilot (DAIS; 0 stars)
Opened: README.md (first third).
- Streamlit Databricks App over a Lakebase synced table; deterministic evidence scoring; memory tables for search history, result snapshots, saved facilities, notes, LLM verification reviews.
- Stated safety boundaries: memory may recall workflow state but never proves capability; facility name is never strong proof of a service.

### TimothyVang/caregap-trust-planner (DAIS; 0 stars)
Opened: README.md.
- Trust score = 25 capability + 20 procedure + 20 equipment + 15 specialty + 15 description + 5 source URL - 20 contradiction - 10 vague - 10 missing-critical; labels Strong / Partial / Weak / Very weak / No usable, plus a separate Contradictory flag.
- Three workflows: plan care gaps, refer patient, review data (override with notes).
- Weak: ships a 2,032-row sample in the app because of the file limit; local build uses synthetic data.

### sachds/dais2026-virtue-healthcare (DAIS; 0 stars)
Opened: README.md.
- Offline LLM extraction of per-capability trust signals with exact evidence snippets and rationale; cardinality cross-check (a strong ICU claim with zero ICU specialists on record is flagged).
- Referral copilot as an agent mesh: plan, retrieve, scrutinise, adversarial sceptic, policy gate, compose; governance rules live in code (`policy.py`), and the UI shows what was blocked.
- Honest-notes section listing what the data cannot support.
- Weak: trust signals precomputed on a 2,500-row sample only; very broad scope (five panes) for a hackathon.

### moganakumaran/carereach (DAIS Track 2; 0 stars)
Opened: README.md (first quarter).
- Two independent signals per region (care gap, evidence confidence) plotted as a 2x2: real desert / data-poor / served.
- `ai_query` with JSON schema to extract capability flags; LLM auditor verdict per claim; badges verified / claimed-but-unverified / no-claim plus the verbatim source sentence; per-region honesty banner (% inferred geography, % high-confidence claims, % with evidence quote).
- Voice question box in Indian languages; plans saved to Lakebase.

### ankitranjan-dsai/facility-trust-desk (DAIS; 0 stars)
Opened: README.md.
- Retrieve-then-judge: deterministic extractor finds verbatim spans and negation cues (out of order, no ICU, refer); LLM judge sees only that text; any quote returned is checked to be a real substring; Supported/Likely verdict without a real citation is auto-downgraded.
- Verdicts: Supported, Likely, Conflicting, Unsupported, Weak, Not stated.
- Fallback chain ending in an offline rule engine, so the demo never dies.
- Includes Free Edition deploy steps and a 3-minute demo script.

### freeformelm/trust-first-triage-desk (DAIS Track 1; 0 stars)
Opened: DEVPOST.md (first half).
- Silver: parse JSON arrays, TRY_CAST numerics, India bbox check (lat 6-37, lon 68-98) caught 6 rows; canonical state via pincode lookup (165,627 offices deduped to 19,586 pincodes) with a `state_source` provenance enum.
- Classifier: rules (confidence 0.85 capability array, 0.80 specialty code, 0.75 procedure/equipment) then LLM fallback capped at 0.75.
- Polarity detection looks before and after the match to catch "ICU cases referred to..." patterns.
- Trust = clamp((extraction confidence - 0.20) + min(0.30, 0.08 x supports) - min(0.80, 0.30 x contradictions)); verified needs trust >= 0.75 and at least 2 supports.
- Evaluation: 20 hand-labelled (facility x capability) scenarios; reports 85% accuracy and contradiction precision/recall of 1.0.
- Strong: the only DAIS repo seen with a labelled evaluation set.

### JanUllmann/MedSatya (Hack-Nation #04 Referral Copilot; 0 stars)
Opened: README.md, backend/engine/evidence.py, ranking.py, checklist.py.
- Unit of scoring is (facility, care need): claim located in capability / specialties / description, then independent support sought in equipment / procedure / specialties; support must not be the same item that made the claim.
- Status bands: strongly supported, partially supported, claim only, not enough data, contradictory. An empty field is never treated as negative evidence.
- Ranking: band first, then within-band score = 100 x (0.50 care evidence + 0.20 freshness + 0.15 distance access + 0.10 human verification (inert hook) + 0.05 location confidence). A numeric score can never promote a facility across a band. Distance score decays linearly to 0 at 150 km.
- Output ladder: primary / backup / fallback, and the nearest facility is flagged separately because nearest is not the same as best-evidenced.
- Call-before-travel checklist generated from exactly what the record does not confirm, plus always-unknown items (operating now, bed free, can admit today).
- Data desert vs medical desert shown as distinct badges; record completeness drives a data-confidence value.
- UI: installable PWA, MapLibre, accessibility toolbar, offline banner, symptom box (symptom to care need), and a public no-login mirror for reviewers.
- Strong: the cleanest explainable ranking design found; honest handling of unknowns; reviewer-friendly access.
- Weak: keyword configs per care need (7 care needs); freshness inferred from year strings; no entity resolution.

### manojarulmurugan/hacknation-referral-copilot (Hack-Nation #04; 0 stars)
Opened: README.md, app/ranking.py, docs/provenance/stage3_findings.md, docs/readiness/stage5_findings.md.
- Stage 3 provenance audit: explodes capability/procedure/equipment into 451,110 bullets; deterministic detector for bullets that name a different city (75 km+ away, via GeoNames) or a different organisation; 4,556 bullets excluded, 1,516 facilities (15.04%) affected; rejected bullets shown in UI under "evidence we rejected".
- Stage 4: 20-capability taxonomy with tracer items (staff, equipment, diagnostics, procedures), grounded in WHO SARA and IPHS 2022.
- Stage 5: verdict per facility x capability over the full cross product: corroborated (2+ tracers from 2+ distinct source fields), claimed_only, insufficient_evidence. Documents that 25% of earlier "corroborated" pairs drew all support from a single field before the fix.
- Ranking: composite = 0.6 evidence + 0.4 proximity; proximity is a distance-decay curve; proximity halved when address and coordinates disagree; dentist/pharmacy records multiplied by 0.2 for advanced-care capabilities; search radius widens 50 / 150 / 300 / 600 km until 5 evidence-bearing results; evidence-backed results kept separate from zero-evidence proximity fillers. Three sort views: best match, nearest, most evidence.
- Query: deterministic aliases first, LLM only when parsing fails; out-of-taxonomy searches fall back to literal matching.
- Includes a GitHub Action to keep the Free Edition app alive.
- Strong: most rigorous data-quality work found; tests; honest documentation of scoring bugs found in review.
- Weak: Dash UI is plainer; heavy offline pipeline with parquet artefacts shipped in the app.

### vahekhumaryan/trust-desk (Hack-Nation #04 Trust Desk; 0 stars)
Opened: README.md, docs/challenge.md, docs/data-profile.md.
- Score 0-100 = corroboration 40 + completeness 20 + web presence 25 + geo validity 15 - suspicion penalties; every score is a range whose width reflects blank fields; labels solid / moderate / speculative.
- Self-validation without ground truth: equipment-corroboration and procedure-corroboration co-occur with odds ratios 1.8 (ICU), 3.6 (maternity), 5.1 (dialysis).
- Search: hybrid Vector Search; a "dialysis near Jaipur" query triggers distance-aware referral ranking.
- LLM audit on demand and cached in Lakebase, traced in MLflow 3; Genie space and AI/BI dashboard as native surfaces; review queue of 112 suspicious records.
- All on Free Edition; notes that Claude/GPT/Gemini endpoints are rate-limited to 0 there, so `gpt-oss-120b` is used.
- data-profile.md is a ready-made profile of the dataset (coverage table, geo quality, capability taxonomy, corroboration matrix, contradictions, web presence).

### kodeezabdullah/Veridex- (Hack-Nation #04; 0 stars)
Opened: README.md (first half).
- Geography resolution chain: state normalisation, district rename/alias, constrained fuzzy match with blocklist, centroid fallback, point-in-polygon on 2019 district boundaries; resolution 60.9% to 98.5%; unresolved rows kept and labelled.
- Evidence spans embedded with gte-large-en into a Vector Search Direct Access index (Delta Sync was about 1 row/s on Free Edition).
- Trust bands by percentile thresholds; keyword guard downgrades likely to weak and weak to none when no capability keyword is present; caps per status (no_signal 30, weak 60, likely 90).
- Agents: rule-based validator (no LLM), constrained explanation agent (Llama 3.3 70B, MLflow), gated Tavily web cross-check.

### bhavana6281/sahara (Hack-Nation #04; Free Edition; 0 stars; no README, ARCHITECTURE.md read)
- Trust score deterministic in Spark, stored in Delta; LLM only turns plain English into a validated filter object and writes cosmetic summaries; never SQL, never scores.
- Three tabs with deliberately different colour legends for trust level vs desert type; readiness queue ranked by leverage, not just low trust.

### amaan784/pramana-care-ai (Hack-Nation 5th, Challenge 03; Free Edition; 0 stars)
Opened: README.md (first third).
- Eight contradiction rules (advanced care claimed with empty equipment; 24x7 emergency claimed by clinic/dentist/pharmacy; coordinates outside India or in the wrong state; "ghost" hospital with null capacity, doctors, equipment; `farmacy` typo; fabricated awards; specialty without expected equipment; stale page). Trust = max(0, 100 - 35 x HIGH - 15 x MED - 5 x LOW).
- LangGraph planner / tools / verifier / synthesiser with hybrid Vector Search, Genie, H3 geo radius; CRAG-style loop capped at 8 iterations; Streamlit chat/map/audit.
- Notes one rule fired zero times and the agent reports that honestly.

### damsolanke/aarogya-atlas (Hack-Nation 5th, Challenge 03; 2 stars)
Opened: README.md (first third).
- 12-tool agent loop; mandatory second "critic" pass scoring each answer 0-100 with PASS/WARN/FAIL and flags, or an explicit "critic unavailable" state.
- Three-tier recommendation (best / closest payer-eligible / backup); travel modes with cost (auto, bus, 108 ambulance); drive-time rings; multilingual.
- Mostly off-Databricks (Vercel, Hugging Face Spaces, Groq, Neon); Databricks used for tracing/Genie/Vector Search.
- Weak for our purposes: LLM-generated trust score is the opposite of the deterministic pattern most Databricks-judged entries used.

### pidoxy/hacknation (Hack-Nation Feb 2026, Ghana; README claims 2nd place, Databricks challenge; 2 stars)
Opened: README.md.
- GPT-4o-mini structured extraction with per-field confidence (README says not calibrated); LangGraph supervisor routing 6 query classes over FAISS; agent trace with row-level citations; region x capability gap matrix; Leaflet map; ElevenLabs voice.
- Pipeline: 1,003 raw rows to 797 after region normalisation, dedup by unique ID with union of list fields, geocoding, anomaly flags.
- Different dataset and framing (medical deserts), not Databricks-hosted (Railway + Vercel).

---

## 3. Cross-cutting patterns

What looks strong across entries (and aligns with our brief's "show reasoning" rule):
- Score the pair (facility, service), not the facility. Separate "evidence this service exists here" from "record completeness" from "distance".
- Corroboration across independent fields (claim in capability/specialties; support in equipment/procedure) with a rule that the same sentence or same field cannot corroborate itself.
- Status bands shown before numbers; some forbid a numeric score from crossing a band.
- Citations as literal substrings of the row, labelled by field; LLM quotes verified as substrings.
- "What is missing" lists and a phone-call checklist; nearest flagged separately from best-evidenced.
- Negation / referral-out / under-construction detection near the keyword.
- Facility-type plausibility penalty (dentist or pharmacy claiming advanced care).
- Coordinate validation (bbox, city-median distance, address-vs-coordinate mismatch) and discounting distance when geo is doubtful.
- Radius widening with honest labelling instead of a hard cut-off.
- LLM kept to query parsing, translation, and optional cached second-opinion; deterministic fallback so the demo survives rate limits.
- Human override/notes/shortlist persisted (Lakebase at those events; a Delta table would be the Free Edition equivalent when Lakebase is not in play).
- Accessibility differentiators seen: Indian-language input/output, voice, WhatsApp share, directions link, emergency numbers surfaced first, PWA/offline, a11y toolbar.

What looks weak or missing across entries (opportunities):
- Almost nobody does real entity resolution of duplicate/merged facility records; the best is bullet-level contamination detection (manojarulmurugan) and registry fuzzy-matching (Jevan Rekha). `cluster_id` exists in the data but no opened README describes using it.
- Service vocabulary is nearly always a short hard-coded keyword list (6-20 services); synonyms and Hindi terms are handled only by the embedding or LLM-translation entries.
- Many scores mix completeness points into what is presented as capability confidence.
- Only one repo has a labelled evaluation set (20 cases); one has statistical self-validation (odds ratios).
- NFHS-5 is used for desert/need context, rarely tied into a referral explanation.
- Travel is straight-line everywhere except one entry that estimates modes/costs.
- Several READMEs are untouched templates, so the code quality of many entries cannot be judged from the README.

---

## 4. Not found

- No official winners list for the DAIS 2026 Apps & Agents for Good hackathon; 1st and 2nd place repos were not identified. The 3rd-place and Top-7 claims are README self-reports.
- No Hack-Nation #04 (July 2026) repo with a README prize claim.
- No GitHub repo named or described as "vf-match"; the search term returns unrelated repos. vfmatch.org/explore is only referenced as inspiration in a participant's copy of the brief.
- No public repo from the CMU Data Science Club x Databricks Datathon (Fall 2026) or reusing the phrase "find the right care" for this dataset; that phrase returned unrelated projects.
- No official Databricks or Virtue Foundation starter repo on GitHub; starter prompt/pydantic files exist only as copies inside `vahekhumaryan/trust-desk` `docs/starter/` (not opened).
- GitHub code search (file-content search) requires authentication and was not used; repos that never mention these terms in name/description/README topic were not discoverable.
- Main code was read only for: Shlok1375, aerkothalanka, JanUllmann, manojarulmurugan (ranking + findings docs), batistajldm (SQL). Other repos are characterised from README/architecture docs only.
