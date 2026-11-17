"""
ratings.py - Context-Adjusted Player Rating System under Pressure for SupeRR Selector S2.

Implements:
1. Batting Pressure Value (BPV) & Baseline:
   - Runs Above Expected (RAE)
   - Win Probability Added (WPA)
   - Dismissal Cost & Avoidance
   - Pressure Delta = Pressure Performance - Baseline
2. Bowling Pressure Value (BoPV) & Baseline:
   - Runs Saved Above Expected (RSAE)
   - Wicket Value Above Expected (WAE)
   - Bowler WPA
   - Pressure Delta = Pressure Performance - Baseline
3. Empirical-Bayes Shrinkage (Partial Pooling):
   - Prior estimated from eligible population
   - Shrinkage factor based on sample size and match variance
4. Clustered Bootstrap 95% Confidence Intervals (by match_id)
5. Consistency & Reliability Factor (match-level hit rate & stability)
6. Role Tagging & Competition Weighting (IPL vs T20I)
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Tuple, Dict, List
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import warnings

warnings.filterwarnings('ignore')

SEED = 42
OUTPUT_DIR = Path(r"D:\SupeRR\outputs")
FIG_DIR = OUTPUT_DIR / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)

# Eligibility thresholds determined from data distribution
MIN_HP_BALLS = 70
MIN_HP_MATCHES = 7


def compute_ball_wpa(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute ball-by-ball Win Probability Added (WPA) for the batting team.
    WPA = WP_after - WP_before.
    Pre-ball WP is in 'wp'.
    Next-ball WP within match and innings is post-ball WP.
    For the last ball of an innings, WP_after is 1.0 (if won) or 0.0 (if lost).
    """
    print("Computing ball-by-ball WPA...")
    df = df.sort_values(['match_id', 'innings', 'innings_ball_num']).copy()
    
    # Next ball's WP in same innings
    df['next_wp'] = df.groupby(['match_id', 'innings'])['wp'].shift(-1)
    
    # For last ball of innings:
    # If chasing (inn 2) and won -> 1.0; if chasing and lost -> 0.0
    # For innings 1 last ball, use the WP of the first ball of innings 2 (from defending perspective: 1 - wp_inn2)
    last_ball_mask = df['next_wp'].isna()
    inn2_mask = df['innings'] == 2
    
    df.loc[last_ball_mask & inn2_mask, 'next_wp'] = df.loc[last_ball_mask & inn2_mask, 'batting_team_won'].astype(float)
    df['next_wp'] = df['next_wp'].fillna(df['wp'])
    
    # WPA from batting team's perspective
    df['wpa'] = df['next_wp'] - df['wp']
    
    # Bowler's WPA is the negative of batting team WPA
    df['bowler_wpa'] = -df['wpa']
    
    return df


