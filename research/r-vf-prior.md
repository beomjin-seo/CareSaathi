# r-vf-prior: Virtue Foundation data/AI work, the Databricks collaboration, and prior uses of this dataset

Research date: 2026-11-21. Everything below is paraphrased from pages I actually opened; locators (URL, section, file, page) are given so each point can be re-checked. Quoting policy: I am limited to one short verbatim quote in this report, so it is used once (section 2.2) and everything else is paraphrase plus exact numbers, field names and enum values.

## Bottom line

- The CMU datathon brief is a near copy of one track of an earlier Databricks event. The "Databricks Apps & Agents for Good Hackathon 2026" (Data + AI Summit, 15-16 June 2026) used the same Virtue Foundation India dataset, the same core requirements, and had four tracks. Track 3, "Referral Copilot", is our challenge almost word for word (location + care need in, evidence-attached shortlist out).
- Two published rubrics exist for this dataset. The DAIS one is unweighted (product judgment, evidence and uncertainty, technical execution, ambition). The Hack-Nation "Data Legend" one (July 2026, same dataset, written with Databricks) is weighted: Evidence and Trust 35, Product Judgment 30, Technical Execution 25, Ambition 10. No rubric is published for the CMU event, so these are the best available proxy for what Databricks judges reward.
- The DAIS winner won by not trusting the rows: it scored each (facility, specialty) claim with a transparent rule-based formula, used the LLM only to read text and pull citations, and multiplied everything by a "is this row one real place" coherence score.
- The official schema doc covers the extracted fields only. It does not define `source_types`, `source`, `cluster_id`, `recency_of_page_update`, `number_of_facts_about_the_organization` or the social-metric columns. What we know about those comes from participant repos and from profiling a public copy of the CSV.
- No official solution accelerator exists under `databricks-solutions` or `databricks-industry-solutions`. The official starter is a Developer Hub template plus the Marketplace listing.

---

## 1. Confirmed about the specific event (CMU DSC x Databricks Datathon, Fall 2026)

Nothing about this event is on the public web as far as I could find (no page, rubric, or winner list). What can be tied to it:

| Point | Source | Confidence |
|---|---|---|
| The dataset name "(DAIS 2026)" matches the Unity Catalog name used by DAIS hackathon teams: `databricks_virtue_foundation_dataset_dais_2026.virtue_foundation_dataset` with tables `facilities`, `india_post_pincode_directory`, `nfhs_5_district_health_indicators`. | https://raw.githubusercontent.com/aerkothalanka/caretrust/main/README.md and https://raw.githubusercontent.com/fulks89-hub/Databricks-2026-Hackathon-Devon/main/data/README.md | High |
| The CMU brief's five "submission must" items are the first five of the six DAIS core requirements (Free Edition, provided dataset, non-technical workflow, cite facility text, communicate uncertainty). The sixth DAIS item, persisting user actions such as notes and shortlists, is not in the CMU brief. The DAIS version also required a Databricks App specifically; CMU allows any format. | https://developers.databricks.com/hackathon/challenge (Core Requirements) | High (comparison is mine) |
| The CMU task equals DAIS Track 3 "Referral Copilot": its examples are dialysis near Jaipur and emergency surgery near Patna, and its minimum workflow is ranked candidates each showing distance, matching evidence, and missing or suspicious evidence, saveable to a shortlist. | https://developers.databricks.com/hackathon/challenge (Track 3) | High |

---

## 2. Adjacent material: earlier challenges on the same dataset

### 2.1 Databricks Apps & Agents for Good Hackathon 2026 (DAIS, 15-16 June 2026)

- Hub: https://developers.databricks.com/hackathon/apps-agents-for-good-2026 . Run with OpenAI; teams of 2-4; submission was a Git repo, project description and a three-minute demo.
- Challenge and tracks: https://developers.databricks.com/hackathon/challenge and https://dais-for-good-2026.devpost.com/
  - Track 1 Facility Trust Desk: per facility and capability, a trust signal with levels such as strong, partial, weak or suspicious, or no claim.
  - Track 2 Medical Desert Planner: trust-weighted aggregation by geography; separate real gaps from data-poor regions.
  - Track 3 Referral Copilot: see section 1.
  - Track 4 Data Readiness Desk: profiling, contradictions, review queue.
