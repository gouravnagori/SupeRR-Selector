"""
baselines.py - Expected-Outcome Baselines (E[runs] and P(wicket)) for SupeRR Selector S2.

Trains context-adjusted baseline models across ALL balls:
1. E[runs]: Expected runs off the bat given pre-ball context.
2. P(wicket): Probability of a wicket given pre-ball context.

Context features:
- Match state: phase, wickets in hand, balls left, innings, venue par score, format (IPL vs T20I)
- Matchup characteristics: batter handedness (RHB/LHB), bowler type (pace/spin, delivery style)
- Team quality: leave-one-out opponent bowling strength and batting strength

Player identities are strictly excluded to avoid absorbing individual player skill.
Evaluated using GroupKFold (by match_id) with 5 folds.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Tuple, Dict, List
import pickle
import warnings
import lightgbm as lgb
from sklearn.model_selection import GroupKFold
from sklearn.metrics import mean_squared_error, mean_absolute_error, log_loss, roc_auc_score, brier_score_loss
from sklearn.calibration import calibration_curve
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

warnings.filterwarnings('ignore')

SEED = 42
OUTPUT_DIR = Path(r"D:\SupeRR\outputs")
FIG_DIR = OUTPUT_DIR / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)


def compute_leave_one_out_team_strengths(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute leave-one-out team bowling and batting strength.
    For each match, strength is computed from all OTHER matches played by the team.
    Shrunk toward format mean for teams with few matches.
    """
    print("Computing leave-one-out team strengths...")
    legal = df[df['is_legal_delivery']].copy()
    
    # Match-level aggregates per team
    bowl_match = legal.groupby(['bowling_team_id', 'match_id', 'match_format']).agg(
        runs_conceded=('bowler_runs_conceded', 'sum'),
        wkts_taken=('is_bowler_wicket', 'sum'),
        balls_bowled=('is_legal_delivery', 'count')
    ).reset_index()
    
    bat_match = legal.groupby(['batting_team_id', 'match_id', 'match_format']).agg(
        runs_scored=('batter_runs', 'sum'),
        balls_faced=('is_legal_delivery', 'count')
    ).reset_index()
    
    # Global format averages
    global_bowl_econ = legal.groupby('match_format')['bowler_runs_conceded'].mean().to_dict()
    global_bowl_wkt = legal.groupby('match_format')['is_bowler_wicket'].mean().to_dict()
    global_bat_sr = legal.groupby('match_format')['batter_runs'].mean().to_dict()
    
    # Team totals across all matches
    team_bowl_tot = bowl_match.groupby('bowling_team_id').agg(
        tot_runs=('runs_conceded', 'sum'),
        tot_wkts=('wkts_taken', 'sum'),
        tot_balls=('balls_bowled', 'sum'),
        matches=('match_id', 'count')
    ).reset_index()
    
    team_bat_tot = bat_match.groupby('batting_team_id').agg(
        tot_runs=('runs_scored', 'sum'),
        tot_balls=('balls_faced', 'sum'),
        matches=('match_id', 'count')
    ).reset_index()
    
    # Merge with match-level stats to subtract current match (leave-one-out)
    loo_bowl = bowl_match.merge(team_bowl_tot, on='bowling_team_id', how='left')
    loo_bowl['rem_runs'] = loo_bowl['tot_runs'] - loo_bowl['runs_conceded']
    loo_bowl['rem_wkts'] = loo_bowl['tot_wkts'] - loo_bowl['wkts_taken']
    loo_bowl['rem_balls'] = loo_bowl['tot_balls'] - loo_bowl['balls_bowled']
    loo_bowl['rem_matches'] = loo_bowl['matches'] - 1
    
    # Shrunk leave-one-out metrics
    prior_weight = 120  # 20 overs worth of balls
    loo_bowl['global_econ'] = loo_bowl['match_format'].map(global_bowl_econ)
    loo_bowl['global_wkt'] = loo_bowl['match_format'].map(global_bowl_wkt)
    
    loo_bowl['opp_bowling_econ'] = (
        (loo_bowl['rem_runs'] + prior_weight * loo_bowl['global_econ']) /
        (loo_bowl['rem_balls'] + prior_weight)
    )
    loo_bowl['opp_bowling_wkt_rate'] = (
        (loo_bowl['rem_wkts'] + prior_weight * loo_bowl['global_wkt']) /
        (loo_bowl['rem_balls'] + prior_weight)
    )
    
    loo_bat = bat_match.merge(team_bat_tot, on='batting_team_id', how='left')
    loo_bat['rem_runs'] = loo_bat['tot_runs'] - loo_bat['runs_scored']
    loo_bat['rem_balls'] = loo_bat['tot_balls'] - loo_bat['balls_faced']
    loo_bat['global_sr'] = loo_bat['match_format'].map(global_bat_sr)
    
    loo_bat['team_batting_sr'] = (
        (loo_bat['rem_runs'] + prior_weight * loo_bat['global_sr']) /
        (loo_bat['rem_balls'] + prior_weight)
    )
    
    # Merge into main dataframe
    df = df.merge(
        loo_bowl[['bowling_team_id', 'match_id', 'opp_bowling_econ', 'opp_bowling_wkt_rate']],
        on=['bowling_team_id', 'match_id'],
        how='left'
    )
    df = df.merge(
        loo_bat[['batting_team_id', 'match_id', 'team_batting_sr']],
        on=['batting_team_id', 'match_id'],
        how='left'
    )
    
    # Fallback to format averages if missing
    for fmt in ['T20', 'T20I']:
        fmt_mask = df['match_format'] == fmt
        df.loc[fmt_mask, 'opp_bowling_econ'] = df.loc[fmt_mask, 'opp_bowling_econ'].fillna(global_bowl_econ[fmt])
        df.loc[fmt_mask, 'opp_bowling_wkt_rate'] = df.loc[fmt_mask, 'opp_bowling_wkt_rate'].fillna(global_bowl_wkt[fmt])
        df.loc[fmt_mask, 'team_batting_sr'] = df.loc[fmt_mask, 'team_batting_sr'].fillna(global_bat_sr[fmt])
        
    return df


