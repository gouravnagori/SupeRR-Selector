# MASTER PROMPT: SupeRR Selector S2, Round 1 (Pressure Performance System + Dashboard)

> How to use: paste everything below the line into your AI coding agent (Claude Code / Cursor / etc.) and attach `data_pack.zip`.
> Before you paste: do the 2-minute "Brand tokens" step in Section 9 so the design is exact.

---

## 0. ROLE AND MINDSET

You are a senior applied-ML / sports-analytics engineer and a front-end engineer. You are building a competition entry for Rajasthan Royals' "SupeRR Selector Season 2, Round 1". The entry is judged by RR's analytics team on **method quality, rigor, reproducibility and cricket sense**, in that order. Looks matter, but the **player-rating logic matters most**, because the final rankings decide the result.

Work like an engineer who must defend every number to a skeptical analyst. If something is uncertain, say so and quantify it. Never invent data, columns or results. Never claim a metric you have not computed.

## 1. THE TASK (verbatim essentials)

Build a data-driven system that measures how batters and bowlers perform in high-pressure situations **compared with their usual performance**, and rank the players who deliver most consistently when it matters.

Final required outputs:
1. **Top-10 batters** and **Top-10 bowlers** under pressure, ranked 1 to 10, no repeats within a list.
2. **Methodology report (PDF)** covering: pressure definition, performance measurement (metrics, baselines, rating logic), fair comparison (sample size, eligibility, context, IPL vs T20I), evidence (tables/charts), reliability and limitations.
3. A **dashboard** (my own addition) that presents the same results interactively. The dashboard is secondary to the rankings and report.

The rankings must come from the supplied data, not from reputation. Methodology must be reproducible by someone else.

Rules: individual entry; the data pack is competition-only, so never upload it anywhere or use external APIs with it; the dashboard must run **fully offline** from precomputed files.

## 2. THE DATA (zip attached; unzip and inspect before anything else)

Files in `Data Pack/`: `ball_by_ball.csv` (~201k rows, 867 matches), `matches.csv`, `competitions.csv`, `teams.csv`, `playing_eleven.csv`, `competition_team_player_mapping.csv`, plus the problem-statement PDF (read it fully).

