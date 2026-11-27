*Full problem statement and build spec, from an empty repo to a deployed
project. Originally a Hiver SDE intern take-home; now a resume project.
Paste this whole document into a new chat as the brief. Owner: Vijay
Samuel (github.com/samuel-hacks).*

# 0. How to use this document (read first)

This is the complete brief for building the AI Customer Support Agent
from scratch. It began as the Hiver SDE intern take-home in September
2026; I am now rebuilding it properly as a portfolio project, starting
from an empty repo and keeping all the original design choices in
Section 1.1. The assistant working on it must:

-   Start from an empty repo using the layout in Section 9.3. Set up the
    project skeleton, dependencies and tests before any modelling.

-   Keep the choices in Section 1.1 fixed. If something in them turns
    out not to work, explain why and propose an alternative before
    changing it.

-   Within the build, extend what already works from earlier milestones;
    do not rewrite or duplicate working modules.

-   Follow the milestone order in Section 11.

-   Never claim something is done without evidence: test output, metrics
    file or screenshot.

-   Keep costs at zero where possible: local models (Ollama) or
    free-tier APIs.

My machine: MacBook Air M5, 16 GB RAM, macOS, VS Code. Fine-tuning
DistilBERT/BERTweet should run on Apple MPS or a free Colab/Kaggle GPU.
Local LLMs should be about 3B to 8B parameters, quantized.

# 1. Problem statement

Brand support teams on Twitter/X receive a constant stream of customer
tweets: login problems, billing questions, app bugs, feature requests,
complaints and praise. Agents spend much of their time reading each
tweet, deciding what it is about, finding how similar cases were
answered before, and typing a reply. Many tweets are routine and could
be answered safely with a well-grounded template; others need a human
because they involve account-specific action, anger, or risk.

Build an **AI support agent for one brand, SpotifyCares**, using real
historical data from the Kaggle \"Customer Support on Twitter\" dataset.
For each incoming customer tweet the agent must:

1.  **Classify intent** into a fixed taxonomy.

2.  **Draft a grounded reply** based only on how SpotifyCares actually
    replied to similar tweets in the past (no invented policies, links
    or promises).

3.  **Decide whether to auto-handle or escalate** to a human, with a
    stated reason.

The project must also include a **golden evaluation set**, an
**evaluation harness**, a **written report**, and a **decision log**, as
the original take-home required.

## 1.1 Constraints from the original brief and my own choices

-   Single brand: **SpotifyCares** (chosen and fixed).

-   Main classifiers: fine-tuned **DistilBERT** and **BERTweet**,
    compared against each other at the end.

-   Baselines: **TF-IDF + Logistic Regression**, **TF-IDF + Linear
    SVM**, **sentence-embedding centroid / kNN**, and **embeddings +
    Logistic Regression / kNN**.

-   Demo: **not Streamlit**. A **Flask REST API** backend with a
    **separate plain HTML/CSS/JavaScript frontend** that is easy to
    deploy.

# 2. Resume claims this project must make true

This entry is already on my resume (dated Sep 2026 to Nov 2026). Tech
line: Python, Flask, Hugging Face, scikit-learn, JavaScript.

  -----------------------------------------------------------------------
  **Resume claim**                 **What must exist to back it**
  -------------------------------- --------------------------------------
  SpotifyCares support agent that  Trained intent classifier served by
  classifies intent                the API, with a documented taxonomy.

  drafts grounded replies          Retrieval over historical SpotifyCares
                                   replies + LLM draft constrained to
                                   retrieved examples, with sources
                                   returned.

  and auto-handles or escalates    Routing policy with confidence
  tickets                          thresholds and rules; every decision
                                   has a reason code.

  Fine-tuned DistilBERT and        Training scripts, saved checkpoints,
  BERTweet over TF-IDF baselines   comparison table including all
                                   baselines.

  with a golden eval harness       Hand-labelled golden set + one command
                                   that produces a metrics report.

  Flask REST API                   Flask app with documented JSON
                                   endpoints, tests, and a JS frontend
                                   calling it.
  -----------------------------------------------------------------------

Once evaluation is done I want to add real numbers to the resume, e.g.
\"BERTweet reached \_\_ macro-F1 vs \_\_ for TF-IDF + SVM; auto-handled
\_\_% of tickets at \_\_% precision.\" Make sure the harness produces
exactly these numbers.

# 3. Data

## 3.1 Source