def calculate_player_pressure_metrics(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Compute raw performance metrics for batters and bowlers under high-pressure (HP)
    and ordinary/baseline conditions.
    """
    legal = df[df['is_legal_delivery']].copy()
    
    # ==================== BATTERS ====================
    print("Calculating batter performance profiles...")
    
    # Group by striker and pressure state
    bat_summary = legal.groupby(['striker_id', 'striker_name', 'is_high_pressure']).agg(
        balls=('is_legal_delivery', 'count'),
        matches=('match_id', 'nunique'),
        actual_runs=('batter_runs', 'sum'),
        exp_runs=('exp_runs', 'sum'),
        rae_total=('rae', 'sum'),
        wpa_total=('wpa', 'sum'),
        wickets_lost=('is_wicket', 'sum'),
        exp_wickets=('exp_wicket', 'sum'),
        fours=('is_four', 'sum'),
        sixes=('is_six', 'sum'),
        dots=('batter_runs', lambda x: (x == 0).sum()),
        ipl_balls=('is_ipl', 'sum'),
        t20i_balls=('is_ipl', lambda x: (x == 0).sum())
    ).reset_index()
    
    # Separate HP and Baseline
    bat_hp = bat_summary[bat_summary['is_high_pressure'] == 1].copy()
    bat_base = bat_summary[bat_summary['is_high_pressure'] == 0].copy()
    
    # Merge HP with player's own baseline
    batters = bat_hp.merge(
        bat_base[['striker_id', 'balls', 'actual_runs', 'exp_runs', 'rae_total', 'wpa_total', 'wickets_lost', 'exp_wickets']],
        on='striker_id',
        how='left',
        suffixes=('', '_base')
    )
    
    # Fill missing baseline with overall mean rates if very few baseline balls
    mean_base_rae = bat_base['rae_total'].sum() / bat_base['balls'].sum() * 100
    mean_base_wpa = bat_base['wpa_total'].sum() / bat_base['balls'].sum() * 100
    
    batters['balls_base'] = batters['balls_base'].fillna(0)
    batters['rae_rate_base'] = np.where(
        batters['balls_base'] >= 30,
        batters['rae_total_base'] / batters['balls_base'] * 100.0,
        mean_base_rae
    )
    batters['wpa_rate_base'] = np.where(
        batters['balls_base'] >= 30,
        batters['wpa_total_base'] / batters['balls_base'] * 100.0,
        mean_base_wpa
    )
    
    # High pressure rates (per 100 balls)
    batters['sr_hp'] = batters['actual_runs'] / batters['balls'] * 100.0
    batters['rae_per_100'] = batters['rae_total'] / batters['balls'] * 100.0
    batters['wpa_per_100'] = batters['wpa_total'] / batters['balls'] * 100.0
    # Dismissal avoidance: (E[wkt] - actual_wkt) per 100 balls
    batters['dismissal_avoidance_100'] = (batters['exp_wickets'] - batters['wickets_lost']) / batters['balls'] * 100.0
    
    # Combined Batting Pressure Value (BPV) per 100 balls:
    # 50% RAE efficiency, 35% WPA (scaled to run equivalent, ~1% WP ≈ 0.8 runs), 15% Dismissal Avoidance (~20 runs per wicket)
    batters['bpv_raw'] = (
        0.50 * batters['rae_per_100'] +
        0.35 * (batters['wpa_per_100'] * 8.0) +
        0.15 * (batters['dismissal_avoidance_100'] * 2.0)
    )
    
    # Batter's baseline score per 100 balls
    batters['bpv_base'] = 0.55 * batters['rae_rate_base'] + 0.45 * (batters['wpa_rate_base'] * 8.0)
    
    # Pressure Delta = HP performance minus own baseline
    batters['pressure_delta'] = batters['bpv_raw'] - batters['bpv_base']
    
    # Composite Batting Score: 65% Absolute Pressure Value + 35% Pressure Delta
    batters['score_composite'] = 0.65 * batters['bpv_raw'] + 0.35 * batters['pressure_delta']
    
    # Roles
    player_roles = df.groupby('striker_id')['batting_role'].agg(lambda x: x.mode().iloc[0] if len(x) > 0 else 'middle_order')
    batters['role'] = batters['striker_id'].map(player_roles).fillna('middle_order')
    
    
    # ==================== BOWLERS ====================
    print("Calculating bowler performance profiles...")
    
    bowl_summary = legal.groupby(['bowler_id', 'bowler_name', 'is_high_pressure']).agg(
        balls=('is_legal_delivery', 'count'),
        matches=('match_id', 'nunique'),
        runs_conceded=('bowler_runs_conceded', 'sum'),
        exp_runs=('exp_runs', 'sum'),
        rsae_total=('rsae', 'sum'),
        wpa_total=('bowler_wpa', 'sum'),
        wickets_taken=('is_bowler_wicket', 'sum'),
        exp_wickets=('exp_wicket', 'sum'),
        wae_total=('wae', 'sum'),
        dots=('bowler_runs_conceded', lambda x: (x == 0).sum()),
        ipl_balls=('is_ipl', 'sum'),
        t20i_balls=('is_ipl', lambda x: (x == 0).sum())
    ).reset_index()
    
    bowl_hp = bowl_summary[bowl_summary['is_high_pressure'] == 1].copy()
    bowl_base = bowl_summary[bowl_summary['is_high_pressure'] == 0].copy()
    
    bowlers = bowl_hp.merge(
        bowl_base[['bowler_id', 'balls', 'runs_conceded', 'exp_runs', 'rsae_total', 'wpa_total', 'wickets_taken', 'wae_total']],
        on='bowler_id',
        how='left',
        suffixes=('', '_base')
    )
    
    mean_base_rsae = bowl_base['rsae_total'].sum() / bowl_base['balls'].sum() * 100
    mean_base_bwpa = bowl_base['wpa_total'].sum() / bowl_base['balls'].sum() * 100
    
    bowlers['balls_base'] = bowlers['balls_base'].fillna(0)
    bowlers['rsae_rate_base'] = np.where(
        bowlers['balls_base'] >= 30,
        bowlers['rsae_total_base'] / bowlers['balls_base'] * 100.0,
        mean_base_rsae
    )
    bowlers['wpa_rate_base'] = np.where(
        bowlers['balls_base'] >= 30,
        bowlers['wpa_total_base'] / bowlers['balls_base'] * 100.0,
        mean_base_bwpa
    )
    
    # High pressure rates (per 100 balls)
    bowlers['econ_hp'] = bowlers['runs_conceded'] / (bowlers['balls'] / 6.0)
    bowlers['rsae_per_100'] = bowlers['rsae_total'] / bowlers['balls'] * 100.0
    bowlers['wpa_per_100'] = bowlers['wpa_total'] / bowlers['balls'] * 100.0
    bowlers['wae_per_100'] = bowlers['wae_total'] / bowlers['balls'] * 100.0
    bowlers['dot_pct_hp'] = bowlers['dots'] / bowlers['balls'] * 100.0
    
    # Combined Bowling Pressure Value (BoPV) per 100 balls:
    # 45% RSAE (runs saved), 35% WPA, 20% WAE (wickets above expected, 1 wkt ≈ 15 runs value)
    bowlers['bopv_raw'] = (
        0.45 * bowlers['rsae_per_100'] +
        0.35 * (bowlers['wpa_per_100'] * 8.0) +
        0.20 * (bowlers['wae_per_100'] * 15.0)
    )
    
    bowlers['bopv_base'] = 0.55 * bowlers['rsae_rate_base'] + 0.45 * (bowlers['wpa_rate_base'] * 8.0)
    bowlers['pressure_delta'] = bowlers['bopv_raw'] - bowlers['bopv_base']
    
    # Composite Bowling Score
    bowlers['score_composite'] = 0.65 * bowlers['bopv_raw'] + 0.35 * bowlers['pressure_delta']
    
    # Roles
    bowler_roles = df.groupby('bowler_id')['bowling_role'].agg(lambda x: x.mode().iloc[0] if len(x) > 0 else 'middle')
    bowlers['role'] = bowlers['bowler_id'].map(bowler_roles).fillna('middle')
    
    return batters, bowlers


def apply_empirical_bayes_shrinkage(df: pd.DataFrame, score_col: str, n_col: str,
                                    match_col: str) -> pd.DataFrame:
    """
    Applies Empirical-Bayes shrinkage (partial pooling) to player scores.
    Estimates prior mean (mu0) and between-player variance (tau2).
    Shrinks smaller sample players toward the prior mean.
    """
    data = df.copy()
    y = data[score_col].values
    n = data[n_col].values
    
    # Estimate standard error for each player: s_i = sigma / sqrt(n_i)
    # Standard deviation of ball-level impact in population ~ 30.0
    sigma_est = 32.0
    s_i2 = (sigma_est ** 2) / n
    
    mu0 = np.average(y, weights=n)
    
    # Total variance
    var_total = np.var(y, ddof=1)
    mean_s_i2 = np.mean(s_i2)
    
    # Between-player variance tau^2
    tau2 = max(1e-4, var_total - mean_s_i2)
    
    # Shrinkage weight B_i = tau2 / (tau2 + s_i2)
    shrinkage_factor = tau2 / (tau2 + s_i2)
    
    data['shrinkage_weight'] = shrinkage_factor
    data['score_shrunk'] = shrinkage_factor * y + (1.0 - shrinkage_factor) * mu0
    
    return data


def compute_match_cluster_bootstrap_intervals(df_balls: pd.DataFrame, player_df: pd.DataFrame,
                                             is_batter: bool, n_boot: int = 400) -> pd.DataFrame:
    """
    Compute 95% Confidence Intervals via Match-Level Block Bootstrap.
    Resamples match_ids with replacement to preserve intra-match correlation.
    """
    print(f"Computing 95% match-clustered bootstrap intervals ({'Batters' if is_batter else 'Bowlers'})...")
    rng = np.random.RandomState(SEED)
    
    # Pre-aggregate player-match level stats
    hp_balls = df_balls[(df_balls['is_high_pressure'] == 1) & (df_balls['is_legal_delivery'])].copy()
    
    id_col = 'striker_id' if is_batter else 'bowler_id'
    
    if is_batter:
        pm = hp_balls.groupby([id_col, 'match_id']).agg(
            balls=('is_legal_delivery', 'count'),
            rae=('rae', 'sum'),
            wpa=('wpa', 'sum'),
            wkt_diff=('exp_wicket', lambda x: x.sum() - hp_balls.loc[x.index, 'is_wicket'].sum())
        ).reset_index()
    else:
        pm = hp_balls.groupby([id_col, 'match_id']).agg(
            balls=('is_legal_delivery', 'count'),
            rsae=('rsae', 'sum'),
            wpa=('bowler_wpa', 'sum'),
            wae=('wae', 'sum')
        ).reset_index()
        
    all_matches = hp_balls['match_id'].unique()
    n_matches = len(all_matches)
    
    # Target eligible player IDs
    target_ids = set(player_df[player_df['is_eligible']][id_col].unique())
    pm_filtered = pm[pm[id_col].isin(target_ids)]
    
    # Dictionary of match_id -> records for fast resampling
    player_match_dict = {}
    for p_id, group in pm_filtered.groupby(id_col):
        player_match_dict[p_id] = group.set_index('match_id')
        
    ci_lower = {}
    ci_upper = {}
    
    for p_id in target_ids:
        p_data = player_match_dict.get(p_id, None)
        if p_data is None or len(p_data) < 3:
            ci_lower[p_id] = player_df.loc[player_df[id_col] == p_id, 'score_shrunk'].values[0] - 12.0
            ci_upper[p_id] = player_df.loc[player_df[id_col] == p_id, 'score_shrunk'].values[0] + 12.0
            continue
            
        p_match_ids = p_data.index.values
        n_p_matches = len(p_match_ids)
        
        boot_scores = []
        for _ in range(n_boot):
            sampled_m = rng.choice(p_match_ids, size=n_p_matches, replace=True)
            sub = p_data.loc[sampled_m]
            b_tot = sub['balls'].sum()
            if b_tot == 0:
                continue
            if is_batter:
                val = 0.50 * (sub['rae'].sum() / b_tot * 100) + 0.35 * (sub['wpa'].sum() / b_tot * 800) + 0.15 * (sub['wkt_diff'].sum() / b_tot * 200)
            else:
                val = 0.45 * (sub['rsae'].sum() / b_tot * 100) + 0.35 * (sub['wpa'].sum() / b_tot * 800) + 0.20 * (sub['wae'].sum() / b_tot * 300)
            boot_scores.append(val)
            
        if len(boot_scores) > 20:
            ci_lower[p_id] = float(np.percentile(boot_scores, 2.5))
            ci_upper[p_id] = float(np.percentile(boot_scores, 97.5))
        else:
            base_val = player_df.loc[player_df[id_col] == p_id, 'score_shrunk'].values[0]
            ci_lower[p_id] = base_val - 10.0
            ci_upper[p_id] = base_val + 10.0
            
    player_df['ci_lower'] = player_df[id_col].map(ci_lower)
    player_df['ci_upper'] = player_df[id_col].map(ci_upper)
    
    return player_df


def compute_consistency_and_final_rankings(df_balls: pd.DataFrame, player_df: pd.DataFrame,
                                          is_batter: bool) -> pd.DataFrame:
    """
    Computes match-by-match consistency metric:
    - Hit Rate: proportion of HP matches with positive impact (beating expectation)
    - Match-to-match standard deviation
    - Final Rating = Shrunk Score * Consistency Multiplier
    """
    print(f"Computing match consistency metrics ({'Batters' if is_batter else 'Bowlers'})...")
    hp = df_balls[(df_balls['is_high_pressure'] == 1) & (df_balls['is_legal_delivery'])].copy()
    id_col = 'striker_id' if is_batter else 'bowler_id'
    
    if is_batter:
        match_impact = hp.groupby([id_col, 'match_id']).agg(
            match_impact=('rae', 'sum'),
            match_balls=('is_legal_delivery', 'count')
        ).reset_index()
    else:
        match_impact = hp.groupby([id_col, 'match_id']).agg(
            match_impact=('rsae', 'sum'),
            match_balls=('is_legal_delivery', 'count')
        ).reset_index()
        
    consistency = match_impact.groupby(id_col).agg(
        total_hp_matches=('match_id', 'count'),
        positive_matches=('match_impact', lambda x: (x > 0).sum()),
        impact_std=('match_impact', lambda x: x.std() if len(x) > 1 else 5.0)
    ).reset_index()
    
    consistency['hit_rate'] = consistency['positive_matches'] / consistency['total_hp_matches']
    consistency['impact_std'] = consistency['impact_std'].fillna(5.0)
    
    player_df = player_df.merge(consistency[[id_col, 'hit_rate', 'impact_std']], on=id_col, how='left')
    player_df['hit_rate'] = player_df['hit_rate'].fillna(0.50)
    player_df['impact_std'] = player_df['impact_std'].fillna(5.0)
    
    # Consistency factor: strictly enforces Section 4.4b requirement:
    # "Final reliability = good impact AND low variance and decent hit-rate (>50%)"
    # Players who fail to beat expectation in >=50% of matches are penalized heavily.
    std_median = player_df['impact_std'].median()
    hit_rate_penalty = np.where(player_df['hit_rate'] < 0.50, 0.70 * (player_df['hit_rate'] / 0.50), 1.0 + 0.35 * (player_df['hit_rate'] - 0.50))
    variance_penalty = np.exp(-0.15 * (player_df['impact_std'] / std_median - 1.0).clip(lower=0))
    player_df['consistency_factor'] = hit_rate_penalty * variance_penalty
    
    # Competition strength adjustment: IPL vs T20I
    # Scale IPL balls slightly (1.05x density factor) to reflect supreme concentration of bowling talent
    ipl_ratio = player_df['ipl_balls'] / (player_df['balls'] + 1e-6)
    player_df['comp_multiplier'] = 1.0 + 0.04 * ipl_ratio
    
    # Final Rating
    player_df['final_pressure_rating'] = (
        player_df['score_shrunk'] * player_df['consistency_factor'] * player_df['comp_multiplier']
    )
    
    # Rank eligible players
    eligible = player_df[player_df['is_eligible']].copy()
    eligible = eligible.sort_values('final_pressure_rating', ascending=False).reset_index(drop=True)
    eligible['rank'] = range(1, len(eligible) + 1)
    
    # Merge ranks back
    player_df = player_df.merge(eligible[[id_col, 'rank']], on=id_col, how='left')
    player_df['rank'] = player_df['rank'].fillna(999).astype(int)
    
    return player_df


def generate_rankings(df_with_baselines: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Execute complete rating, shrinkage, bootstrap, and ranking pipeline."""
    print("\n" + "=" * 60)
    print("STAGE 4: Player Pressure Ratings & Empirical-Bayes Shrinkage")
    print("=" * 60)
    
    df_wpa = compute_ball_wpa(df_with_baselines)
    batters, bowlers = calculate_player_pressure_metrics(df_wpa)
    
    # Eligibility filters
    batters['is_eligible'] = (batters['balls'] >= MIN_HP_BALLS) & (batters['matches'] >= MIN_HP_MATCHES)
    bowlers['is_eligible'] = (bowlers['balls'] >= MIN_HP_BALLS) & (bowlers['matches'] >= MIN_HP_MATCHES)
    
    print(f"Eligible batters: {batters['is_eligible'].sum()} / {len(batters)}")
    print(f"Eligible bowlers: {bowlers['is_eligible'].sum()} / {len(bowlers)}")
    
    # Empirical Bayes Shrinkage
    batters = apply_empirical_bayes_shrinkage(batters, 'score_composite', 'balls', 'matches')
    bowlers = apply_empirical_bayes_shrinkage(bowlers, 'score_composite', 'balls', 'matches')
    
    # Bootstrap intervals
    batters = compute_match_cluster_bootstrap_intervals(df_wpa, batters, is_batter=True)
    bowlers = compute_match_cluster_bootstrap_intervals(df_wpa, bowlers, is_batter=False)
    
    # Consistency and final ranking
    batters = compute_consistency_and_final_rankings(df_wpa, batters, is_batter=True)
    bowlers = compute_consistency_and_final_rankings(df_wpa, bowlers, is_batter=False)
    
    # Export full and Top-10 tables
    top10_batters = batters[batters['rank'] <= 10].sort_values('rank').copy()
    top10_bowlers = bowlers[bowlers['rank'] <= 10].sort_values('rank').copy()
    
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    batters.to_csv(OUTPUT_DIR / 'batters_ranking.csv', index=False)
    bowlers.to_csv(OUTPUT_DIR / 'bowlers_ranking.csv', index=False)
    top10_batters.to_csv(OUTPUT_DIR / 'top10_batters.csv', index=False)
    top10_bowlers.to_csv(OUTPUT_DIR / 'top10_bowlers.csv', index=False)
    
    print(f"Rankings successfully written to {OUTPUT_DIR}")
    return batters, bowlers


if __name__ == '__main__':
    from src.data import clean_and_prepare
    from src.wp_model import train_wp_models
    from src.pressure import compute_pressure_index
    from src.baselines import train_expected_outcome_models
    
    df, _ = clean_and_prepare(save_audit=False)
    wp_results = train_wp_models(df)
    
    df['wp'] = wp_results['all_predictions']
    venue_par = wp_results['venue_par']
    df = df.merge(venue_par[['venue_id', 'match_format', 'venue_par_score']],
                  on=['venue_id', 'match_format'], how='left')
    df['venue_par_score'] = df['venue_par_score'].fillna(160.0)
    df['is_ipl'] = (df['match_format'] == 'T20').astype(int)
    df['chase_pressure'] = df['required_run_rate'] * np.log1p(df['balls_remaining'])
    df['inn1_score_vs_par'] = np.where(
        df['innings'] == 1,
        df['cum_total_runs'] - (df['venue_par_score'] * df['legal_balls_before'] / 120.0),
        0.0
    )
    
    df = compute_pressure_index(df, wp_results)
    df, _ = train_expected_outcome_models(df)
    
    batters, bowlers = generate_rankings(df)
    
    print("\n" + "=" * 50)
    print("TOP 10 BATTERS UNDER PRESSURE")
    print("=" * 50)
    top10_b = batters[batters['rank'] <= 10].sort_values('rank')
    for _, r in top10_b.iterrows():
        print(f"#{r['rank']:2d} | {r['striker_name']:<22} | Role: {r['role']:<12} | Rating: {r['final_pressure_rating']:5.2f} (95% CI: [{r['ci_lower']:4.1f}, {r['ci_upper']:4.1f}]) | Balls: {r['balls']:3d} | SR: {r['sr_hp']:5.1f}")
        
    print("\n" + "=" * 50)
    print("TOP 10 BOWLERS UNDER PRESSURE")
    print("=" * 50)
    top10_bw = bowlers[bowlers['rank'] <= 10].sort_values('rank')
    for _, r in top10_bw.iterrows():
        print(f"#{r['rank']:2d} | {r['bowler_name']:<22} | Role: {r['role']:<12} | Rating: {r['final_pressure_rating']:5.2f} (95% CI: [{r['ci_lower']:4.1f}, {r['ci_upper']:4.1f}]) | Balls: {r['balls']:3d} | Econ: {r['econ_hp']:4.2f}")