Known facts (verify them yourself, don't trust blindly):
- Formats: `T20` (IPL, 2022-2026, ~401 matches) and `T20I` (~482 matches), Jan 2022 to Nov 2026.
- `ball_by_ball` columns include: match_id, innings, overid, over_ball_num, innings_ball_num, batting_team_id, bowling_team_id, striker_id/name, non_striker_id/name, bowler_id/name, batting_type, bowling_type, batting_order, runs, is_four, is_six, is_wicket, dismissal_type, dismissed_player_id, extras_type, extras1_runs, extras_2_runs, pace_or_spin, bowl_speed (often 0, treat as missing), stroke, delivery_style, over_or_around, on_or_off.
- `innings` has values 3 and 4 (super overs), so handle or exclude them explicitly and document the choice.
- `matches` has `knock_out`, `stage`, `revised_target`, `first_inn_revised_overs`, `second_inn_revised_overs` (rain-reduced matches), `win_team_id`, `result`, `venue_id`, `toss_*`. Use these.
- `playing_eleven` has `is_impact`, `is_impact_off`, `is_captain`, `is_wk`, `batting_order`.

### Mandatory data-quality pass (write results to `outputs/data_audit.md`)
- Define precisely: legal ball (exclude wides and no-balls from balls faced and over counts), whether `runs` includes extras, how byes/leg-byes are credited (to team, not batter, not bowler).
- Bowler runs conceded = batter runs + wides + no-balls; **not** byes or leg-byes.
- Bowler wickets: exclude run out, retired, obstructing the field, timed out. Document the list used.
- Dismissed player may differ from striker (non-striker run-out): attribute to `dismissed_player_id`.
- Reduced-over matches: use the revised target and revised overs for required run rate and balls remaining. Never compute pressure from 20 overs in a shortened game.
- Abandoned or no-result matches: drop from any win-probability training.
- Check for duplicate balls, missing IDs, name collisions (same name, different `player_id`; always key on `player_id`), and players appearing under multiple teams (IPL franchise and national team).
- Report counts before and after cleaning.

## 3. DEFINING PRESSURE (the core idea; do this carefully)

Pressure must be a **continuous, per-ball score computed only from information available before that ball is bowled**. There must be zero look-ahead leakage.

### 3.1 Build a ball-by-ball Win Probability (WP) model
- Target: whether the **batting team** at that moment eventually wins the match.
- Features at the start of each ball: innings, balls left (use revised overs where relevant), wickets lost, current score, current run rate, **target and required run rate (chase only)**, runs needed, resources-style interaction features (wickets in hand x balls left), format (IPL vs T20I), and a venue/team-strength prior (e.g., venue first-innings average from **training matches only**).
- For the first innings, WP needs a par-score reference. Use a venue-and-format expected-final-score model (also trained without leakage) so the model works in both innings.
- Models: fit **logistic regression** as a transparent baseline and **gradient-boosted trees (LightGBM, fallback sklearn HistGradientBoosting)** as the main model. Use monotonic constraints where sensible (more wickets in hand never lowers WP). Compare both and keep the simpler one if the gain is negligible.
- Validation: **grouped CV by match_id (and a time-based holdout on the latest season)**. Report log-loss, Brier score, AUC, and a **calibration plot**. Show that WP is calibrated before you rely on it. No random ball-level splits.

### 3.2 Pressure Index (PI) per ball
Compute PI from two parts and show a plot for each:
1. **Leverage**: expected absolute change in WP from the next ball, estimated from the WP model over the distribution of possible outcomes (0,1,2,3,4,6, wicket) in that state. This is the standard "leverage index" idea. High leverage means the next ball matters a lot.
2. **Closeness / state tension**: how contested the game is, e.g. `1 - |WP - 0.5| * 2`, plus chase features (required rate minus current rate, balls left).

Combine into a single PI (document the formula; a leverage-dominant weighting is recommended). Then define pressure buckets with data-driven thresholds (e.g., top quartile of PI = "high pressure", bottom half = "ordinary"). Also add **context flags** for stage (knockout, playoff, final) as a sensitivity layer and never as the main definition.

### 3.3 Prove the definition is meaningful (mandatory chart set)
Show that high-PI balls differ from ordinary balls: lower scoring rate, higher wicket rate, more dots, across both formats and both innings. If the definition does not separate situations, fix it before continuing. Also include a sensitivity analysis: re-rank using 3 alternative pressure definitions (e.g., "death overs of a close chase", "top-20% PI", "required-rate-based only") and report rank stability (Spearman/Kendall plus top-10 overlap).

## 4. MEASURING PLAYER PERFORMANCE (the most important section)

The ranking must reward **performance above what was expected in the same situation**, not raw stats.

### 4.1 Expected-outcome baseline (context-adjusted)
Train expected-value models on **all balls** (not only pressure ones) so each ball gets an expectation for its context:
- `E[runs]` and `P(wicket)` for a ball, given: phase (powerplay/middle/death), wickets in hand, balls left, innings, batter handedness, bowler type (pace/spin and bowling_type), venue-level scoring environment, format, and opponent bowling/batting strength (computed leave-one-out so a player doesn't influence his own context).
- Use gradient-boosted trees; calibrate; evaluate with grouped CV. Keep features that are known **before** the ball.
- Do not include the player's own identity in the context model (so it can't absorb the player's skill).

### 4.2 Batting score under pressure
For each batter and each ball faced, compute:
- **Runs Above Expected (RAE)** = actual runs minus E[runs]
- **Dismissal cost** = value of the wicket in WP terms
- **WPA (Win Probability Added)** for the batter from his balls
- A combined **Batting Pressure Value (BPV)** per 100 pressure balls = RAE efficiency plus WPA plus dismissal-avoidance, with weights justified in the report (and tested for sensitivity).
Also compute the batter's **own baseline** (his non-pressure performance, same metrics) and a **pressure delta** = pressure performance minus own baseline. Rank on a blend that rewards **high absolute pressure value AND not collapsing relative to own norm**. Explain the blend. A player who is average normally but elite under pressure should rank high; so should a player who is elite everywhere and stays elite under pressure.

### 4.3 Bowling score under pressure
Symmetric logic, from the bowler's side:
- **Runs Saved Above Expected**, **Wicket Value above expected**, **dot-ball pressure creation**, **WPA from bowler's perspective**, economy and wicket-rate vs expected, phase-adjusted (a death-overs bowler is compared with death-overs expectation, never with powerplay economy).
- Include boundary-prevention and yorker/dot rate at high PI if the data supports it.
- Bowlers' own baseline and pressure delta, computed the same way as for batters.

### 4.4 Fair comparison rules
- **Minimum sample**: set explicit eligibility (e.g., at least N high-pressure balls faced/bowled AND at least M distinct high-pressure matches). Choose N and M from the data (look at the distribution), justify them, and show how rankings change if you vary them.
- **Shrinkage**: apply **empirical-Bayes / hierarchical (partial pooling) shrinkage** to every player's pressure rating so that small samples are pulled toward the mean, and report **95% intervals** (bootstrap by match, not by ball, because balls within a match are correlated).
- **Role context**: opener, middle-order, finisher, bowling phase usage. Do not rank a finisher against an opener on unequal opportunity without adjustment. Report role tags.
- **IPL vs T20I**: add a competition-strength adjustment (e.g., fit a mixed-effects or hierarchical model with a competition effect, or scale by opposition quality). State the assumption and show rankings with and without the adjustment. Players with data in both formats should have both combined in a principled way (weighted by pressure balls).
- **Recency**: include a sensitivity run that down-weights older seasons, since the auction is about 2027 form, but don't make it the headline unless it clearly improves out-of-sample prediction.

### 4.4b Reliability (this is the title of the challenge, so treat it as a first-class result)
- **Split-half reliability**: odd vs even matches, and first-half vs second-half of the period; report correlation of ratings. Report which metrics are stable and which are noise.
- **Consistency score**: share of high-pressure matches (or innings/spells) in which the player beat expectation, and the standard deviation across matches. Final "reliability" = good impact AND low variance and decent hit-rate.
- **Predictive check**: build ratings on earlier seasons and test whether they predict pressure performance in the latest season better than naive stats (strike rate, average, economy). If your method does not beat naive baselines, say so honestly and investigate.
- Final ranking score = a documented combination of (shrunk pressure value) x (consistency/reliability factor), with a table showing each component for every top-10 player.

## 5. OUTPUT FILES

Produce these in `outputs/`:
- `data_audit.md`
- `model_cards.md` (WP model, expected-run model, expected-wicket model: features, CV scores, calibration, limitations)
- `batters_ranking.csv`, `bowlers_ranking.csv`: full eligible-player tables with all components, intervals, sample sizes, role tags, rank.
- `top10_batters.csv`, `top10_bowlers.csv`
- `sensitivity_results.csv` (alternative definitions, thresholds, weights, with/without competition adjustment)
- `figures/` (all report charts, PNG at 200 dpi, plus SVG where possible)
- `report/methodology_report.pdf` (see Section 7)
- `dashboard/` (see Section 8)
- `README.md` (exact steps to reproduce from the zip; fixed random seeds; `requirements.txt`; single command `make all` or `python run_all.py`)

Code layout: `src/` modules (`data.py`, `pressure.py`, `wp_model.py`, `baselines.py`, `ratings.py`, `reliability.py`, `viz.py`), notebooks only for exploration, and one runnable pipeline. Type hints, docstrings, unit tests for the cricket-logic pieces (legal ball counts, bowler-credited wickets, revised-target handling, chase RRR computation).

## 6. WORKING METHOD: STAGE GATES (important)

Work in stages. **At the end of each stage, stop and print a short summary of results and any problems, then continue only if the checks pass.** Never skip ahead with unverified numbers.

1. Data audit and cleaning.
2. WP model + calibration + pressure index + the "pressure is meaningful" charts.
3. Expected-outcome baselines.
4. Player ratings, shrinkage, intervals.
5. Reliability and sensitivity, final ranking.
6. Sanity review of the top 10: print the top-10 batters and bowlers with sample sizes and think like an RR scout. Flag anything that looks wrong (e.g., a player with tiny sample, a role artifact, a team-quality artifact) and fix the method rather than hand-editing the list.
7. Report.
8. Dashboard.

Also, **ask me before assuming** only if a choice would materially change rankings; otherwise decide, document, and test sensitivity.

## 7. METHODOLOGY REPORT (PDF, ~10-14 pages)

Structure: 1) Executive summary with both top-10 lists. 2) Pressure definition and why (with the separation charts). 3) Models and validation (WP calibration, expected-run baseline). 4) Rating construction (formulas written out plainly). 5) Fair-comparison choices (samples, role, IPL vs T20I). 6) Results: top-10 tables with intervals, sample sizes, component breakdown; a few player case studies (a batter whose raw stats mislead, a bowler who is better than his economy suggests). 7) Reliability evidence. 8) Sensitivity. 9) Limitations (where the model is uncertain, small samples, T20I opposition strength). 10) **RR fit**: for each top-10 player, one short paragraph on role, phase, handedness/type, age/experience if derivable from data, and what gap they fill; add a clearly labelled note that auction price/availability were not in the data. Keep the writing plain, specific and honest. No filler, no hype.

