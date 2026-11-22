# r-free-edition: What Databricks Free Edition supports (checked 2026-11-21)

Scope and method notes.
- Everything below is about the Free Edition platform. No page I opened mentions the CMU datathon itself, so section 1 is empty; event facts come only from the brief.
- Quoting: this agent runs under a rule allowing at most one verbatim quote per response, so the task's "quote per finding" requirement could not be met. Each finding is instead a close paraphrase (exact numbers kept) of the page at the URL given, which I actually opened. The single verbatim quote is in the Apps section.
- "Official" = docs.databricks.com / databricks.com. "Community" = community.databricks.com (poster role stated). INFERENCE = my reasoning, not a page's statement.

## 1. Confirmed about the specific event (CMU DSC x Databricks Datathon, Fall 2026)

Nothing found on the web. See "Not found".

## 2. Free Edition facts from official docs

Main source (last updated Nov 16, 2026): https://docs.databricks.com/aws/en/getting-started/free-edition-limitations

| Area | What the page says |
|---|---|
| Compute model | Serverless only; custom compute configurations unsupported |
| Notebooks | Limited compute size and usage; no numbers published |
| SQL warehouse | One warehouse, capped at 2X-Small |
| Jobs | Max 5 concurrent job tasks per account |
| Lakeflow pipelines | One active pipeline per pipeline type |
| Databricks Apps | Up to 3 per account; each app auto-stops 24 hours after it was started, updated, or redeployed; can be restarted any time |
| Model Serving | Limit on number of active endpoints (number not given); no GPU endpoints; no provisioned throughput; no custom models on GPU or batch inference; certain models unavailable |
| Vector Search (renamed "AI Search") | One endpoint, one search unit; Direct Vector Access not supported |
| Lakebase | One project per account, scale-to-zero compute |
| Outbound internet | Restricted to a limited set of trusted domains (list not published) |
| Quota exceeded | Workspace compute shut down for the rest of the day, in extreme cases rest of the month; data and settings kept; resumes when limit resets |
| GPU | After LinkedIn identity verification you get limited access to AI Runtime |
| Unsupported | R and Scala, custom storage locations, online tables, CDC Lakeflow Connect connectors, clean rooms, all legacy features, Knowledge Assistant |
| Admin | One workspace + one metastore; no account console or account-level APIs; login only by email OTP, Google, or Microsoft; no SSO/SCIM |
| Reliability | No guaranteed reliability, support, or SLA; non-commercial use only |

### GPU via LinkedIn: VERIFIED, with a moving history
- Current page: LinkedIn verification (a "Verify identity" button in the workspace top bar, shown only if the account is eligible) grants limited AI Runtime access. AI Runtime is defined as Databricks' fully managed serverless GPU offering (A10s and H100s): https://docs.databricks.com/aws/en/machine-learning/ai-runtime/
- Wayback snapshots of the same page that I opened show the wording changed repeatedly:
  - Version dated Jun 30, 2026: limited serverless GPU was simply included, selectable from the notebook compute selector, subject to capacity, with no LinkedIn gate. http://web.archive.org/web/20260710075721/https://docs.databricks.com/aws/en/getting-started/free-edition-limitations
  - Version dated Jul 20, 2026: LinkedIn verification unlocked two things: limited serverless GPU compute and outbound internet access. http://web.archive.org/web/20260906132202/https://docs.databricks.com/aws/en/getting-started/free-edition-limitations
  - Version dated Sep 29, 2026: verification unlocks limited serverless GPU only; outbound internet no longer listed. http://web.archive.org/web/20261010042004/https://docs.databricks.com/aws/en/getting-started/free-edition-limitations
  - Nov 16, 2026: limited access to AI Runtime only.
- Conclusion: the GPU claim is correct as of Nov 2026. A claim that LinkedIn verification also opens outbound internet was true in the docs for roughly Jul-Sep 2026 but is no longer documented; do not rely on it.
- Blog, Jun 17, 2026: GPUs added to Free Edition subject to availability, alongside Genie Code, Lakebase, Agent Bricks, Lakeflow Designer. https://www.databricks.com/blog/whats-coming-next-free-edition
- Databricks employees, Jul 1, 2026: no published GPU quota number; fair-use throttling; capacity-constrained. https://community.databricks.com/t5/machine-learning/what-is-the-gpu-quota-limit-for-free-edition/m-p/161129