- Dataset statement on that page: 10,000 records, 51 columns; all records have name, state, city, lat/long, controlled specialties, description and source URLs; 9,996 have a postcode. Coverage: description 100%, capability 99.7%, procedure 92.5%, equipment 77.0%, numberDoctors 36.4%, capacity 25.2%, yearEstablished 47.8%. The page tells teams to treat the evidence fields as claims.
- Judging dimensions (no weights given): product judgment (clear user, thoughtful workflow and tradeoffs), evidence and uncertainty (grounded in citations, honest uncertainty), technical execution (works live, Databricks capabilities used well), ambition (beyond minimum workflow).
- Prizes on Devpost: $10,000 / $5,000 / $2,500. One judge is named on the Devpost page.
- Official starter: https://developers.databricks.com/templates/hackathon-app-with-synced-dataset (Databricks App on Lakebase with the dataset synced from Unity Catalog). Setup checklist: https://developers.databricks.com/hackathon/quick-start-checklist . Marketplace listing id `19326b3d-db63-4627-abc0-cf4e8131a305` (login required; the public details URL returned a not-found page for me).

### 2.2 Hack-Nation 6th Global AI Hackathon, Challenge 04 "Data Legend" (same India dataset)

Source: challenge brief PDF stored in a participant repo, https://raw.githubusercontent.com/vahekhumaryan/trust-desk/main/task.docx.pdf (5 pages).

- Same four tracks and same coverage table as DAIS. Says Virtue Foundation and Databricks for Good built the "reasoning layer" and teams ship the product layer.
- Weighted evaluation (page 5): Evidence and Trust 35%, Product Judgment 30%, Technical Execution 25%, Ambition 10%.
  - Evidence and Trust asks for row-level citations, strong vs weak evidence, and data deserts vs medical deserts. The one verbatim quote in this report, from that criterion: "Since there is no ground truth, we value apps that double-check their own work." (Hack-Nation x Databricks, Data Legend brief, p.5)
  - Product Judgment asks whether the app solves a real decision problem for a non-technical NGO planner instead of putting technology behind a chat box.
- Example of the expected trust logic (page 2): an advanced-surgery claim with no anesthesiologist listed should rank below one corroborated across three fields.
- Stretch goals (page 3): sentence-level citations with the reasoning step shown (MLflow 3 tracing suggested); a validator step against medical standards or internal consistency rules; a PIN-code map that separates "no hospitals here" from "we don't know what's here"; solving any open question the Databricks for Good team marks could-have or won't-have.
- Open research areas (page 4): confidence scoring without ground truth (prediction intervals suggested); claims vs evidence; the data-desert problem given 25% capacity and 36% doctor-count coverage.
- Suggested stack (page 4): Databricks Apps, Agent Bricks, Genie, MLflow 3, Mosaic AI Vector Search, Lakebase.

### 2.3 Hack-Nation Feb 7-8 2026, "Bridging Medical Deserts" (Ghana dataset, same schema family)

Source: https://raw.githubusercontent.com/pidoxy/hacknation/main/1.%20Databricks_%20Bridging%20Medical%20Deserts%20-%20Building%20Intelligent%20Document%20Parsing%20Agents%20for%20the%20Virtue%20Foundation.pdf

- Goal: an agent that extracts and verifies facility capabilities from free text, finds gaps, and flags incomplete or suspicious claims.
- Evaluation: Technical Accuracy 35% (must-have queries and anomaly detection), IDP Innovation 30%, Social Impact 25%, User Experience 10% (intuitive for non-technical NGO planners).
- Stretch: row-level citations, with a bonus for citations per agent step; a map; alignment with the real VF agent's open questions.
- MVP item 3 asks for a planning system usable across experience levels and age groups.
- It links three resources that also apply to the India data: the Ghana CSV, the schema documentation, and the prompts and pydantic models used to create the data.

---

## 3. Schema documentation (official) and what it does not cover

### 3.1 Official schema doc

Opened as text export: https://docs.google.com/document/d/1UDkH0WLmm3ppE3OpzSuZQC9_7w3HO1PupDLFVqzS_2g/export?format=txt (same content as `Virtue Foundation Scheme Documentation.pdf` in https://github.com/pidoxy/hacknation).