## 8. DASHBOARD

Stack: a static, offline site (React + Vite + TypeScript, or plain HTML/JS if simpler) reading precomputed JSON. Charts with D3 or Recharts. No network calls at runtime. Must open with one command and also build to a static folder.

Pages/sections:
1. **Hero / overview**: the two top-10 lists as ranked cards with animated count-up of the headline rating and a mini spark of consistency.
2. **How pressure works**: an interactive explainer. A slider through an innings showing WP and pressure index rising and falling; click a famous-looking close chase from the data and watch PI per ball.
3. **Batters** and **Bowlers** tabs: sortable/filterable table (role, format, min sample slider), each row expandable.
4. **Player detail**: pressure vs ordinary performance comparison, rating with confidence interval, match-by-match consistency strip, phase breakdown, role tag.
5. **Compare**: pick 2-3 players and compare radar/bars.
6. **Method & reliability**: calibration curve, split-half result, sensitivity heatmap (rank stability), eligibility slider showing how rankings move.
7. **RR fit** panel on each top-10 player.

Accessibility and quality: responsive (mobile first), keyboard accessible, WCAG AA contrast, readable chart labels, `prefers-reduced-motion` respected (turn off non-essential animation), no layout shift, fast load.

### Animation spec (purposeful, premium, not gimmicky)
- Page load: staggered fade-and-rise for cards (about 60-80 ms stagger, 400-600 ms ease-out).
- Numbers count up once when scrolled into view.
- Ranking list: smooth FLIP reorder animation when sorting or filtering.
- Charts: lines draw in (stroke-dashoffset), bars grow from baseline, tooltips ease in.
- Pressure explainer: animated ball-by-ball playback with a scrubber; the pressure meter fills smoothly.
- Hover: subtle lift and accent underline on cards; rank badges have a light shimmer on first view only.
- Easing: cubic-bezier(0.22, 1, 0.36, 1). Keep every animation under about 700 ms; none should block interaction.
- Use CSS/Framer Motion/GSAP ScrollTrigger as appropriate; no heavy video backgrounds.

