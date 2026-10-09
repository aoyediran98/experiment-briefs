---
name: experiment-brief
description: Write a pre-registered A/B test brief from a hypothesis and funnel numbers, attach any mockups or screenshots, publish it to the experiment-briefs site via GitHub and Vercel, and return the live link. Use when asked for an experiment brief, test brief, or sample size for a test.
---

# Experiment brief

Turn a hypothesis plus funnel numbers into a pre-registered test brief, publish it as a page on the briefs site, and reply with the link. The numbers are fixed by the script first; the written brief is produced around them and never changes them.

## Config (edit once)

- SITE_URL: https://experiment-briefs.vercel.app
- AUTHOR: Aminat Oyediran

This skill lives inside the experiment-briefs repository, so the session is already in the repo: work from its root and do not clone.

## Inputs to collect

Required: the observation that prompted the test (data, research, tickets), baseline conversion %, weekly eligible units entering the test, minimum detectable effect (relative %).
Defaults if not given: arms 2, alpha 0.05, power 0.8, unit of randomisation = user, allocation 50/50, surface inferred from context.
Optional: visuals. Any images or PDFs attached to the conversation (mockups, screenshots, funnel charts) go into the brief. If the user has not said what each shows, ask once which file is control, which is variant, and which is evidence; if unanswered, infer from filenames and say what you assumed.
Rewrite the hypothesis into one falsifiable sentence that names the change, the expected effect on the primary metric, and the reason ("Because X, doing Y will increase Z, because W"). Never accept "let's test a green button" as a hypothesis; ask what was observed. Ask for a missing number only if it cannot be inferred; otherwise proceed with a stated assumption.

## Steps

1. **Update.** `git pull` so briefs/index.json is current.
2. **Sanity-check feasibility before writing.** Estimate per-arm n for a two-proportion z-test and run time = n x arms / weekly units. If over 8 weeks, say so up front and offer a larger MDE or fewer arms before writing; never silently produce an infeasible brief. Also check the decision test: if win, loss and flat would all lead to the same action, say the test is not worth running.
3. **Stage visuals.** Copy each attached image or PDF into `incoming/` with a short descriptive filename (e.g. `control-goal-step.png`, `variant-b-ranges.png`, `funnel-dropoff-sept.png`). Accepted: png, jpg, gif, webp, svg, pdf, under 5 MB each; if one is larger, downscale it with Python (Pillow) to 1600 px wide before copying. Do not alter the content of a mockup.
4. **Write the brief JSON** at `input.json`, following `examples/quiz-goal-ranges.json` exactly. Author every field in plain, concrete language, in five groups:
   - **The why**: `problem` (what was observed, with numbers and sources), `hypothesis` (top-level field), `decisionRules.win / loss / flat` (what ships and what is tested next in each case; they must differ), `priorEvidence` (related past tests, or state none).
   - **What is being tested**: `control` (exact current state), `variants` (arms - 1 entries, each with `change` describing the one meaningful difference, plus `headline`, `supporting`, `rationale`), `audience`, `excluded`, `entryPoint` (where assignment happens), `unitOfRandomisation` (and why).
   - **How it will be judged**: `primaryMetric` as an object with `name`, `numerator`, `denominator`, `attributionWindow`; `successCriteria` (one paragraph quoting the target rate, the end-date rule and what counts as win / loss / inconclusive; no early stopping); `secondaryMetrics` (2-3); `guardrails` (2-3, each with a threshold); `mdeRationale` (tie the MDE to business value in money or volume).
   - **Statistics and logistics**: `baselineSource` (system, date range, audience definition), `trafficAllocation` (split and any ramp), `stoppingRule` (commit to the planned duration; name the only conditions for an early stop), `segmentsToWatch` (pre-registered, 2-4).
   - **Risks and ownership**: `risks` (overlapping tests, seasonality, campaigns, novelty), `qaChecks` (assignment firing, metric events, sample ratio check), `owners.build / analysis / decision`.
   - **Visuals**: `visuals` list, one entry per staged file: `{"path": "incoming/<file>", "caption": "<what it shows, one line>", "placement": "problem|control|variants|results"}`. Evidence goes under `problem`; the current state under `control`; mockups under `variants`; analysis mock-ups under `results`. Captions say what the reader should notice.
   Use the baseline and target rates exactly as given; do not recalculate sample size in prose.
5. **Render.** `python3 scripts/make_brief.py input.json`. It prints `briefs/<slug>.html`, copies visuals into `briefs/assets/<slug>/`, and updates `briefs/index.json`. Check stderr for skipped visuals and fix them before continuing. Read the rendered flag: if red (over 8 weeks), stop and report rather than publishing.
6. **Publish.** `rm -rf input.json incoming && git add -A && git commit -m "Brief: <title>" && git push`. Vercel deploys within about a minute.
7. **Reply** with: the live link `SITE_URL/briefs/<slug>.html`, the three headline numbers (sample per arm, run time, target rate), the feasibility flag in one sentence, how many visuals were included, and any assumption made for a missing input.

## Fallback

If `git push` fails, do not retry blindly. Publish the rendered HTML with the Artifact tool instead: inline `style.css` into the page and embed each visual as a data: URI, give that link, and say in one line that the site push failed and why.

## Quality bar

- Pre-registration is the point: metric definition, success criteria, end date and segments are fixed before any copy is written.
- One primary metric only, defined as numerator / denominator with a window. Guardrails have numbers.
- Statistical significance is not practical significance: if the MDE is below what the business would act on, say so.
- Unit of randomisation is stated and justified; session-level assignment needs a reason.
- Every visual has a caption that earns its place; no decorative images.
- No marketing filler in variants; every headline must plausibly move the primary metric for the reason stated.