| Field | Definition (paraphrased) |
|---|---|
| `procedure` (list) | Specific clinical services performed: interventions, diagnostic procedures, screenings. Each item a declarative statement, with quantities when available. |
| `equipment` (list) | Physical devices and infrastructure: imaging machines, OR technology, monitors, lab analyzers, utilities such as oxygen plants and backup power. Model names when available. |
| `capability` (list) | Level and type of care the facility can deliver: trauma or emergency levels, units (ICU, NICU, burn), clinical programs, diagnostic capabilities, accreditations, inpatient or outpatient, staffing levels, patient capacity. Excludes addresses, contact info, hours, pricing. |
| `specialties` (list) | Exact case-sensitive camelCase names from a specialty hierarchy; most specific appropriate one; only when clearly mentioned or strongly implied. |
| `facilityTypeId` | hospital, pharmacy, doctor, clinic, dentist. |
| `operatorTypeId` | public, private. |
| `affiliationTypeIds` | faith-tradition, philanthropy-legacy, community, academic, government. |
| `description` | Short paragraph on services and/or history. |
| `numberDoctors`, `capacity`, `area` | Doctor count; inpatient bed capacity; floor area in square metres. |
| `officialWebsite` | Domain only, must be the organisation's own site. `websites` is the broader list of associated sites. |
| address fields | `address_line1-3` street only; city, state/region, postcode, country and ISO alpha-2 code separate. Country is to be inferred from URL domain or phone if not stated. |

Not defined anywhere in the doc: `source_types`, `source_ids`, `source`, `source_content_id`, `content_table_id`, `cluster_id`, `unique_id`, `source_urls`, `recency_of_page_update`, `number_of_facts_about_the_organization`, `distinct_social_media_presence_count`, `affiliated_staff_presence`, `custom_logo_presence`, `post_metrics_*`, `engagement_metrics_*`, `coordinates`.

### 3.2 The extraction prompts (how the claim fields were generated)

Opened: https://raw.githubusercontent.com/pidoxy/hacknation/main/prompts_and_pydantic_models/free_form.py , `medical_specialties.py`, `facility_and_ngo_fields.py`, `organization_extraction.py` (same folder).

- `free_form.py`: one prompt per named organisation extracts `procedure`, `equipment`, `capability` from page text and images. It instructs the model to keep only facts supported by the content, avoid generic statements, and keep facts specific to the target organisation. The pydantic description for `equipment` says not to list bed counts, while the prompt's own example output includes a bed-count item under equipment, so the categories overlap in practice.
- `medical_specialties.py`: specialties are restricted to levels 0-1 of a hierarchy and **the facility name alone can assign a specialty**: a name containing Hospital or Medical Centre with no specialty term maps to `internalMedicine`; Clinic maps to `familyMedicine`; Trauma maps to `criticalCareMedicine`; Kidney/Nephrology to `nephrology`; generic oncology to `medicalOncology`; Maternity/Obstetric to `gynecologyAndObstetrics`; generic surgery to `generalSurgery`. Consequence for us: a `specialties` entry is weak evidence on its own, and `internalMedicine`/`familyMedicine` are close to defaults.
- `facility_and_ngo_fields.py`: the structured-field prompt is conservative by design: include a fact only if the evidence names the organisation or points to it unambiguously, ignore other facilities on the same page, do not infer. This tells us cross-facility mixing on multi-facility pages (directories, empanelment lists) was a known risk at extraction time.
- `organization_extraction.py`: defines a facility as a physical, currently operating site delivering in-person diagnosis or treatment; government agencies are excluded as organisations.

### 3.3 Provenance columns: what participants and the data itself show (not official)