## 9. DESIGN: MATCH THE RAJASTHAN ROYALS WEBSITE (NO GENERIC "AI" LOOK)

**Hard constraints:** do NOT use default AI aesthetics: no purple-to-blue gradients, no glassmorphism blobs, no Inter/Roboto/system-default look, no generic emoji icons, no stock dashboard template. The look must feel like it belongs on https://www.rajasthanroyals.com/.

### Brand tokens: do this first (2 minutes, by me or by you)
I could not verify exact values, so **extract them from the live site, don't guess**:
- If you have browser/network access: fetch the site's CSS, and list the real computed values for background, primary pink, royal blue, text colors, button styles, border radii, and the exact `font-family` / webfont files used for headings, nav and body.
- If you cannot access it: stop and ask me to paste the values from Chrome DevTools (right-click, Inspect, Computed, then `font-family`, `color`, `background-color`; also the Network tab, Fonts filter, for font names). I will provide them.
- Starting reference only (**unverified**; replace with the extracted values): RR identity is a vivid **pink** and a deep **royal blue** with white, plus dark surfaces for the site's Dark Mode. Define everything as CSS variables (`--rr-pink`, `--rr-blue`, `--bg`, `--surface`, `--text`, `--muted`, `--border`, `--accent`) in one `tokens.css` so the whole theme can be corrected in one place.
- Fonts: use the **same families RR uses** (self-host the files if licensed for web use; otherwise pick the closest free Google Font and say which substitution you made). Match heading weight, letter-spacing and casing style to the site (observe whether headings are uppercase/condensed).
- Support **light and dark themes** like the site does ("Dark Mode" toggle exists on the site), persisting the choice.

