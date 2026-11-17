# SupeRR Selector Season 2, Round 1
## Rajasthan Royals Pressure Performance System & Analytics Dashboard

An end-to-end sports analytics machine learning system that measures how T20 batters and bowlers perform in high-pressure situations compared with their usual performance, ranking players who deliver most consistently when it matters most.

---

## 1. Quickstart & Complete Reproduction

### Prerequisites
- Python 3.10+ (tested on Python 3.14)
- A modern web browser (for the interactive dashboard)

### Step 1: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 2: Run Complete Pipeline (One Command)
```bash
python run_all.py
```
This executes all 8 stages from raw data to PDF report and offline dashboard in ~90 seconds with fixed random seed (`SEED = 42`):
1. **Data Ingestion & Cleaning**: Legal ball definition, extras attribution, bowler-credited wickets, super overs exclusion, DLS revised overs.
2. **Win Probability & Pressure Index**: Pre-ball Logistic Regression & LightGBM with monotonic constraints, GroupKFold CV, 2026 holdout validation, Leverage & Closeness formulation.
3. **Context Baselines**: Leave-one-out opponent strength, LightGBM $E[\text{runs}]$ and $P(\text{wicket})$ models.
4. **Player Ratings**: Runs Above Expected (RAE), Runs Saved Above Expected (RSAE), WPA, Dismissal Avoidance, Empirical-Bayes shrinkage, 95% match-clustered bootstrap CIs.
5. **Reliability & Sensitivity**: Split-half stability (odd/even), 2022-2025 out-of-sample forward prediction to 2026, 7 sensitivity scenarios.
6. **Visualizations**: 8 publication-quality charts saved to `outputs/figures/`.
7. **Methodology Report**: 13-page PDF generated at `outputs/report/methodology_report.pdf`.
8. **Dashboard Data**: Precomputed JSON generated for zero-latency offline exploration.

### Step 3: Launch Interactive Offline Dashboard
```bash
cd dashboard
python -m http.server 8000
```
Then open `http://localhost:8000` in your browser (or simply double-click `dashboard/index.html` to open directly).

---

## 2. Definitive Rankings

### Top 10 Batters Under Pressure
| Rank | Player | Role Tag | HP Balls | HP SR | RAE/100 | Hit Rate | Final Rating | 95% Clustered CI |
|:---:|:---|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| **#1** | **Ayush Mhatre** | Middle Order / Opener | 90 | 193.3 | +48.2 | 80.0% | **29.45** | [13.7, 59.1] |
| **#2** | **Heinrich Klaasen** | Middle Order Spine | 163 | 198.2 | +42.1 | 70.8% | **27.88** | [14.8, 41.8] |
| **#3** | **Vaibhav Sooryavanshi** | Aggressive Opener (RR) | 227 | 222.5 | +45.8 | 74.2% | **27.50** | [22.9, 56.3] |
| **#4** | **Rashid Khan** | Clutch Finisher | 77 | 185.7 | +36.2 | 50.0% | **22.24** | [-7.4, 54.5] |
| **#5** | **Ashutosh Sharma** | Designated Death Finisher | 97 | 182.5 | +32.1 | 53.8% | **20.97** | [-9.2, 62.5] |
| **#6** | **Glenn Maxwell** | Middle Order Floater | 184 | 175.0 | +28.4 | 57.7% | **18.87** | [5.7, 33.8] |
| **#7** | **Tim David** | Death Overs Finisher | 264 | 185.2 | +24.6 | 64.9% | **18.78** | [8.4, 41.1] |
| **#8** | **Parvez Emon** | Top Order LHB | 213 | 148.8 | +19.5 | 62.1% | **17.87** | [7.8, 30.8] |
| **#9** | **Bhanuka Rajapaksa** | Middle Order Intent LHB | 100 | 166.0 | +18.7 | 66.7% | **15.41** | [-1.5, 33.9] |
| **#10** | **Sikandar Raza** | Experienced Finisher | 236 | 146.6 | +14.2 | 58.3% | **15.26** | [7.9, 27.9] |

### Top 10 Bowlers Under Pressure
| Rank | Player | Primary Phase | HP Balls | HP Econ | RSAE/100 | Hit Rate | Final Rating | 95% Clustered CI |
|:---:|:---|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| **#1** | **Sufiyan Muqeem** | Middle Mystery Spin | 133 | 4.29 | +44.1 | 83.3% | **28.46** | [15.0, 30.9] |
| **#2** | **Yash Thakur** | Death Overs Seam | 79 | 8.51 | +22.4 | 60.0% | **23.38** | [-10.9, 25.3] |
| **#3** | **Gudakesh Motie** | Middle Overs Spin | 164 | 6.29 | +20.8 | 64.7% | **18.93** | [-4.5, 26.4] |
| **#4** | **Dunith Wellalage** | Middle Overs Control | 79 | 6.08 | +19.6 | 66.7% | **17.28** | [-13.2, 31.5] |
| **#5** | **Washington Sundar** | Powerplay Defensive Spin | 133 | 6.77 | +18.9 | 66.7% | **16.06** | [-0.9, 29.7] |
| **#6** | **Mayank Yadav** | Express Middle Pace (150+) | 83 | 7.30 | +17.2 | 76.9% | **14.46** | [-23.7, 30.5] |
| **#7** | **Josh Hazlewood** | Powerplay & Death Anchor | 458 | 7.18 | +18.4 | 62.5% | **13.88** | [1.4, 18.9] |
| **#8** | **Patrick Cummins** | Powerplay Enforcer | 255 | 6.71 | +15.7 | 64.5% | **13.58** | [-0.7, 19.7] |
| **#9** | **Arshad Khan** | Powerplay Left-Arm Seam | 101 | 7.54 | +14.1 | 58.8% | **12.97** | [-15.8, 20.6] |
| **#10** | **Kuldeep Yadav** | Middle Attacking Wrist Spin | 348 | 7.64 | +13.8 | 56.4% | **12.97** | [-0.5, 14.0] |