def prepare_baseline_features(df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray, np.ndarray, list, Dict]:
    """Prepare context feature matrix X, y_runs, and y_wicket."""
    data = df.copy()
    
    # Categorical encodings
    data['is_rhb'] = (data['batting_type'] == 'RHB').astype(float)
    data['is_pace'] = (data['pace_or_spin'] == 'Pace').astype(float)
    
    # Phase one-hot
    phase_dummies = pd.get_dummies(data['phase'], prefix='phase', dtype=float)
    for col in ['phase_powerplay', 'phase_middle', 'phase_death']:
        if col not in phase_dummies.columns:
            phase_dummies[col] = 0.0
            
    # Bowling type target encoding / top categories
    top_bowl_types = data['bowling_type'].value_counts().head(8).index.tolist()
    for bt in top_bowl_types:
        col_name = 'bt_' + str(bt).replace(' ', '_').replace('-', '_').lower()
        data[col_name] = (data['bowling_type'] == bt).astype(float)
        
    bowl_type_cols = [f'bt_{str(bt).replace(" ", "_").replace("-", "_").lower()}' for bt in top_bowl_types]
    
    feature_cols = [
        'innings',
        'balls_remaining',
        'wickets_in_hand',
        'cum_total_runs',
        'current_run_rate',
        'required_run_rate',
        'venue_par_score',
        'is_ipl',
        'is_rhb',
        'is_pace',
        'opp_bowling_econ',
        'opp_bowling_wkt_rate',
        'team_batting_sr',
        'phase_powerplay',
        'phase_middle',
        'phase_death'
    ] + bowl_type_cols
    
    # Combine feature frame
    feat_df = pd.concat([data[['innings', 'balls_remaining', 'wickets_in_hand', 'cum_total_runs',
                               'current_run_rate', 'required_run_rate', 'venue_par_score', 'is_ipl',
                               'is_rhb', 'is_pace', 'opp_bowling_econ', 'opp_bowling_wkt_rate',
                               'team_batting_sr'] + bowl_type_cols], phase_dummies[['phase_powerplay', 'phase_middle', 'phase_death']]], axis=1)
    
    X = feat_df[feature_cols].values.astype(np.float32)
    X = np.nan_to_num(X, nan=0.0, posinf=100.0, neginf=-100.0)
    
    y_runs = data['batter_runs'].values.astype(np.float32)
    y_wicket = data['is_wicket'].values.astype(np.float32)
    
    metadata = {
        'feature_cols': feature_cols,
        'top_bowl_types': top_bowl_types
    }
    
    return X, y_runs, y_wicket, feature_cols, metadata


