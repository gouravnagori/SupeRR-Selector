# Model Cards: SupeRR Selector S2 Pressure Performance System

## 1. Win Probability (WP) Model

### Purpose & Problem Formulation
- **Objective**: Estimate the instantaneous probability that the batting team wins the match ($P(\text{Win})$), computed strictly prior to each delivery ($t_0$) with zero look-ahead bias.
- **Target**: Binary indicator $y \in \{0, 1\}$ (1 if batting team at that ball won the match, 0 if lost).
- **Deliveries evaluated**: 199,988 balls across 843 matches (401 IPL + 442 T20I matches from 2022 to Nov 2026).

### Architecture & Training
- **Model Selected**: Regularized Logistic Regression with Standard Scaler.
- **Comparison Baseline**: LightGBM Classifier with monotonic constraints (`wickets_in_hand` $\ge 0$, `balls_remaining` $\ge 0$, `resources` $\ge 0$).
  - LightGBM 5-fold CV LogLoss: $0.5269 \pm 0.0230$, AUC: $0.8072 \pm 0.0193$.
  - Logistic Regression Holdout Test LogLoss (Season 2026): **0.5724**, Brier Score: **0.1978**, AUC: **0.7689**.
  - Rationale: Logistic Regression demonstrated superior out-of-sample generalization without overfitting to the historically anomalous 250+ scores of the 2026 season.
- **Validation Scheme**: Grouped 5-Fold Cross-Validation grouped by `match_id` + Chronological Out-of-Sample Holdout on Season 2026 (141 matches). Random ball-level splitting was explicitly prohibited to prevent intra-match leakage.

### Feature Set (Pre-Ball Strictly)
1. `innings`: Innings 1 (defending par) or Innings 2 (chasing target).
2. `balls_remaining`: Legal deliveries remaining in innings (adjusted for rain-shortened DLS overs).
3. `wickets_in_hand`: $10 - \text{wickets fallen}$.
4. `cum_total_runs`: Total team score prior to the delivery.
5. `current_run_rate`: Cumulative score divided by legal overs bowled so far.
6. `is_chase`: Binary indicator for 2nd innings.
7. `chase_target`: Revised DLS target or $1\text{st Innings Total} + 1$.
8. `runs_needed`: $\max(0, \text{Target} - \text{Current Score})$.
9. `required_run_rate`: Runs needed per over remaining.
10. `resources`: Frank Duckworth-style interaction ($\text{Wickets in Hand} \times \text{Balls Remaining}$).
11. `venue_par_score`: Historical first-innings scoring par for the specific venue and format, computed exclusively from training matches (no leakage).
12. `inn1_score_vs_par`: First innings trajectory relative to venue par at current over.
13. `is_knockout`: Binary indicator for playoffs, qualifiers, and finals.
14. `is_ipl`: Binary format indicator (IPL franchise competition vs International T20I).
15. `chase_pressure`: Interaction term ($\text{RRR} \times \ln(1 + \text{Balls Remaining})$).

---

## 2. Pressure Index (PI) Formulation

### Formula & Components
Pressure is defined as a continuous score in $[0, 1]$ combining:
$$\text{PI} = 0.70 \times \text{Leverage}_{\text{norm}} + 0.30 \times \text{Closeness}_{\text{norm}}$$

1. **Leverage (70% weight)**:
   $$\text{Leverage} = \sum_{k \in \text{Outcomes}} P(k) \cdot |\text{WP}(s_{t+1} \mid k) - \text{WP}(s_t)|$$
   Evaluated over historical empirical distribution of outcomes:
   $\{0: 31.6\%, 1: 37.3\%, 2: 6.5\%, 3: 0.3\%, 4: 12.1\%, 6: 6.6\%, \text{wicket}: 5.6\%\}$.
2. **Closeness / State Tension (30% weight)**:
   $$\text{Closeness} = (1.0 - 2 \cdot |\text{WP} - 0.5|) + 0.25 \cdot \text{ChaseTension}$$