Design direction: sports-broadcast editorial, confident and bold, big typographic numbers, generous spacing, sharp or lightly rounded corners consistent with the site, pink used as the single strong accent (CTAs, rank badges, highlights), blue for structure and charts, neutral dark/white surfaces. Chart palette is derived from the brand colors only (pink, blue, and tints/neutrals), with colorblind-safe differentiation using shape/label/pattern as well as color. Include the Rajasthan Royals name as text only; do not copy or embed official logos or imagery without permission, and leave a clearly marked placeholder slot for a logo.

## 10. QUALITY BAR AND ANTI-FAILURE CHECKLIST

Before declaring done, verify and tell me the result of each:
- [ ] No leakage: WP/baseline features use only pre-ball information; CV grouped by match.
- [ ] WP calibration plot looks sane; AUC and log-loss reported.
- [ ] High-PI vs ordinary separation shown for batting and bowling.
- [ ] Reduced-over (revised target) matches handled; super-overs handled.
- [ ] Bowler credit rules (extras, wicket types) unit-tested.
- [ ] Shrinkage and match-level bootstrap intervals computed; eligibility thresholds justified.
- [ ] Split-half reliability and predictive test reported honestly.
- [ ] Sensitivity: top-10 overlap across alternative definitions reported; list which picks are robust and which are fragile.
- [ ] Top-10 lists pass a "cricket sense" review; any odd entries explained or fixed in the method.
- [ ] Report numbers match CSVs and dashboard exactly (single source of truth: the CSVs).
- [ ] Pipeline reruns from scratch with one command and identical results (seeds fixed).
- [ ] Dashboard works offline, mobile and desktop, passes basic accessibility checks, respects reduced motion.
- [ ] No data pack contents are published or sent anywhere.

## 11. FINAL RESPONSE FORMAT

When finished, give me: (1) the two top-10 lists in order with ratings, intervals and sample sizes; (2) 5 bullets on why the method is defensible; (3) the 3 biggest limitations; (4) the exact file list and the commands to run the pipeline and the dashboard; (5) any decision you made that I should double-check.