def train_expected_outcome_models(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict]:
    """
    Train E[runs] regressor and P(wicket) classifier with 5-fold GroupKFold by match_id.
    Returns dataframe with attached 'exp_runs' and 'exp_wicket', plus model metrics.
    """
    print("\n" + "=" * 60)
    print("STAGE 3: Expected-Outcome Baselines Training (E[runs] & P(wicket))")
    print("=" * 60)
    
    # Add leave-one-out team strengths
    df = compute_leave_one_out_team_strengths(df)
    
    # Prepare features
    X, y_runs, y_wicket, feature_cols, metadata = prepare_baseline_features(df)
    groups = df['match_id'].values
    
    print(f"Features: {len(feature_cols)} | Samples: {X.shape[0]:,} balls across {len(np.unique(groups))} matches")
    
    gkf = GroupKFold(n_splits=5)
    
    oof_exp_runs = np.zeros(len(df), dtype=np.float32)
    oof_exp_wicket = np.zeros(len(df), dtype=np.float32)
    
    runs_params = {
        'objective': 'regression',
        'metric': 'rmse',
        'boosting_type': 'gbdt',
        'learning_rate': 0.05,
        'num_leaves': 31,
        'max_depth': 5,
        'feature_fraction': 0.8,
        'bagging_fraction': 0.8,
        'bagging_freq': 5,
        'min_child_samples': 50,
        'seed': SEED,
        'verbose': -1,
        'n_jobs': -1
    }
    
    wicket_params = {
        'objective': 'binary',
        'metric': 'binary_logloss',
        'boosting_type': 'gbdt',
        'learning_rate': 0.03,
        'num_leaves': 31,
        'max_depth': 5,
        'feature_fraction': 0.8,
        'bagging_fraction': 0.8,
        'bagging_freq': 5,
        'min_child_samples': 50,
        'seed': SEED,
        'verbose': -1,
        'n_jobs': -1
    }
    
    print("\nRunning 5-fold GroupKFold cross-validation...")
    cv_runs_rmse = []
    cv_runs_mae = []
    cv_wkt_logloss = []
    cv_wkt_auc = []
    cv_wkt_brier = []
    
    for fold, (tr_idx, val_idx) in enumerate(gkf.split(X, y_runs, groups)):
        X_tr, X_val = X[tr_idx], X[val_idx]
        y_r_tr, y_r_val = y_runs[tr_idx], y_runs[val_idx]
        y_w_tr, y_w_val = y_wicket[tr_idx], y_wicket[val_idx]
        
        # Train E[runs]
        dtrain_r = lgb.Dataset(X_tr, label=y_r_tr)
        dval_r = lgb.Dataset(X_val, label=y_r_val, reference=dtrain_r)
        model_r = lgb.train(
            runs_params, dtrain_r, num_boost_round=300,
            valid_sets=[dval_r],
            callbacks=[lgb.early_stopping(30, verbose=False)]
        )
        oof_exp_runs[val_idx] = model_r.predict(X_val)
        
        cv_runs_rmse.append(np.sqrt(mean_squared_error(y_r_val, oof_exp_runs[val_idx])))
        cv_runs_mae.append(mean_absolute_error(y_r_val, oof_exp_runs[val_idx]))
        
        # Train P(wicket)
        dtrain_w = lgb.Dataset(X_tr, label=y_w_tr)
        dval_w = lgb.Dataset(X_val, label=y_w_val, reference=dtrain_w)
        model_w = lgb.train(
            wicket_params, dtrain_w, num_boost_round=300,
            valid_sets=[dval_w],
            callbacks=[lgb.early_stopping(30, verbose=False)]
        )
        oof_exp_wicket[val_idx] = model_w.predict(X_val)
        
        cv_wkt_logloss.append(log_loss(y_w_val, oof_exp_wicket[val_idx]))
        cv_wkt_auc.append(roc_auc_score(y_w_val, oof_exp_wicket[val_idx]))
        cv_wkt_brier.append(brier_score_loss(y_w_val, oof_exp_wicket[val_idx]))
        
    print(f"  E[runs] CV RMSE:  {np.mean(cv_runs_rmse):.4f} ± {np.std(cv_runs_rmse):.4f}")
    print(f"  E[runs] CV MAE:   {np.mean(cv_runs_mae):.4f} ± {np.std(cv_runs_mae):.4f}")
    print(f"  P(wkt)  CV AUC:   {np.mean(cv_wkt_auc):.4f} ± {np.std(cv_wkt_auc):.4f}")
    print(f"  P(wkt)  CV LogL:  {np.mean(cv_wkt_logloss):.4f} ± {np.std(cv_wkt_logloss):.4f}")
    print(f"  P(wkt)  CV Brier: {np.mean(cv_wkt_brier):.4f} ± {np.std(cv_wkt_brier):.4f}")
    
    # Train full models on all data
    print("\nTraining final baseline models on full dataset...")
    dtrain_r_full = lgb.Dataset(X, label=y_runs)
    final_model_r = lgb.train(runs_params, dtrain_r_full, num_boost_round=150)
    
    dtrain_w_full = lgb.Dataset(X, label=y_wicket)
    final_model_w = lgb.train(wicket_params, dtrain_w_full, num_boost_round=150)
    
    # Use out-of-fold predictions to prevent training set leakage in player ratings!
    df['exp_runs'] = oof_exp_runs
    df['exp_wicket'] = oof_exp_wicket
    
    # Context-adjusted value metrics
    df['rae'] = df['batter_runs'] - df['exp_runs']  # Runs Above Expected (Batter)
    df['rsae'] = df['exp_runs'] - df['bowler_runs_conceded']  # Runs Saved Above Expected (Bowler)
    df['wae'] = df['is_bowler_wicket'].astype(float) - df['exp_wicket']  # Wicket Above Expected (Bowler)
    
    # Calibration plot for P(wicket)
    plot_wicket_calibration(y_wicket, oof_exp_wicket)
    plot_baseline_feature_importance(final_model_r, final_model_w, feature_cols)
    
    metrics = {
        'runs_cv_rmse': np.mean(cv_runs_rmse),
        'runs_cv_mae': np.mean(cv_runs_mae),
        'wkt_cv_auc': np.mean(cv_wkt_auc),
        'wkt_cv_logloss': np.mean(cv_wkt_logloss),
        'wkt_cv_brier': np.mean(cv_wkt_brier),
        'feature_cols': feature_cols,
        'model_runs': final_model_r,
        'model_wicket': final_model_w
    }
    
    return df, metrics


