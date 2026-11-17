"""
pressure.py - Pressure Index computation for SupeRR Selector S2.

Computes ball-by-ball Pressure Index from:
1. Leverage: expected absolute WP change from possible next-ball outcomes
2. Closeness: how contested the game is (WP near 0.5)

Vectorized, robust, and zero look-ahead leakage.
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


def compute_outcome_frequencies(df: pd.DataFrame) -> Dict:
    """Compute actual per-ball outcome frequencies from the data."""
    legal = df[df['is_legal_delivery']].copy()
    n = len(legal)
    
    freqs = {}
    freqs[0] = int(((legal['batter_runs'] == 0) & (~legal['is_wicket'])).sum()) / n
    freqs[1] = int(((legal['batter_runs'] == 1) & (~legal['is_wicket'])).sum()) / n
    freqs[2] = int(((legal['batter_runs'] == 2) & (~legal['is_wicket'])).sum()) / n
    freqs[3] = int(((legal['batter_runs'] == 3) & (~legal['is_wicket'])).sum()) / n
    freqs[4] = int(((legal['batter_runs'] >= 4) & (legal['is_six'] != True) & (~legal['is_wicket'])).sum()) / n
    freqs[6] = int(((legal['is_six'] == True) & (~legal['is_wicket'])).sum()) / n
    freqs['wicket'] = int(legal['is_wicket'].sum()) / n
    
    # Normalize
    total = sum(freqs.values())
    freqs = {k: v/total for k, v in freqs.items()}
    
    print(f"  Outcome frequencies: {', '.join(f'{k}={v:.3f}' for k, v in freqs.items())}")
    return freqs


def predict_wp_batch(model, scaler, X: np.ndarray, is_lr: bool) -> np.ndarray:
    """Safely predict win probability for any model type."""
    X_clean = np.nan_to_num(X, nan=0.0, posinf=100.0, neginf=-100.0)
    if is_lr:
        X_scaled = scaler.transform(X_clean)
        return model.predict_proba(X_scaled)[:, 1]
    else:
        return model.predict(X_clean)


def compute_leverage_vectorized(df: pd.DataFrame, wp_model, scaler, feature_cols: list,
                                outcome_freqs: Dict, is_lr: bool) -> np.ndarray:
    """
    Compute leverage index for each ball using vectorized NumPy operations.
    Leverage = E[|WP_after - WP_before|] over distribution of possible outcomes.
    """
    n = len(df)
    leverage = np.zeros(n, dtype=np.float64)
    current_wp = df['wp'].values.astype(np.float64)
    
    # Base feature vectors
    innings = df['innings'].values.astype(np.float32)
    is_chase = (innings == 2).astype(np.float32)
    chase_target = df['chase_target'].values.astype(np.float32)
    total_balls = df['total_balls_innings'].values.astype(np.float32)
    venue_par = df['venue_par_score'].fillna(160.0).values.astype(np.float32)
    is_knockout = df['is_knockout'].values.astype(np.float32)
    is_ipl = df['is_ipl'].values.astype(np.float32)
    
    base_legal_balls = df['legal_balls_before'].values.astype(np.float32)
    base_wickets_in_hand = df['wickets_in_hand'].values.astype(np.float32)
    base_cum_runs = df['cum_total_runs'].values.astype(np.float32)
    
    col_idx = {name: i for i, name in enumerate(feature_cols)}
    
    # For each outcome (0, 1, 2, 3, 4, 6, wicket)
    for outcome, prob in outcome_freqs.items():
        if prob < 0.001:
            continue
        
        # 1 legal ball consumed
        hypo_legal_balls = base_legal_balls + 1.0
        hypo_balls_rem = np.maximum(0.0, total_balls - hypo_legal_balls)
        
        if outcome == 'wicket':
            hypo_wickets = np.maximum(0.0, base_wickets_in_hand - 1.0)
            hypo_runs = base_cum_runs.copy()
        else:
            hypo_wickets = base_wickets_in_hand.copy()
            hypo_runs = base_cum_runs + float(outcome)
            
        hypo_resources = hypo_wickets * hypo_balls_rem
        
        overs_bowled = np.maximum(hypo_legal_balls / 6.0, 1e-4)
        hypo_crr = hypo_runs / overs_bowled
        
        hypo_runs_needed = np.where(is_chase == 1.0, np.maximum(0.0, chase_target - hypo_runs), 0.0)
        overs_rem = np.maximum(hypo_balls_rem / 6.0, 1e-4)
        hypo_rrr = np.where((is_chase == 1.0) & (hypo_balls_rem > 0), hypo_runs_needed / overs_rem, 0.0)
        hypo_chase_press = hypo_rrr * np.log1p(hypo_balls_rem)
        
        hypo_inn1_par = np.where(innings == 1.0, hypo_runs - (venue_par * hypo_legal_balls / 120.0), 0.0)
        
        # Construct feature matrix X_hypo
        X_hypo = np.zeros((n, len(feature_cols)), dtype=np.float32)
        X_hypo[:, col_idx['innings']] = innings
        X_hypo[:, col_idx['balls_remaining']] = hypo_balls_rem
        X_hypo[:, col_idx['wickets_in_hand']] = hypo_wickets
        X_hypo[:, col_idx['cum_total_runs']] = hypo_runs
        X_hypo[:, col_idx['current_run_rate']] = hypo_crr
        X_hypo[:, col_idx['is_chase']] = is_chase
        X_hypo[:, col_idx['chase_target']] = chase_target
        X_hypo[:, col_idx['runs_needed']] = hypo_runs_needed
        X_hypo[:, col_idx['required_run_rate']] = hypo_rrr
        X_hypo[:, col_idx['resources']] = hypo_resources
        X_hypo[:, col_idx['venue_par_score']] = venue_par
        X_hypo[:, col_idx['inn1_score_vs_par']] = hypo_inn1_par
        X_hypo[:, col_idx['is_knockout']] = is_knockout
        X_hypo[:, col_idx['is_ipl']] = is_ipl
        X_hypo[:, col_idx['chase_pressure']] = hypo_chase_press
        
        # Predict WP
        wp_hypo = predict_wp_batch(wp_model, scaler, X_hypo, is_lr)
        
        # Accumulate expected change
        leverage += prob * np.abs(wp_hypo - current_wp)
        
    return leverage


def compute_closeness(df: pd.DataFrame) -> np.ndarray:
    """
    Compute closeness/state tension score.
    Closeness = 1 - |WP - 0.5| * 2 (normalized to [0, 1]).
    Includes chase tension when required run rate is competitive.
    """
    wp = df['wp'].values
    closeness = 1.0 - np.abs(wp - 0.5) * 2.0
    closeness = np.clip(closeness, 0.0, 1.0)
    
    is_chase = (df['innings'].values == 2)
    rrr = df['required_run_rate'].values
    crr = df['current_run_rate'].values
    balls_rem = df['balls_remaining'].values
    
    # Tension peaks when game is tight in the 2nd half of chase
    chase_tension = np.where(
        is_chase & (rrr > 4.0) & (rrr < 16.0) & (balls_rem < 60),
        np.exp(-0.5 * ((rrr - 9.0) / 4.0) ** 2),
        0.0
    )
    
    combined = closeness + 0.25 * chase_tension
    max_val = np.max(combined)
    if max_val > 0:
        combined = combined / max_val
    return np.clip(combined, 0.0, 1.0)


def compute_pressure_index(df: pd.DataFrame, wp_results: Dict) -> pd.DataFrame:
    """
    Compute the main Pressure Index and alternative definitions.
    PI = 0.7 * leverage_normalized + 0.3 * closeness_normalized
    """
    print("\n" + "=" * 60)
    print("STAGE 2: Computing Pressure Index")
    print("=" * 60)
    
    result = df.copy()
    
    chosen = wp_results['chosen_model']
    is_lr = (chosen == 'lr')
    wp_model = wp_results['lr']['model'] if is_lr else wp_results['lgb']['model']
    scaler = wp_results['lr']['scaler'] if is_lr else None
    feature_cols = wp_results['feature_cols']
    
    print(f"Using {chosen.upper()} model for leverage estimation.")
    outcome_freqs = compute_outcome_frequencies(result)
    
    print("Computing vectorized leverage...")
    leverage = compute_leverage_vectorized(result, wp_model, scaler, feature_cols, outcome_freqs, is_lr)
    result['leverage'] = leverage
    
    print("Computing state closeness...")
    closeness = compute_closeness(result)
    result['closeness'] = closeness
    
    # Normalization
    lev_min, lev_max = np.percentile(leverage, 1), np.percentile(leverage, 99)
    lev_norm = np.clip((leverage - lev_min) / (lev_max - lev_min + 1e-6), 0.0, 1.0)
    
    # Pressure Index: 70% Leverage, 30% Closeness
    result['pressure_index'] = 0.70 * lev_norm + 0.30 * closeness
    
    # Data-driven thresholds
    q50 = result['pressure_index'].quantile(0.50)
    q75 = result['pressure_index'].quantile(0.75)
    
    result['pressure_bucket'] = pd.cut(
        result['pressure_index'],
        bins=[-np.inf, q50, q75, np.inf],
        labels=['ordinary', 'moderate', 'high']
    )
    result['is_high_pressure'] = (result['pressure_bucket'] == 'high').astype(int)
    
    print(f"PI Distribution: median={q50:.4f}, Q75={q75:.4f}, max={result['pressure_index'].max():.4f}")
    print(f"High-pressure deliveries: {result['is_high_pressure'].sum():,} ({result['is_high_pressure'].mean()*100:.1f}%)")
    
    # Alternative PI definitions for sensitivity analysis
    # Alt 1: Death overs in a close chase (overs 16-20, WP between 0.20 and 0.80)
    result['pi_alt_death_chase'] = (
        (result['innings'] == 2) &
        (result['overid'] >= 16) &
        (result['wp'] >= 0.20) &
        (result['wp'] <= 0.80)
    ).astype(int)
    
    # Alt 2: Top 20% PI
    p80 = result['pressure_index'].quantile(0.80)
    result['pi_alt_top20'] = (result['pressure_index'] >= p80).astype(int)
    
    # Alt 3: Required-rate pressure (> 10 RRR with <= 36 balls left in chase)
    result['pi_alt_rrr'] = (
        (result['innings'] == 2) &
        (result['required_run_rate'] >= 9.5) &
        (result['balls_remaining'] <= 42) &
        (result['wickets_in_hand'] >= 2)
    ).astype(int)
    
    return result


def plot_pressure_separation(df: pd.DataFrame) -> None:
    """Generate mandatory validation plots proving PI separates situations cleanly."""
    print("Generating pressure separation charts...")
    legal = df[df['is_legal_delivery']].copy()
    legal['is_dot'] = (legal['batter_runs'] == 0) & (~legal['is_wicket'])
    
    fig, axes = plt.subplots(2, 3, figsize=(16, 10))
    colors = {'ordinary': '#1A3667', 'moderate': '#5A6B82', 'high': '#E63894'}
    
    # 1. Scoring rate (Runs per 100 balls)
    ax = axes[0, 0]
    sr_bucket = legal.groupby('pressure_bucket', observed=True)['batter_runs'].mean() * 100
    bars = ax.bar(['Ordinary (Q0-50)', 'Moderate (Q50-75)', 'High PI (Top 25%)'], sr_bucket.values,
                  color=[colors['ordinary'], colors['moderate'], colors['high']], width=0.55)
    ax.set_ylabel('Runs per 100 balls (SR equivalent)', fontsize=11)
    ax.set_title('Scoring Rate Under Pressure', fontweight='bold', fontsize=12)
    ax.grid(axis='y', alpha=0.3)
    for b in bars:
        ax.text(b.get_x() + b.get_width()/2, b.get_height() + 1.5, f"{b.get_height():.1f}", ha='center', fontweight='bold')
    ax.set_ylim(0, max(sr_bucket.values) * 1.15)
    
    # 2. Wicket rate (%)
    ax = axes[0, 1]
    wr_bucket = legal.groupby('pressure_bucket', observed=True)['is_wicket'].mean() * 100
    bars = ax.bar(['Ordinary', 'Moderate', 'High PI'], wr_bucket.values,
                  color=[colors['ordinary'], colors['moderate'], colors['high']], width=0.55)
    ax.set_ylabel('Wickets per 100 balls (%)', fontsize=11)
    ax.set_title('Wicket Rate Under Pressure', fontweight='bold', fontsize=12)
    ax.grid(axis='y', alpha=0.3)
    for b in bars:
        ax.text(b.get_x() + b.get_width()/2, b.get_height() + 0.2, f"{b.get_height():.2f}%", ha='center', fontweight='bold')
    ax.set_ylim(0, max(wr_bucket.values) * 1.25)
    
    # 3. Dot ball percentage (%)
    ax = axes[0, 2]
    dot_bucket = legal.groupby('pressure_bucket', observed=True)['is_dot'].mean() * 100
    bars = ax.bar(['Ordinary', 'Moderate', 'High PI'], dot_bucket.values,
                  color=[colors['ordinary'], colors['moderate'], colors['high']], width=0.55)
    ax.set_ylabel('Dot Ball Rate (%)', fontsize=11)
    ax.set_title('Dot Ball Percentage by Pressure Tier', fontweight='bold', fontsize=12)
    ax.grid(axis='y', alpha=0.3)
    for b in bars:
        ax.text(b.get_x() + b.get_width()/2, b.get_height() + 0.8, f"{b.get_height():.1f}%", ha='center', fontweight='bold')
    ax.set_ylim(0, max(dot_bucket.values) * 1.15)
    
    # 4. PI by Over of Innings
    ax = axes[1, 0]
    pi_over = legal.groupby(['overid', 'innings'])['pressure_index'].mean().unstack()
    ax.plot(pi_over.index, pi_over[1], 'o-', color='#1A3667', linewidth=2, label='Innings 1 (Defending/Setting)')
    if 2 in pi_over.columns:
        ax.plot(pi_over.index, pi_over[2], 's-', color='#E63894', linewidth=2.5, label='Innings 2 (Chasing)')
    ax.set_xlabel('Over Number', fontsize=11)
    ax.set_ylabel('Mean Pressure Index', fontsize=11)
    ax.set_title('Pressure Progression Across Overs', fontweight='bold', fontsize=12)
    ax.legend(frameon=True)
    ax.grid(True, alpha=0.3)
    
    # 5. Format comparison: IPL vs T20I
    ax = axes[1, 1]
    format_comp = legal.groupby(['match_format', 'pressure_bucket'], observed=True)['batter_runs'].mean() * 100
    format_comp = format_comp.unstack(level=0)
    x = np.arange(len(format_comp))
    width = 0.35
    ax.bar(x - width/2, format_comp['T20'], width, label='IPL (T20)', color='#1A3667', alpha=0.9)
    ax.bar(x + width/2, format_comp['T20I'], width, label='T20I', color='#E63894', alpha=0.9)
    ax.set_xticks(x)
    ax.set_xticklabels(['Ordinary', 'Moderate', 'High PI'])
    ax.set_ylabel('Runs per 100 balls', fontsize=11)
    ax.set_title('Scoring Rate: IPL vs T20I', fontweight='bold', fontsize=12)
    ax.legend()
    ax.grid(axis='y', alpha=0.3)
    
    # 6. Pressure Distribution density
    ax = axes[1, 2]
    ax.hist(legal[legal['innings']==1]['pressure_index'], bins=40, density=True, alpha=0.5, color='#1A3667', label='1st Innings')
    ax.hist(legal[legal['innings']==2]['pressure_index'], bins=40, density=True, alpha=0.5, color='#E63894', label='2nd Innings')
    ax.axvline(legal['pressure_index'].quantile(0.75), color='#E63894', linestyle='--', linewidth=1.5, label='Q75 Cutoff')
    ax.set_xlabel('Pressure Index', fontsize=11)
    ax.set_ylabel('Density', fontsize=11)
    ax.set_title('Pressure Index Distribution', fontweight='bold', fontsize=12)
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    plt.suptitle('Pressure Index (PI) Empirical Validation: Separation of Match Realities',
                 fontsize=15, fontweight='bold', y=0.99)
    plt.tight_layout()
    chart_path = FIG_DIR / 'pressure_separation.png'
    plt.savefig(chart_path, dpi=200, bbox_inches='tight')
    plt.close()
    print(f"  Validation chart saved: {chart_path}")


def plot_example_chase(df: pd.DataFrame) -> None:
    """Generate ball-by-ball plot of a thrilling close chase."""
    print("Generating example chase case-study plot...")
    inn2 = df[df['innings'] == 2].copy()
    match_pi = inn2.groupby('match_id').agg(
        mean_pi=('pressure_index', 'mean'),
        balls=('innings_ball_num', 'count'),
        knockout=('is_knockout', 'first')
    ).reset_index()
    # Find match with high mean PI and > 100 balls
    qualifying = match_pi[(match_pi['balls'] >= 110) & (match_pi['mean_pi'] > 0.40)]
    if len(qualifying) == 0:
        qualifying = match_pi[match_pi['balls'] >= 100].sort_values('mean_pi', ascending=False)
    
    target_match_id = qualifying.sort_values('mean_pi', ascending=False).iloc[0]['match_id']
    match_balls = df[(df['match_id'] == target_match_id) & (df['innings'] == 2)].sort_values('innings_ball_num')
    
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 7), sharex=True, gridspec_kw={'height_ratios': [2, 1.2]})
    
    x = np.arange(len(match_balls))
    wp = match_balls['wp'].values
    pi = match_balls['pressure_index'].values
    q75 = df['pressure_index'].quantile(0.75)
    
    # WP panel
    ax1.plot(x, wp, color='#1A3667', linewidth=2.5, label='Chasing Team Win Probability')
    ax1.axhline(0.5, color='gray', linestyle=':', alpha=0.7, label='Even Contest (50%)')
    ax1.fill_between(x, wp, 0.5, where=(wp >= 0.5), color='#1A3667', alpha=0.15)
    ax1.fill_between(x, wp, 0.5, where=(wp < 0.5), color='#E63894', alpha=0.15)
    ax1.set_ylabel('Win Probability', fontsize=11, fontweight='bold')
    ax1.set_ylim(-0.05, 1.05)
    ax1.grid(True, alpha=0.3)
    ax1.legend(loc='upper left')
    
    # Mark wickets
    wkts = np.where(match_balls['is_wicket'].values == True)[0]
    if len(wkts) > 0:
        ax1.scatter(wkts, wp[wkts], color='#E63894', s=60, zorder=5, label='Wicket Fallen', marker='X')
        ax1.legend(loc='upper left')
        
    ax1.set_title(f'Ball-by-Ball Win Probability & Pressure Dynamics — Match #{int(target_match_id)}',
                  fontweight='bold', fontsize=13)
    
    # PI panel
    bar_colors = ['#E63894' if p >= q75 else '#1A3667' for p in pi]
    ax2.bar(x, pi, color=bar_colors, width=0.8, alpha=0.85)
    ax2.axhline(q75, color='#E63894', linestyle='--', linewidth=1.5, label='High Pressure Threshold (Q75)')
    ax2.set_xlabel('Balls Bowled in Chase', fontsize=11, fontweight='bold')
    ax2.set_ylabel('Pressure Index (PI)', fontsize=11, fontweight='bold')
    ax2.set_ylim(0, 1.05)
    ax2.grid(True, alpha=0.3)
    ax2.legend(loc='upper left')
    
    plt.tight_layout()
    chart_path = FIG_DIR / 'example_chase_wp_pi.png'
    plt.savefig(chart_path, dpi=200, bbox_inches='tight')
    plt.close()
    print(f"  Chase plot saved: {chart_path}")


if __name__ == '__main__':
    from src.data import clean_and_prepare
    from src.wp_model import train_wp_models
    
    df, audit = clean_and_prepare(save_audit=False)
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
    plot_pressure_separation(df)
    plot_example_chase(df)