Profile of a public copy of the CSV (https://raw.githubusercontent.com/sundarep-ai/databricks-for-good-hackathon/main/pipeline/data/facilities.csv, 10,088 rows x 51 columns; my own count):

- `source`: the string `kie` in 9,970 rows, blank in 117, junk in 1. It is effectively a constant, so it carries no ranking signal.
- `source_types`: a list with one entry per contributing source record. Rows containing each value: `overture` 9,165; `dynamic` 6,942; `constant` 3,393; `mongo_facility` 1,124; `mongo_ngo` 228.
- `cluster_id`: 9,959 distinct non-blank values, 118 blank rows, a handful of ids appearing twice.
- `recency_of_page_update`: the literal string `null` in 6,426 rows; the most common real values are 2025-12-18 to 2025-12-21.
- `number_of_facts_about_the_organization`: `null` in 7,214 rows.
- `source_urls`: 3 to 30+ URLs per row; about 2,000 rows have 30 or more.
- `organization_type`, `facilityTypeId`, `operatorTypeId` each contain a few dozen column-shifted junk values (coordinates, GeoJSON, URL arrays, free text).
- `specialties`: 2,933 distinct strings; top are internalMedicine (6,847 rows), familyMedicine (5,178), gynecologyAndObstetrics (4,497), dentistry (4,192); nephrology 2,156; emergencyMedicine 2,085; criticalCareMedicine 1,677; neonatologyPerinatalMedicine 1,255.

Interpretations by participants (treat as hypotheses):

- DAIS winner's config ranks source types by authority: `mongo_facility`/`mongo_ngo` 1.0, `constant` 0.8, `dynamic` 0.5, `overture` 0.3, with a code comment reading curated > constant > scraped > map-tile. https://raw.githubusercontent.com/sundarep-ai/databricks-for-good-hackathon/main/pipeline/src/config.py
- A Hack-Nation participant's data profile describes `cluster_id` as the entity-resolution key, with 11 size-2 clusters that are exact duplicate rows, safe to dedupe; it is not a chain or branch grouping. https://raw.githubusercontent.com/vahekhumaryan/trust-desk/main/docs/data-profile.md (section 7)
- The DAIS session slides use "KIE" as the name of the LLM extraction stage (slide on decomposed extraction and content hashing) and show Overture and Bright Data as the two data sources feeding it. https://microsites.databricks.com/sites/default/files/dais/2026/D26B3239.pdf . The acronym is not expanded there; "key information extraction" is my reading. The same deck has a data-quality slide about what makes a record valid for upsert to Mongo, which fits `mongo_*` meaning records already in VF's curated MongoDB store (the 2024 blog describes a Databricks-MongoDB sync).

---

## 4. How the dataset is built, per Databricks and Virtue Foundation

### 4.1 Databricks blog, May 2026

https://www.databricks.com/blog/databricks-good-and-virtue-foundation-partnering-connect-medical-volunteers-critical-health

- The dataset is called the Foundational Data Refresh (FDR): facilities and nonprofits in 72 low and lower-middle income countries, the core of VF Match.
- Sources: Overture Maps for facility locations; Bright Data web scraping.
- Extraction: OpenAI GPT models over more than 25 million web pages, split into steps (medical relevance, organisation type, then specialties, equipment, procedures), with per-record state so reruns skip finished LLM calls.
- Entity resolution: Splink probabilistic record linkage, weighted comparisons on fields such as phone number and street address, producing one unified key per facility. Stated problem: the same facility appears with name variants, inconsistent addresses, or missing contacts.
- VF Agent prototype: LangGraph multi-agent. A Medical Specialty Extractor normalises user language to standard terms; a supervisor routes to an AI Search (vector search) agent for facility discovery or a Genie agent for analytical questions.
- The blog reports no extraction accuracy or hallucination figures.

### 4.2 DAIS 2026 session

Session page: https://www.databricks.com/dataaisummit/session/building-ai-matters-powering-global-healthcare-virtue-foundation . Slides: https://microsites.databricks.com/sites/default/files/dais/2026/D26B3239.pdf (44 pages; speakers from Virtue Foundation and Databricks).

- Scale on the slides: 72 countries, 100+ medical specialties, 400k+ facilities and NGOs. The slides say 5M+ web pages crawled, which differs from the blog's 25 million.
- Two decision use cases are named: where to build the next surgical centre, and how best to deploy tricycle ambulances.
- Consumption layer is VF Match and the VF Agent. VF Match is described as a marketplace for volunteers that also lets users explore medical deserts.
- Three production challenges: crawl volume, single-shot extraction being expensive and fragile (solved by staged extraction), and skewed partitions in probabilistic matching.

### 4.3 Databricks blog, December 2024 (first iteration)

https://www.databricks.com/blog/elevating-global-health-databricks-and-virtue-foundation

- Llama 3.1 70B extracted hospital details from website text. Entity matching used exact country, fuzzy region or city, and embedding similarity on names, with a tunable distance threshold deciding when a human reviews a merge.
- Named users: doctors and academic researchers. Access via vfmatch.org and a RAG chatbot.

### 4.4 VF Agent question reference (what Databricks for Good is trying to answer)

https://raw.githubusercontent.com/pidoxy/hacknation/main/Virtue%20Foundation%20Agent%20Questions%20-%20Hack%20Nation.pdf (11 pages, 59 questions, MoSCoW priorities)

- Must-have: counts of hospitals by specialty or procedure in a region; what services a named facility offers; whether clinics in an area do a service; how many hospitals treating a condition are within X km of a place; geographic cold spots for a critical procedure by km or travel time; procedures that depend on only one or two facilities in a region; unrealistic procedure counts for facility size.
- Should-have: facilities that claim a subspecialty but lack the basic equipment for it; share of facilities whose procedure claim comes with the minimum required equipment (example given: cataract surgery and an operating microscope); claims corroborated by multiple independent websites.
- Could-have: visiting or camp-based services vs permanent ones; language suggesting the facility refers patients onward instead of performing the procedure; strong clinical claims with weak operational signals.
- Won't-have (too hard for them): how fast claims go stale and where to re-scrape; corroboration across website text, images and social pages.

---

## 5. Known failure modes of the dataset

No peer-reviewed paper or arXiv preprint from Virtue Foundation on the extraction pipeline or its error rates was found. The evidence is from participants who worked with the data:

| Failure mode | Detail | Source |
|---|---|---|
| Merged entities (over-clustering) | The DAIS winners say that after exploring the data and talking with the person who assembled it, the most striking problem was single records combining several hospitals with contradictory locations and borrowed capabilities. Their pipeline flags 2,249 of 10,077 facilities as likely merged (coherence below 0.5) and 13.4% of claims as disputed. | https://cavallotechnologies.ca/news/fix-the-foundation-how-we-won-the-databricks-hackathon-2026 ; https://raw.githubusercontent.com/sundarep-ai/databricks-for-good-hackathon/main/hackathon_task.md (sections 1, 8) |
| Unsupported claims | About 40% of (facility, specialty) claims had no supporting text beyond the list entry. A separate participant found roughly half of ICU, NICU, oncology, emergency and maternity capability claims had no corroboration in equipment, procedure or description. | hackathon_task.md section 8; https://raw.githubusercontent.com/vahekhumaryan/trust-desk/main/docs/data-profile.md section 4 |
| Off-topic sources | Real-estate, insurance, travel and marketplace domains feed some records (2,685 issue rows). | hackathon_task.md section 9 |
| Column-shifted rows | 88 rows where country, country code or organisation type are wrong because columns shifted; another team flags about 145 with a looser heuristic. `unique_id` is not a valid UUID in 88 rows. | hackathon_task.md section 4; https://raw.githubusercontent.com/fulks89-hub/Databricks-2026-Hackathon-Devon/main/data/CLEANING_REPORT.md |
| Duplicates | 11 byte-identical duplicate rows (10,088 to 10,077). | CLEANING_REPORT.md |
| Null sentinels | The literal string `null` is the main placeholder (for example 6,342 `numberDoctors` values), plus empty strings and `[]`. | https://raw.githubusercontent.com/fulks89-hub/Databricks-2026-Hackathon-Devon/main/data/README.md |
| Bad numerics | `capacity` up to 200,000 and `numberDoctors` up to 15,000; `yearEstablished` values such as 0, 1, 4. | CLEANING_REPORT.md; data-profile.md section 9 |
| Geography | 118 rows without coordinates and 6 outside India; `address_stateOrRegion` has 253 distinct messy values and sometimes holds a district; deriving state from the PIN directory gives about 96% coverage. | data-profile.md section 2; CLEANING_REPORT.md |
| LLM filler | 237 equipment rows and 129 procedure rows contain filler saying nothing specific was listed; empty-string array items exist. | data-profile.md section 10 |
| `websites` is not the facility's site | It is a list of source URLs (journals, travel sites, government portals); only `officialWebsite` is the facility's own domain, and 43 of those are directories or social pages. | data-profile.md section 6 |
| Array caps | Procedure arrays appear capped at 50 items; capability averages about 23 items per row with heavy near-duplicate phrasing. | data-profile.md sections 3, 5 |
| Join traps | NFHS district and state names have trailing spaces; the PIN table has one row per post office so a PIN is not unique; about 95.5% of clean facility postcodes match the PIN table. | data-profile.md section 8 |
| Soft signals that misfire | "Surgery claim with no anaesthesia mention" hits 73% of surgery-claiming rows including well-known large hospitals, so it only works as a weak signal. | data-profile.md section 5 |

---

## 6. What won at DAIS (same dataset, Databricks judges)

Gallery: https://dais-for-good-2026.devpost.com/project-gallery (122 submissions; three marked Winner).

1. **1st: Data Readiness Desk** (Track 4). https://devpost.com/software/project-cavallo ; repo https://github.com/sundarep-ai/databricks-for-good-hackathon ; write-up https://cavallotechnologies.ca/news/fix-the-foundation-how-we-won-the-databricks-hackathon-2026
   - Unit of trust is the (facility, specialty) claim: about 118k claims from 10k rows.
   - trust = coherence x (0.45 Evidence + 0.15 Authority + 0.15 Independent corroboration + 0.15 Spatial consistency + 0.10 Recency). All constants live in one config file.
   - Evidence tiers: 0 list-only (0.10), 1 asserted in prose (0.40), 2 named procedure (0.70), 3 named equipment and procedure (0.95). A tier-0 claim is capped at the "Claimed" badge and cannot reach "Likely".
   - Coherence combines agreement of state from coordinates, PIN and address; distance between coordinates and PIN centroid; number of distinct source domains; and the share of claims whose evidence is about this facility.
   - The LLM (Databricks `ai_query`) only assigns the tier, returns verbatim spans, and says whether the text is about the same facility. The verdict is rule-based. The team states they rejected letting a model judge claims outright because an unexplained verdict is not actionable.
   - A separate confidence band (high/med/low) is shown next to trust.
   - Stack: Unity Catalog, `ai_query`, Genie (SQL shown beside answers), Lakebase, Databricks App (FastAPI + React), OpenAI agent with web search.
2. **2nd: Asclepius** (all four tracks). https://devpost.com/software/asclepius-mdbkwl ; repo https://github.com/fulks89-hub/Databricks-2026-Hackathon-Devon
   - Referral Copilot with a plain-language assistant (English and Hindi) behind a literal-substring citation guard: every quote is re-anchored to the source text and anything that cannot be grounded is refused.
   - Desert planner flags 189 "unknown-supply" districts separately so a join gap is not scored as scarcity.
   - Their grounding spec attaches an uncertainty chip (0-100 with band and component breakdown) to every AI answer and returns an insufficient-evidence result when no literal span exists. https://raw.githubusercontent.com/fulks89-hub/Databricks-2026-Hackathon-Devon/main/docs/AI_GROUNDING.md
   - Free Edition limits they hit: 3-app cap, 24h auto-stop, one Vector Search endpoint, daily compute limits, and the SQL warehouse being disabled mid-event.
3. **3rd: CareSignal** (search + geo + trust review + chat). https://devpost.com/software/caresignal-c1o837 ; repo https://github.com/aerkothalanka/caretrust
   - Positions itself as decision support for families, not automated decisions.
   - Scoring uses per-service term dictionaries (dialysis, ICU, maternity, emergency/trauma, oncology, cardiac surgery, eye care) and a visible breakdown: specialties match 1.5, procedure match 1.5, equipment 1.0, capability 1.0, description 1.0, source-URL relevance 1.0, contactability 0.75, location completeness 0.5, human verification 1.5, freshness 0.25. https://raw.githubusercontent.com/aerkothalanka/caretrust/main/backend/scoring.py

A non-winning participant account (Rearc) confirms the event constraints and that the Virtue Foundation speaker framed the work around healthcare deserts: https://rearc.io/blog/dais-2026-hackathon

---

## 7. End users and decisions, as stated by the dataset owner

- Virtue Foundation's Actionable Data Initiative page names the audience as people and institutions that deliver healthcare: volunteers, nonprofits, governments, the private sector. VF Match is a map-based matching platform with filters for medical deserts, hospital accessibility and physician density. https://virtuefoundation.org/research-analytics/
- DataRobot customer story: medical deserts are identified by specialty; decisions include where to site new hospitals or surgical centres and where to place volunteer clinicians; visualisations are used by health ministers and NGOs. https://www.datarobot.com/customers/virtue-foundation/
- CARTO post on VFMatch: defines a medical desert as a community lacking access to medical necessities; maps overlay facilities with population density and travel time to the nearest facility. https://carto.com/blog/vfmatch-org-the-first-mapping-and-matching-global-health-platform/
- Databricks customer page: VF uses the platform to refresh and map global health data and match hospital and NGO resources with specialists. https://www.databricks.com/customers/virtue-foundation
- The hackathon briefs written with Databricks name the user as a non-technical healthcare planner, NGO coordinator or analyst.

---

## 8. Solution accelerators and repos

- Official: none found. GitHub repository search returned zero results for "virtue" in both `databricks-solutions` and `databricks-industry-solutions`. The only official starter is the Developer Hub template in section 2.1.
- Community repos that use VF data (all unofficial):
  - India dataset: `sundarep-ai/databricks-for-good-hackathon`, `fulks89-hub/Databricks-2026-Hackathon-Devon`, `aerkothalanka/caretrust`, `vahekhumaryan/trust-desk`.
  - Ghana dataset: `pidoxy/hacknation` (holds the schema doc, prompts, brief and question list), `FarahBaraket-03/MedBridgeAI`, `sudiptabag2004/CareGap-Intelligence-Agent`, `DeePZeeRa/databricks_accenture_hackathon_virtue_foundationtrack`, `OmSinha07/VirtueAudit-AI-Automated-Medical-Infrastructure-Verification-Risk-Assessment`, `deepayanA320/databricks_hackerthon_virtue_foundation`.
  - Listed by https://api.github.com/search/repositories?q=virtue+foundation+databricks

---

## 9. Implications for our build

1. Build to the two published rubrics: citations and honest uncertainty first, a clear non-technical user second, reliability on Free Edition third.
2. Rank on claim-level evidence, not on the `specialties` list. A specialty can come from the facility's name alone, so require backing in `procedure`, `equipment`, `capability` or `description` and show the exact text.
3. Gate every recommendation on "is this one real place": compare the state implied by the PIN, the coordinates and the address, and the coordinate-to-PIN distance. Say so in the explanation when they disagree.
4. Keep the scoring formula rule-based and visible; use an LLM only to read text and return spans. Both top DAIS teams did this and the winner said so explicitly.
5. Show what is missing or suspicious next to what matches, per the Track 3 minimum workflow.
6. Separate "no evidence of the service" from "no data". Sparse `capacity` and `numberDoctors` should never lower a facility's rank as if they were negatives.
7. Do not use `source` (constant) or `websites` (source URLs) as signals. `source_types`, distinct source domains, `recency_of_page_update` and `officialWebsite` are usable but undocumented, so label them as heuristics.
8. Cheap differentiators the Databricks for Good team itself lists as unsolved: detect referral or visiting-camp language (the facility arranges or hosts the service but does not perform it permanently), and check that a claimed service comes with its minimum equipment (dialysis machines for dialysis, operating theatre and anaesthesia for a C-section, ventilators for ICU).
9. Persisting a shortlist or notes is not required by the CMU brief but was a core requirement in both earlier versions, so judges from Databricks may look for it.

---

## 10. Not found

- Any public page, rubric or results for the CMU datathon itself.
- A public (no-login) Marketplace listing page for the dataset.
- Official definitions of `source_types` values, `source = kie`, `cluster_id`, `recency_of_page_update`, `number_of_facts_about_the_organization`, or the social-metric columns.
- An official expansion of "KIE".
- A peer-reviewed paper or preprint by Virtue Foundation or Databricks on the extraction method, its accuracy, or hallucination rates.
- An official Databricks solution accelerator or notebook for this dataset.
- The phrase "Actionable Data Initiative" in Databricks material (it is Virtue Foundation's own term); the May 2026 Databricks blog does not use the term "medical deserts" (the session slides and VF pages do).
- Winners of the Hack-Nation 6th "Data Legend" challenge.
- Contents of the YouTube videos linked from the Databricks blog and of the DAIS official-rules PDF (not opened); a participant blog on noop.app could not be loaded.
