"""
run_all.py - Master Pipeline Execution Script for SupeRR Selector S2.

Executes the complete end-to-end pipeline with fixed random seeds (SEED=42):
- Stage 1: Data Audit & Cleaning
- Stage 2: Win Probability Modeling & Pressure Index (Leverage + Closeness)
- Stage 3: Expected-Outcome Context Baselines (E[runs] & P(wicket))
- Stage 4: Player Ratings, Empirical-Bayes Shrinkage & 95% Clustered Bootstrap CIs
- Stage 5: Split-Half Reliability & Multi-Scenario Sensitivity Benchmarks
- Stage 6: Visualization Generation (8 Publication-Quality Figures)
- Stage 7: Methodology Report PDF (13 Pages)
- Stage 8: Interactive Offline Dashboard Data Export

Usage:
    python run_all.py
"""

import sys
import time
from pathlib import Path

# Ensure project root is in python path
ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))

from src.data import clean_and_prepare
from src.wp_model import train_wp_models
from src.pressure import compute_pressure_index, plot_pressure_separation, plot_example_chase
from src.baselines import train_expected_outcome_models
from src.ratings import generate_rankings, compute_ball_wpa
from src.reliability import evaluate_split_half_reliability, evaluate_predictive_check, run_sensitivity_benchmarks
from src.viz import plot_top10_cards
from src.report_generator import build_methodology_report
from src.export_dashboard_data import export_data


def run_pipeline():
    start_time = time.time()
    print("=" * 70)
    print("SupeRR Selector Season 2 — Round 1 Technical Pipeline Execution")
    print("Rajasthan Royals Analytics | Pressure Performance System")
    print("=" * 70)

    # 1. Stage 1: Data Cleaning & Audit
    t0 = time.time()
    print("\n>>> STAGE 1: Data Ingestion & Quality Audit")
    df, audit = clean_and_prepare(save_audit=True)
    print(f"    Completed in {time.time() - t0:.1f}s | {len(df):,} balls, {df['match_id'].nunique()} matches.")

    # 2. Stage 2: WP Model & Pressure Index
    t0 = time.time()
    print("\n>>> STAGE 2: Win Probability Modeling & Pressure Index")
    wp_results = train_wp_models(df)
    df['wp'] = wp_results['all_predictions']
    venue_par = wp_results['venue_par']
    df = df.merge(venue_par[['venue_id', 'match_format', 'venue_par_score']],
                  on=['venue_id', 'match_format'], how='left')
    df['venue_par_score'] = df['venue_par_score'].fillna(160.0)
    df['is_ipl'] = (df['match_format'] == 'T20').astype(int)
    df['chase_pressure'] = df['required_run_rate'] * (df['balls_remaining'] + 1).apply(
        lambda x: 0 if x <= 0 else float(__import__('numpy').log1p(x))
    )
    df['inn1_score_vs_par'] = 0.0

    df = compute_pressure_index(df, wp_results)
    plot_pressure_separation(df)
    plot_example_chase(df)
    print(f"    Completed in {time.time() - t0:.1f}s | High-pressure balls: {df['is_high_pressure'].sum():,}.")

    # 3. Stage 3: Expected Context Baselines
    t0 = time.time()
    print("\n>>> STAGE 3: Context Baselines (E[runs] & P(wicket))")
    df, baseline_metrics = train_expected_outcome_models(df)
    print(f"    Completed in {time.time() - t0:.1f}s | E[runs] RMSE: {baseline_metrics['runs_cv_rmse']:.4f}, P(wkt) AUC: {baseline_metrics['wkt_cv_auc']:.4f}.")

    # 4. Stage 4: Player Ratings & Shrinkage
    t0 = time.time()
    print("\n>>> STAGE 4: Player Pressure Ratings & Shrinkage")
    batters, bowlers = generate_rankings(df)
    print(f"    Completed in {time.time() - t0:.1f}s | Eligible: {batters['is_eligible'].sum()} batters, {bowlers['is_eligible'].sum()} bowlers.")

    # 5. Stage 5: Reliability & Sensitivity
    t0 = time.time()
    print("\n>>> STAGE 5: Reliability Benchmarks & Sensitivity")
    df_wpa = compute_ball_wpa(df)
    el_bat = set(batters[batters['is_eligible']]['striker_id'].unique())
    el_bowl = set(bowlers[bowlers['is_eligible']]['bowler_id'].unique())
    evaluate_split_half_reliability(df_wpa, el_bat, el_bowl)
    evaluate_predictive_check(df_wpa, el_bat, el_bowl)
    run_sensitivity_benchmarks(df_wpa, batters, bowlers)
    print(f"    Completed in {time.time() - t0:.1f}s | Sensitivity table generated.")

    # 6. Stage 6: Visualization
    t0 = time.time()
    print("\n>>> STAGE 6: Visualizations")
    plot_top10_cards()
    print(f"    Completed in {time.time() - t0:.1f}s | Top 10 figures saved.")

    # 7. Stage 7: PDF Methodology Report
    t0 = time.time()
    print("\n>>> STAGE 7: PDF Methodology Report Generation")
    build_methodology_report()
    print(f"    Completed in {time.time() - t0:.1f}s | Report compiled.")

    # 8. Stage 8: Dashboard JSON Export
    t0 = time.time()
    print("\n>>> STAGE 8: Dashboard Data Export")
    export_data()
    print(f"    Completed in {time.time() - t0:.1f}s | Offline JSON data synchronized.")

    print("\n" + "=" * 70)
    print(f"PIPELINE FULLY COMPLETE IN {time.time() - start_time:.1f}s!")
    print("=" * 70)


if __name__ == '__main__':
    run_pipeline()