### Databricks Apps (general docs; no Free Edition override found)
- Public access is impossible. The permissions page states: "You can't make Databricks apps public." (Databricks docs, Configure permissions for a Databricks app). It adds that anonymous access and SSO bypass are unsupported. https://docs.databricks.com/aws/en/dev-tools/databricks-apps/permissions
- App users must belong to the Databricks account where the app is deployed; sharing is by CAN USE / CAN MANAGE per user or group, or an "anyone in my organization" toggle. https://docs.databricks.com/aws/en/dev-tools/databricks-apps/key-concepts
- Sizes in general docs: Medium (up to 2 vCPU, 6 GB, default), Large (up to 4 vCPU, 12 GB), XLarge (up to 12 vCPU, 48 GB, some regions). Whether Free Edition permits non-Medium: not found. https://docs.databricks.com/aws/en/dev-tools/databricks-apps/compute-size
- In-memory and local-file state is lost on restart; persist in tables, volumes, or Lakebase (key-concepts page).
- App builds download from pypi.org / files.pythonhosted.org (requirements.txt) or registry.npmjs.org (package.json). https://docs.databricks.com/aws/en/dev-tools/databricks-apps/networking

### Foundation Model APIs, ai_query, AI Functions
- No Free Edition rate or daily limits are published. The limits page says limits depend on workspace platform tier and model, and its tables are for Enterprise tier only. It tells you to read your actual quota at AI Gateway > model > Metrics > Quota limits. https://docs.databricks.com/aws/en/machine-learning/foundation-model-apis/limits
- AI Functions listed on the current page (updated Nov 20, 2026): ai_classify, ai_extract, ai_parse_document, ai_similarity, ai_gen, ai_translate, ai_summarize, ai_mask, ai_fix_grammar, ai_analyze_sentiment, ai_forecast, plus Beta ai_prep_search, ai_search, ai_enrich, ai_transcribe, ai_decide. Only stated compute restriction: not on Classic SQL warehouses; DBR 15.4 LTS+. Free Edition's warehouse is serverless, so not excluded by that rule. No page confirms or denies each function on Free Edition. https://docs.databricks.com/aws/en/large-language-models/ai-functions
- ai_query calls system.ai model services (examples on page: system.ai.gpt-5-mini, system.ai.gemini-3-flash); recommends one query over the full dataset and failOnError=false for large runs. https://docs.databricks.com/aws/en/large-language-models/ai-query
- Current model catalogue includes open models GPT OSS 120B and 20B, Gemma 3 12B, Llama 4 Maverick, embeddings GTE Large (En) and BGE Large (En), plus partner GPT / Gemini families. Which ones a Free Edition workspace can call is not stated. https://docs.databricks.com/aws/en/machine-learning/foundation-model-apis/supported-models

### Genie (spaces are now called "Genie Agents")
- Up to 50 tables/views/metric views per Genie Agent; needs a pro or serverless SQL warehouse; up to 200,000 conversations per agent. https://docs.databricks.com/aws/en/genie-agents/set-up
- To use a shared Genie Agent a person needs: a workspace entitlement (consumer access or Databricks SQL), at least SELECT on every Unity Catalog object the agent uses, and CAN VIEW/CAN RUN on the agent. Warehouse access is covered by the author's embedded compute credentials. So a judge must be a user of the workspace with data grants.