Kaggle dataset \"Customer Support on Twitter\" (file twcs.csv). Columns:
tweet_id, author_id, inbound (True for customer tweets), created_at,
text, response_tweet_id, in_response_to_tweet_id. Brand accounts appear
by handle in author_id (here SpotifyCares).

## 3.2 Preparation pipeline (data/prepare.py)

1.  Load twcs.csv with explicit dtypes (tweet IDs as strings).

2.  Find every SpotifyCares reply and walk in_response_to_tweet_id back
    to the customer tweet it answers. Build pairs: (customer_tweet,
    brand_reply, conversation_id, created_at).

3.  Keep the first customer tweet of each conversation as the \"ticket\"
    text; keep the full thread for context if useful.

4.  Clean text: strip the brand \@mention, normalise URLs to \<URL\> and
    user mentions to \@user (BERTweet expects this style), keep emojis,
    remove exact duplicates.

5.  Remove brand reply signatures (agent initials like \"\^JD\") from
    replies before indexing, but keep them in a separate field.

6.  Split by **time** (e.g. oldest 80% train, next 10% validation,
    newest 10% test) to avoid leakage between near-duplicate tweets.
    Save to data/processed/\*.parquet.

7.  Write a short data card: number of pairs, date range, average
    length, language mix, examples.

## 3.3 Intent taxonomy

Define 8 to 12 intents from a quick review of the data. A starting
proposal (adjust after looking at real tweets, and record the final list
in DECISIONS.md):

  -----------------------------------------------------------------------
  **Intent**            **Examples**
  --------------------- -------------------------------------------------
  account_login         Cannot log in, password reset, account hacked,
                        email change

  billing_payment       Charged twice, refund, payment failed, price
                        change

  subscription_plan     Premium, Family, Student, Duo plans,
                        upgrade/downgrade, cancel

  playback_app_bug      Songs skip, app crashes, no sound, app not
                        loading

  device_connect        Spotify Connect, smart speakers, car, TV, console

  offline_downloads     Downloads missing, offline mode, storage

  library_playlists     Lost playlists, liked songs, recommendations

  podcasts_content      Missing song/podcast, region availability, lyrics

  feature_request       Please add X

  praise_other          Thanks, compliments, chit-chat, unrelated
  -----------------------------------------------------------------------

## 3.4 Labelling strategy

-   **Silver labels for training**: label the training split with a mix
    of keyword rules and an LLM (local or free tier) using a strict
    prompt with the taxonomy and examples. Store label + model
    confidence.

-   **Gold labels for evaluation**: I hand-label (or hand-verify) a
    golden set (Section 7). The golden set is never used for training or
    threshold tuning.

-   Report agreement between silver labels and gold labels on the golden
    set; this tells us how noisy the training labels are.

# 4. Intent classification

## 4.1 Baselines (scikit-learn)

-   TF-IDF (word 1-2 grams + char 3-5 grams) + Logistic Regression.

-   TF-IDF + Linear SVM (calibrated with CalibratedClassifierCV so it
    gives probabilities).

-   Sentence embeddings (e.g. all-MiniLM-L6-v2 or bge-small-en-v1.5) +
    nearest-centroid.

-   Embeddings + kNN, and embeddings + Logistic Regression.

## 4.2 Fine-tuned transformers (Hugging Face)

-   distilbert-base-uncased and vinai/bertweet-base (BERTweet needs its
    own normaliser: \@USER, HTTPURL, emoji handling).

-   Hugging Face Trainer, max length 128, 3 to 5 epochs, early stopping
    on validation macro-F1, class weights if imbalanced.

-   Run each with 3 random seeds and report mean and standard deviation.

-   Save best checkpoints to models/, plus a label map and config.
    Export the final model for CPU inference.

## 4.3 Metrics

-   Macro-F1 (primary), accuracy, per-class precision/recall/F1,
    confusion matrix.

-   Calibration (reliability plot or expected calibration error),
    because routing depends on confidence.

-   CPU inference latency per tweet and model size on disk.

-   One comparison table with all baselines and both transformers, on
    the same frozen test split and on the golden set.

# 5. Grounded reply drafting

## 5.1 Retrieval index

-   Index historical SpotifyCares replies from the **train split only**,
    each stored with the customer tweet it answered, its intent and
    date.

-   Embed the customer tweet side (that is what new tickets look like);
    search by embedding similarity, filtered or boosted by predicted
    intent.

-   Storage: FAISS or a simple NumPy index is enough; keep it in the
    repo build step, not a hosted DB.

## 5.2 Drafting

1.  Retrieve the top 5 most similar past (customer tweet, SpotifyCares
    reply) pairs.

2.  Prompt an LLM (local via Ollama, or a free-tier hosted model;
    provider chosen by env var) to write a reply in SpotifyCares tone,
    under 280 characters, using only facts and steps that appear in the
    retrieved replies.

3.  The LLM must return structured output: {reply, used_source_ids,
    needs_dm: bool, confidence}.

4.  Post-checks: length limit, no URLs or links that are not in the
    sources, no promises of refunds or account changes, no personal data
    requests in public. Failing checks either triggers one rewrite or
    forces escalation.

5.  Fallback when the LLM is unavailable: return the single best
    retrieved reply, lightly templated, and mark it as a template.

## 5.3 Groundedness score

Compute a simple groundedness score for each draft: share of draft
sentences that are supported by at least one retrieved reply (embedding
similarity above a threshold, or an LLM judge in the eval harness only).
Low groundedness forces escalation.

# 6. Auto-handle vs escalate

Routing is a transparent policy, not a black box. Every decision returns
a route and one or more reason codes.

  -----------------------------------------------------------------------
  **Escalate when**                               **Reason code**
  ----------------------------------------------- -----------------------
  Classifier confidence below a tuned threshold   LOW_CONFIDENCE

  Intent is in the always-human list              SENSITIVE_INTENT
  (billing_payment, account_login when            
  hacked/locked)                                  

  Strong negative sentiment, anger, threats to    ANGRY_OR_RISKY
  cancel, or legal words                          

  Tweet contains or asks for personal data        PII
  (email, card, phone)                            

  Draft groundedness below threshold or           UNGROUNDED_DRAFT
  post-checks failed                              

  Draft says a DM or account action is needed     NEEDS_ACCOUNT_ACTION
  -----------------------------------------------------------------------

Otherwise the ticket is **auto-handled** with the draft. Tune the
confidence threshold on the validation split to hit a target precision
for auto-handled tickets (for example at least 90% of auto-handled
tickets should be ones a human would also auto-handle), and report the
coverage (share auto-handled) at that precision. Plot the precision vs
coverage curve.

# 7. Golden evaluation set

-   Size: 300 to 400 tickets sampled from the **test** time window,
    stratified across intents (with a natural-distribution subset too).

-   For each ticket store: ticket_id, text, gold_intent, gold_route
    (auto/escalate), gold_reason (optional), reference_reply (the real
    SpotifyCares reply), notes.

-   Labelling guide in eval/LABELING_GUIDE.md with intent definitions,
    edge cases and routing rules, so labels are consistent.

-   Label a 50-ticket subset twice (on different days) and report
    self-agreement, or have a friend label it and report agreement.

-   File: eval/golden.jsonl, versioned. Never used for training or
    tuning.

# 8. Evaluation harness

One command: python -m eval.run \--config eval/config.yaml produces
eval/results/\<timestamp\>/metrics.json and report.md.

  -----------------------------------------------------------------------
  **Area**            **Metrics**
  ------------------- ---------------------------------------------------
  Intent              Macro-F1, accuracy, per-class F1, confusion matrix,
                      for every model

  Routing             Precision and recall of auto-handle vs gold route,
                      coverage, escalation reason breakdown,
                      precision-coverage curve

  Reply quality       LLM-as-judge rubric (1 to 5) for groundedness,
                      helpfulness, tone match, safety; plus BERTScore vs
                      the real reply as a secondary signal; human spot
                      check of 50 with agreement reported

  Safety              Count of drafts with invented links, promises, or
                      PII requests (should be 0 after post-checks)

  Performance         p50/p95 latency of /api/triage end to end, and per
                      stage (classify, retrieve, draft)
  -----------------------------------------------------------------------

The harness must be deterministic where possible (fixed seeds,
temperature 0 for the judge) and must record model names, prompt
versions and git commit in the output.

# 9. Flask API and frontend

## 9.1 Endpoints

  -----------------------------------------------------------------------
  **Method + path**   **Input**            **Output**
  ------------------- -------------------- ------------------------------
  POST /api/triage    {text}               {intent, confidence, top3,
                                           route, reasons, draft,
                                           sources, groundedness,
                                           latency_ms}

  POST /api/batch     {items: \[{id,       List of triage results
                      text}\]} (max 100)   

  GET /api/examples   none                 Sample tickets per intent for
                                           the demo

  GET /api/metrics    none                 Latest eval summary (from
                                           metrics.json)

  GET /api/health     none                 {status, model, version}
  -----------------------------------------------------------------------

-   App factory pattern (create_app()), blueprints, config from env,
    models loaded once at startup.

-   Input validation (pydantic or marshmallow), consistent JSON errors,
    CORS for the frontend origin, request logging with latency.

-   Gunicorn in production.

## 9.2 Frontend (plain HTML, CSS, JavaScript)

-   Inbox-style page: left column of sample tickets (or paste your own),
    right panel showing intent with confidence bar, route badge (Auto /
    Escalate) with reasons, the draft reply in an editable box, and the
    source replies it was grounded on.

-   Metrics page: renders the latest eval summary (tables, simple charts
    with Chart.js or plain SVG).

-   Calls the API with fetch; API base URL set in one config file.

-   Served as static files (from Flask or any static host).

## 9.3 Repository layout

support-agent/

data/ prepare.py, label_silver.py, processed/ (gitignored large files)

models/ train_baselines.py, train_transformer.py, saved/ (gitignored)

agent/ classifier.py, retriever.py, drafter.py, router.py, pipeline.py,
prompts/

api/ \_\_init\_\_.py (create_app), routes.py, schemas.py

frontend/ index.html, metrics.html, app.js, styles.css

eval/ golden.jsonl, LABELING_GUIDE.md, run.py, judge.py, config.yaml,
results/

tests/ test_router.py, test_api.py, test_drafter_checks.py,
test_prepare.py

Dockerfile, docker-compose.yml, requirements.txt, Makefile, .env.example

README.md, REPORT.md, DECISIONS.md

# 10. Deployment and quality

-   Dockerfile for the API (CPU torch, model weights baked in or
    downloaded at build).

-   Deploy somewhere free and simple: Hugging Face Spaces (Docker),
    Render, Railway, or Google Cloud Run. Frontend can be served by
    Flask or a static host.

-   pytest for router rules, drafter post-checks, data prep, and API
    endpoints (with a fake drafter so tests need no LLM). GitHub Actions
    running tests on push.

-   If the hosted demo cannot run an LLM for free, the demo uses the
    template fallback and the README says so clearly.

# 11. Milestones (about 6 working days from an empty repo)

  ---------------------------------------------------------------------------
  **Day**   **Goal**                              **Done when**
  --------- ------------------------------------- ---------------------------
  1         Repo skeleton (layout, requirements,  CI green; processed parquet
            Makefile, pytest, CI); download       files + data card +
            twcs.csv; data prep, time split, data taxonomy in DECISIONS.md
            card; lock the taxonomy               

  2         Silver labels; golden set sampled and golden.jsonl with 300+
            labelling guide written; I label the  items
            golden set                            

  3         All baselines + DistilBERT + BERTweet Table in eval/results with
            trained (3 seeds); comparison table   mean and std

  4         Retriever, drafter with post-checks,  pipeline.py triages any
            router with tuned threshold           text end to end

  5         Flask API + frontend + tests +        Demo works locally;
            Docker; eval harness full run         report.md generated

  6         Deploy, README, REPORT.md,            Public link works; repo
            DECISIONS.md, screenshots; final      looks finished
            resume numbers                        
  ---------------------------------------------------------------------------

# 12. Deliverables checklist

-   Cleaned dataset + data card.

-   Intent taxonomy and labelling guide.

-   Golden evaluation set (versioned).

-   Trained baselines, DistilBERT and BERTweet, with a comparison table.

-   Grounded drafter with post-checks and fallback.

-   Transparent router with reason codes and a precision-coverage curve.

-   Evaluation harness producing metrics.json and report.md in one
    command.

-   Flask REST API + plain JS frontend + tests + Dockerfile + CI.

-   **REPORT.md**: problem, data, approach, results tables, error
    analysis (10 worst mistakes with explanations), limitations, what I
    would do next.

-   **DECISIONS.md**: dated entries for each important choice (brand,
    taxonomy, models, thresholds, LLM provider, why not Streamlit) with
    options considered and reasons.

-   **README.md**: pitch, demo link, screenshots, quick start,
    architecture sketch, headline metrics.

# 13. Interview questions this project should prepare me for

-   Why did BERTweet beat (or not beat) DistilBERT on this data?

-   How noisy were the silver labels, and how did you check?

-   How did you choose the auto-handle threshold, and what is the
    trade-off between precision and coverage?

-   How do you stop the drafter from inventing policies or links?

-   Why a time-based split instead of a random split?

-   How would you adapt this to a second brand, or to email tickets like
    Hiver handles?