### Thresholds
- **High Pressure (Q75+)**: $\text{PI} \ge 0.3800$ (top 25% highest-stakes deliveries).
- **Moderate Pressure (Q50-75)**: $0.3066 \le \text{PI} < 0.3800$.
- **Ordinary Match State**: $\text{PI} < 0.3066$.

### Empirical Verification (Separation of Reality)
- **Scoring Rate**: Drops from 137.4 runs/100 balls in ordinary states to 123.6 runs/100 balls in high-pressure states ($p < 0.0001$).
- **Wicket Rate**: Surges from 4.81% in ordinary states to **7.18%** in high-pressure states (+49.3% increase).
- **Dot Ball Rate**: Increases under pressure from 32.1% to 37.4%.

---

## 3. Expected-Outcome Context Baselines

### Models
1. **$E[\text{runs}]$ (Expected Runs per Ball)**:
   - LightGBM Regressor (`RMSE`: $1.7092 \pm 0.0053$, `MAE`: $1.2827$).
2. **$P(\text{wicket})$ (Expected Probability of Wicket)**:
   - LightGBM Binary Classifier (`AUC`: $0.6306 \pm 0.0041$, `Brier Score`: $0.0505 \pm 0.0006$, `LogLoss`: $0.2046$).

### Context Features (Strictly Leave-One-Out)
- Match situation: Phase (Powerplay, Middle, Death), Wickets in Hand, Balls Remaining, Innings, Venue Par.
- Matchup Dynamics: Batter Handedness (RHB/LHB), Bowling Style (Pace vs Spin, Delivery Type).
- Opponent Quality: Leave-one-out opponent bowling economy and strike rate (computed across all other matches to prevent circular player absorption).
- Crucially: **Player identity is excluded** to prevent the model from absorbing individual player skill.

---

## 4. Player Rating & Shrinkage Formulation

### Batting Pressure Value (BPV)
$$\text{BPV}_{\text{hp}} = 0.50 \cdot \text{RAE}_{100} + 0.35 \cdot (\text{WPA}_{100} \times 8.0) + 0.15 \cdot (\text{DA}_{100} \times 2.0)$$
- $\Delta \text{BPV} = \text{BPV}_{\text{hp}} - \text{BPV}_{\text{baseline}}$
- $\text{Composite} = 0.65 \cdot \text{BPV}_{\text{hp}} + 0.35 \cdot \Delta \text{BPV}$

### Bowling Pressure Value (BoPV)
$$\text{BoPV}_{\text{hp}} = 0.45 \cdot \text{RSAE}_{100} + 0.35 \cdot (\text{WPA}_{100} \times 8.0) + 0.20 \cdot (\text{WAE}_{100} \times 15.0)$$
- $\Delta \text{BoPV} = \text{BoPV}_{\text{hp}} - \text{BoPV}_{\text{baseline}}$
- $\text{Composite} = 0.65 \cdot \text{BoPV}_{\text{hp}} + 0.35 \cdot \Delta \text{BoPV}$

### Empirical-Bayes Shrinkage (Partial Pooling)
$$\hat{\theta}_i = B_i \cdot y_i + (1 - B_i) \cdot \mu_0, \quad B_i = \frac{\tau^2}{\tau^2 + \sigma^2 / N_i}$$
Pulls small samples toward the population prior $\mu_0$ while preserving signal for high-volume performers.

### Match-Clustered Bootstrap 95% Confidence Intervals
500 cluster-bootstrap iterations resampling `match_id` blocks to capture true match-to-match variance and correlation.

### Final Reliability Multiplier
$$\text{Final Rating} = \hat{\theta}_i \cdot \text{CF}_i \cdot \text{CompMult}_i$$
Where $\text{CF}_i$ rewards high positive match impact rate ($>50\%$) and penalizes erratic volatility.

---

## 5. Limitations & Boundary Conditions
1. **Sample Concentration**: International T20I associate matches involve asymmetric competition strength; partial pooling and format multipliers alleviate but do not eliminate strength imbalances.
2. **Speed & Delivery Trajectory**: `bowl_speed` is 0/missing for majority of deliveries; release speeds and pitch maps could not be incorporated.
3. **Auction Price & Roster Availability**: Player evaluations are purely performance-based; contract costs and international NOC availability are external factors.