---

## 3. Directory Layout & Deliverables

```
D:\SupeRR\
├── 6af458274c1e8_data_pack/       # Extracted competition data pack
│   └── Data Pack/
│       ├── ball_by_ball.csv       # 200,999 raw balls
│       ├── matches.csv            # 883 match records
│       ├── competitions.csv       # T20 & T20I tournament metadata
│       ├── teams.csv              # Team mappings
│       ├── playing_eleven.csv     # Lineups & captain/wk indicators
│       └── competition_team_player_mapping.csv
├── src/
│   ├── __init__.py
│   ├── data.py                    # Data cleaning, legal deliveries, DLS
│   ├── wp_model.py                # Win Probability model & holdout calibration
│   ├── pressure.py                # Pressure Index (Leverage + Closeness)
│   ├── baselines.py               # E[runs] & P(wicket) context baselines
│   ├── ratings.py                 # BPV/BoPV, EB shrinkage, 95% CIs
│   ├── reliability.py             # Split-half & forward prediction checks
│   ├── viz.py                     # Publication figure generation
│   ├── report_generator.py        # PDF Methodology Report compiler
│   └── export_dashboard_data.py   # JSON synchronizer for dashboard
├── tests/
│   └── test_cricket_logic.py      # Unit tests for legal balls, extras, wickets
├── outputs/
│   ├── data_audit.md              # Comprehensive data audit report
│   ├── model_cards.md             # Detailed ML model cards
│   ├── batters_ranking.csv        # Full eligible batters ranking
│   ├── bowlers_ranking.csv        # Full eligible bowlers ranking
│   ├── top10_batters.csv          # Top-10 batters with component breakdown
│   ├── top10_bowlers.csv          # Top-10 bowlers with component breakdown
│   ├── sensitivity_results.csv    # 7-scenario rank robustness matrix
│   ├── figures/                   # 8 publication figures (PNG, 200 dpi)
│   │   ├── wp_calibration.png
│   │   ├── wp_feature_importance.png
│   │   ├── pressure_separation.png
│   │   ├── example_chase_wp_pi.png
│   │   ├── baseline_wicket_calibration.png
│   │   ├── baseline_feature_importance.png
│   │   ├── top10_batters_ranking.png
│   │   ├── top10_bowlers_ranking.png
│   │   ├── split_half_reliability.png
│   │   └── sensitivity_rank_stability.png
│   └── report/
│       └── methodology_report.pdf # 13-page technical methodology report
├── dashboard/
│   ├── index.html                 # Offline dashboard markup (7 sections)
│   ├── tokens.css                 # Rajasthan Royals official brand tokens
│   ├── data.js                    # Inlined precomputed datasets (no CORS issues)
│   └── app.js                     # Interactive scrubber, sorting, filtering, compare
├── run_all.py                     # Master one-command reproduction script
├── requirements.txt               # Pinned Python package dependencies
└── README.md                      # Documentation & instructions
```

---

## 4. Anti-Failure Checklist Verification
- [x] **Zero Look-ahead Leakage**: Win probability and baseline features use only pre-ball state ($t_0$).
- [x] **Grouped Match CV**: All cross-validation grouped by `match_id` plus a chronological holdout on Season 2026.
- [x] **Calibrated WP**: Calibration curves verified with Brier score ($0.1978$) and AUC ($0.7689$).
- [x] **Empirical Separation Proved**: High-PI deliveries exhibit +49.3% higher wicket rate, lower scoring rate, and higher dot ball percentage.
- [x] **DLS Revised Targets & Overs**: Exact revised targets and overs used for chase required run rates.
- [x] **Bowler Credit Rules Unit-Tested**: Run outs, retired out, and obstructing the field excluded from bowler wickets; byes/leg-byes excluded from bowler economy.
- [x] **Empirical-Bayes Shrinkage & 95% CIs**: Partial pooling pulls small-sample outliers toward the prior mean; 95% cluster-bootstrap intervals explicitly quantify uncertainty.
- [x] **Out-of-Sample Predictive Check**: Historical ratings beat naive economy (+41.9%) and strike rate on the unseen 2026 season.
- [x] **Sensitivity Analysis**: 7 alternate scenarios evaluated; rank stability (Spearman $\rho = 0.84 - 0.94$) and Top-10 overlap documented.
- [x] **Fully Offline Dashboard**: Opens in any browser with zero network requests, containing interactive chase scrubber, sortable tables, compare view, and light/dark mode.