### AI/BI dashboards
- Published dashboards can use shared data permissions (publisher's credentials, the default; this is the embed_credentials=true option in the API) so viewers need no data grants, but viewers must still be registered users of the account. There is no anyone-with-the-link mode. https://docs.databricks.com/aws/en/dashboards/share/share
- Published dashboards can be downloaded as PDF (one, several, or all pages): a static fallback artifact.
- External embedding for people outside the organization exists but requires a service principal, your own server issuing scoped tokens, the CLI, and admin-approved domains; the Ask Genie button is not available in that mode. Not confirmed on Free Edition. https://docs.databricks.com/aws/en/dashboards/share/embedding/external-embed

### Geospatial, volumes, serverless quirks
- H3 functions: supported on all compute types except classic SQL warehouses (DBR 17.0+); no library install needed. https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-h3-geospatial-functions
- ST_ functions: apply to Databricks SQL and DBR 17.1+; GEOMETRY is GA, GEOGRAPHY is Public Preview. No Free Edition-specific statement. https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-st-geospatial-functions
- Volumes: any file format; UI upload capped at 5 GB per file. https://docs.databricks.com/aws/en/volumes/volume-files
- Serverless: %pip installs must be redone in each new session; PySpark UDF sandbox default memory 1 GiB; no Spark UI, no RDD API, limited DBFS (use volumes or workspace files); default time zone UTC; ANSI mode on. https://docs.databricks.com/aws/en/compute/serverless/limitations
- Notebook export formats: source file, HTML, .dbc archive, .ipynb, with outputs optionally included. https://docs.databricks.com/aws/en/notebooks/notebook-export-import

### Other official
- Free Edition overview lists building AI apps and agents, dashboards with Genie, Lakeflow pipelines, Genie Code, Lakebase as in scope. https://docs.databricks.com/aws/en/getting-started/free-edition
- Free trial vs Free Edition: Free Edition is forever free with daily usage limits; Databricks reserves the right to train on your data. https://docs.databricks.com/aws/en/getting-started/free-trial-vs-free-edition
- Blog, Oct 26, 2026: Free Edition is designed for up to five people sharing one account for a group project; quota resets daily; daily credit can be doubled up to three times per year (how is not explained). https://www.databricks.com/blog/how-teach-databricks-free-edition
- MLflow docs point newcomers to Free Edition; no Free Edition-specific tracing limits found. https://docs.databricks.com/aws/en/mlflow/
- Agent docs describe MLflow Tracing, Agent Runtime, AI Search retrieval, with no Free Edition notes. https://docs.databricks.com/aws/en/agents

## 3. Community evidence (adjacent, lower confidence)

- Premium models blocked. Databricks employee, Jul 2, 2026 (accepted answer): a PERMISSION_DENIED error saying the endpoint is disabled by a Databricks-set rate limit of 0 is a workspace trust-tier restriction; Trial and Free Edition workspaces sit in a TRIAL_VERIFIED tier where the Claude Opus family and GPT-5.x are blocked regardless of AI Gateway settings; open models such as Llama endpoints suggested. https://community.databricks.com/t5/generative-ai/foundation-models-api-blocked-quot-databricks-set-rate-limit-of/td-p/160952
- Same error on a Claude Sonnet endpoint, Aug 23, 2026; a non-employee reply says Llama 4 Maverick and other Llama models were exempt at that time. https://community.databricks.com/t5/generative-ai/databricks-hosted-foundation-model-apis-blocked-by-workspace/td-p/166270
- Daily-limit lockout during a hackathon, Nov 11-12, 2025: participant's SQL warehouse and notebooks refused to run with a message about hitting the free daily limit; a Databricks employee replied nothing could be done. https://community.databricks.com/t5/databricks-free-edition-help/hitting-free-tier-daily-limit-during-hackathon-unable-to/m-p/138688
- Reset time: Databricks employee, Jun 19, 2026: no published reset timestamp or timezone; may not align with midnight UTC; repeated hits can affect the rest of the month. https://community.databricks.com/t5/administration-architecture/you-have-hit-your-free-daily-limit/td-p/159849
- Community manager, Nov 24, 2025: daily limits exist, typically bite users in the highest usage range that day, reset next day; no numbers. https://community.databricks.com/t5/databricks-free-edition-help/is-there-any-fixed-daily-limit-on-databricks-free/td-p/140189
- Outbound allowlist: Databricks employee, Mar 7, 2026: no public list of trusted domains; workaround is download locally and upload to a workspace or Volume, or use pip-installable data packages. User tests in same thread: pypi.org resolved, wikipedia.org refused in us-east-2 but worked in eu-west-1. https://community.databricks.com/t5/databricks-free-edition-help/nookup-in-web-console/m-p/146594 ; https://community.databricks.com/t5/databricks-free-edition-help/whitelist-for-outbound-network-access/m-p/146591
- Third-party blog, Aug 12, 2026: external article sites and a brokerage API failed DNS resolution from Free Edition serverless while another host worked; author moved web fetching to an offline job and kept the App query-only; sentence-transformers embedding ran fine on serverless. https://aaboutdata.substack.com/p/what-the-docs-dont-tell-you-about
- Apps for judges: non-employee answer during the Nov 2025 hackathon: apps reach only authenticated Databricks users; add judges' emails with CAN USE or demo locally; asker noted judges' emails were not provided. https://community.databricks.com/t5/databricks-free-edition-help/not-able-to-create-pubic-link-for-databricks-web-app/td-p/138583
- App outage report, Aug 20, 2026: Free tier app showed an app-not-available page with OAuth failures despite running status; unresolved. https://community.databricks.com/t5/databricks-free-edition-help/databricks-app-access-issue-free-tier-platform/td-p/166033
- Genie throttling: Databricks employee, Apr 29, 2026: roughly 20 questions/minute via UI and about 5/minute via API (soft, rolling); Free Edition degrades Agent Mode to chat instead of shutting the workspace; a temporary backend restriction on agentic features was in force then. https://community.databricks.com/t5/generative-ai/are-there-limits-set-for-agent-mode-in-databricks-free-edition/m-p/155797
- Agent Bricks conflict: Databricks employee, Jul 2, 2026 said Agent Bricks is not available on Free Edition and Supervisor Agent saves fail with a contact-sales error; Premium/Enterprise users later reported the same gate. Conflicts with the Jun 17, 2026 blog. Current limitations page excludes only Knowledge Assistant. https://community.databricks.com/t5/generative-ai/failed-to-save-agent-supervisor-agent-is-not-available-to-access/td-p/161089
- Delta Sharing as recipient: Databricks employee, Apr 2, 2026 said a share can be catalogued on a UC-enabled Free workspace, but his own test failed for an unrelated reason. Marketplace listings not discussed. https://community.databricks.com/t5/databricks-free-edition-help/delta-share-recipient/m-p/152966
- Git folders: community member, Sep 17, 2026 reports clone/commit/push/pull working on Free Edition via the GitHub App; another user hit a resolver error on push; employee advice is a single write-capable PAT (fine-grained: Contents read and write). https://community.databricks.com/t5/administration-architecture/databricks-free-edition-github-push-fails-with-quot-resolver/m-p/168871

## 4. Adjacent: hand-off in Databricks' own Free Edition Hackathon (Nov 2025; NOT this event)

- Official rules: entrants had to give judges access via a website link, working demo, or test build; private projects had to include login credentials in testing instructions; a text description; a demo video of at most five minutes posted publicly; Stage One was pass/fail on whether links worked and the demo was accessible to judges. https://www.databricks.com/sites/default/files/2025-10/free-edition-hackathon-official-rules.docx.pdf
- Stage Two criteria, equally weighted: Technical Complexity and Execution; Creativity and Innovation; Presentation and Communication; Impact and Learning Value. Same four in the winners post (Dec 16, 2025), whose winners were a video knowledge-base workflow, a space-weather grid-risk forecaster, and an NLP recipe recommender. https://www.databricks.com/blog/announcing-winners-inaugural-databricks-free-edition-hackathon
- Databricks employee on that hackathon: deliverables were a working demo or test-build URL, a detailed description, and public video links. https://community.databricks.com/t5/databricks-free-edition-help/query-about-artifacts-to-be-submitted-for-hackathon/td-p/138248
- Teaching blog pattern: export notebooks as .ipynb and distribute through a GitHub repository.

## 5. Recommended hand-off to judges (INFERENCE; no page prescribes this for our event)

1. Assume judges cannot click into the workspace: Apps, Genie, and dashboards all require an authenticated account user.
2. Ask organizers for judges' emails today. Add them as workspace users; grant CAN USE on the app, view on the published dashboard (shared data permissions), SELECT on tables behind Genie. Test with a second non-admin login.
3. Always ship artifacts that survive a quota lockout: a demo video (5 minutes was Databricks' own norm), a GitHub repo (Git folder push or exported .ipynb/HTML with outputs), and a dashboard PDF.
4. Present live from your own logged-in browser.

## 6. Live-demo breakers, ranked

1. Daily quota. One heavy batch (LLM calls over ~10k rows, embedding sync) can shut all compute until an undocumented reset. Do heavy work Saturday, persist results to Delta tables, keep Sunday light. The whole team shares one account quota.
2. App 24-hour auto-stop. An app last deployed Saturday afternoon is stopped by Sunday 13:00. Restart or redeploy Sunday morning and re-test.
3. Model gate. Premium Claude/GPT endpoints may be hard-blocked. Check AI Gateway > Metrics per model first; keep an open-model fallback.
4. No arbitrary outbound internet from notebooks/jobs (and, by the same serverless plane, likely apps: INFERENCE). Geocoding/routing APIs, scraping, model downloads may fail DNS. Bring extra data through a Volume. PyPI installs work.
5. Judges need accounts (section 5).
6. One 2X-Small warehouse serves the app, dashboard, Genie, and ai_query simultaneously: cold starts and queuing.
7. One AI Search endpoint with one search unit; Delta Sync index only.
8. Genie rate limits and possible Agent Mode degradation.
9. Knowledge Assistant unavailable; Supervisor Agent likely gated.
10. No SLA; unexplained app outage report exists. The video is the safety net.

## Not found

- Any web page about the CMU DSC x Databricks Datathon (rubric, judge access, submission mechanics).
- Numeric Free Edition daily quota (DBUs, hours, queries) or the reset time.
- Free Edition-specific Foundation Model API rate/daily limits, or an official list of models callable on Free Edition.
- Official confirmation that each AI Function (ai_classify, ai_extract, ai_similarity, ai_gen, ai_translate, ai_parse_document) works on Free Edition.
- The trusted-domain allowlist; whether Databricks Apps share the same egress restriction (no page states it explicitly).
- Whether current LinkedIn verification still unlocks outbound internet (documented Jul-Sep 2026, absent now).
- Official Free Edition procedure and cap for adding other users (only a blog statement that an account is meant for groups of at most five).
- App compute sizes permitted on Free Edition; number of model serving endpoints allowed.
- Free Edition-specific statements on MLflow Tracing, Agent Framework / Agent Runtime deployment, ST_/H3 functions, Git folders.
- Whether the Virtue Foundation Marketplace listing installs cleanly on Free Edition (the brief says it does; no web confirmation).