def plot_wicket_calibration(y_true, y_pred) -> None:
    """Plot calibration curve for expected wicket baseline."""
    prob_true, prob_pred = calibration_curve(y_true, y_pred, n_bins=10, strategy='uniform')
    
    fig, ax = plt.subplots(figsize=(7, 6))
    ax.plot(prob_pred, prob_true, 's-', color='#E63894', linewidth=2, label='P(wicket) Model (OOF)')
    ax.plot([0, 0.25], [0, 0.25], '--', color='gray', label='Perfect Calibration')
    ax.set_xlabel('Predicted Probability of Wicket', fontsize=11)
    ax.set_ylabel('Observed Wicket Frequency', fontsize=11)
    ax.set_title('Expected Wicket Baseline Calibration (Grouped CV)', fontweight='bold', fontsize=12)
    ax.legend(frameon=True)
    ax.grid(True, alpha=0.3)
    ax.set_xlim(0, max(prob_pred)*1.2)
    ax.set_ylim(0, max(prob_true)*1.2)
    plt.tight_layout()
    plt.savefig(FIG_DIR / 'baseline_wicket_calibration.png', dpi=200, bbox_inches='tight')
    plt.close()
    print(f"  Saved wicket calibration to {FIG_DIR / 'baseline_wicket_calibration.png'}")


def plot_baseline_feature_importance(model_r, model_w, feature_cols) -> None:
    """Plot feature importance for baseline models."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
    
    imp_r = model_r.feature_importance(importance_type='gain')
    imp_w = model_w.feature_importance(importance_type='gain')
    
    idx_r = np.argsort(imp_r)[-10:]
    idx_w = np.argsort(imp_w)[-10:]
    
    ax1.barh(range(10), imp_r[idx_r], color='#1A3667')
    ax1.set_yticks(range(10))
    ax1.set_yticklabels([feature_cols[i] for i in idx_r])
    ax1.set_title('E[runs] Top 10 Drivers (Gain)', fontweight='bold')
    ax1.set_xlabel('Feature Importance')
    ax1.grid(axis='x', alpha=0.3)
    
    ax2.barh(range(10), imp_w[idx_w], color='#E63894')
    ax2.set_yticks(range(10))
    ax2.set_yticklabels([feature_cols[i] for i in idx_w])
    ax2.set_title('P(wicket) Top 10 Drivers (Gain)', fontweight='bold')
    ax2.set_xlabel('Feature Importance')
    ax2.grid(axis='x', alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(FIG_DIR / 'baseline_feature_importance.png', dpi=200, bbox_inches='tight')
    plt.close()
    print(f"  Saved baseline feature importance to {FIG_DIR / 'baseline_feature_importance.png'}")


if __name__ == '__main__':
    from src.data import clean_and_prepare
    from src.wp_model import train_wp_models
    from src.pressure import compute_pressure_index
    
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
    df, baseline_metrics = train_expected_outcome_models(df)
    
    print("\nBaseline summary:")
    print(f"Mean actual runs: {df['batter_runs'].mean():.3f} vs Mean E[runs]: {df['exp_runs'].mean():.3f}")
    print(f"Mean actual wickets: {df['is_wicket'].mean():.3f} vs Mean P(wicket): {df['exp_wicket'].mean():.3f}")

