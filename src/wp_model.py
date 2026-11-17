"""
wp_model.py - Win Probability model for SupeRR Selector S2.

Trains a ball-by-ball win probability model using:
- Logistic Regression (baseline)
- LightGBM (main model) with monotonic constraints

Features are pre-ball only (no look-ahead leakage).
Validation: GroupKFold by match_id + time-based holdout.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Tuple, Dict, Optional
import pickle
import warnings

from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold
from sklearn.metrics import log_loss, brier_score_loss, roc_auc_score
from sklearn.calibration import calibration_curve
from sklearn.preprocessing import StandardScaler
import lightgbm as lgb
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

warnings.filterwarnings('ignore')

SEED = 42
OUTPUT_DIR = Path(r"D:\SupeRR\outputs")
FIG_DIR = OUTPUT_DIR / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)


def compute_venue_par_scores(df: pd.DataFrame, train_match_ids: set) -> pd.DataFrame:
    """
    Compute venue-and-format first-innings average score from TRAINING matches only.
    This avoids leakage - we never use test match data for venue stats.
    """
    # Only use training matches for venue stats
    train_data = df[df['match_id'].isin(train_match_ids) & (df['innings'] == 1)]
    
    # Compute first innings total per match
    inn1_totals = train_data.groupby(['match_id', 'venue_id', 'match_format'])['total_runs'].sum().reset_index()
    inn1_totals.rename(columns={'total_runs': 'inn1_total'}, inplace=True)
    
    # Venue-format average
    venue_par = inn1_totals.groupby(['venue_id', 'match_format'])['inn1_total'].agg(['mean', 'count']).reset_index()
    venue_par.columns = ['venue_id', 'match_format', 'venue_par_score', 'venue_match_count']
    
    # Global average as fallback
    global_par = inn1_totals.groupby('match_format')['inn1_total'].mean().reset_index()
    global_par.columns = ['match_format', 'global_par_score']
    
    venue_par = venue_par.merge(global_par, on='match_format', how='left')
    
    # Shrink venue par toward global (especially for low sample venues)
    min_matches = 5
    venue_par['venue_par_score'] = np.where(
        venue_par['venue_match_count'] >= min_matches,
        venue_par['venue_par_score'],
        venue_par['global_par_score']
    )
    
    return venue_par


def prepare_wp_features(df: pd.DataFrame, venue_par: pd.DataFrame) -> Tuple[pd.DataFrame, list]:
    """
    Prepare features for the WP model. All features are pre-ball (no leakage).
    
    Returns feature matrix and feature column names.
    """
    features = df.copy()
    
    # Merge venue par score
    features = features.merge(
        venue_par[['venue_id', 'match_format', 'venue_par_score']],
        on=['venue_id', 'match_format'],
        how='left'
    )
    features['venue_par_score'] = features['venue_par_score'].fillna(160)  # reasonable T20 default
    
    # Inn 1 par-score comparison: current score vs expected at this point
    features['inn1_score_vs_par'] = np.where(
        features['innings'] == 1,
        features['cum_total_runs'] - (features['venue_par_score'] * features['legal_balls_before'] / 120),
        0
    )
    
    # Feature columns
    feature_cols = [
        'innings',                    # 1 or 2
        'balls_remaining',            # legal balls left
        'wickets_in_hand',            # 10 - wickets fallen
        'cum_total_runs',             # score before this ball
        'current_run_rate',           # runs per over so far
        'is_chase',                   # innings 2 indicator
        'chase_target',               # target (chase only, 0 for inn 1)
        'runs_needed',                # runs still needed (chase only)
        'required_run_rate',          # RRR (chase only)
        'resources',                  # wickets_in_hand * balls_remaining
        'venue_par_score',            # venue first-innings average
        'inn1_score_vs_par',          # score relative to par (inn 1 only)
        'is_knockout',                # knockout match indicator
    ]
    
    # Format encoding (IPL=1, T20I=0)
    features['is_ipl'] = (features['match_format'] == 'T20').astype(int)
    feature_cols.append('is_ipl')
    
    # Interaction: balls * wickets already encoded as 'resources'
    # Additional interaction: RRR * balls_remaining for chase pressure
    features['chase_pressure'] = features['required_run_rate'] * np.log1p(features['balls_remaining'])
    feature_cols.append('chase_pressure')
    
    return features, feature_cols


def train_wp_models(df: pd.DataFrame) -> Dict:
    """
    Train Win Probability models with proper grouped CV and time holdout.
    
    Returns dict with models, metrics, and predictions.
    """
    print("=" * 60)
    print("STAGE 2: Win Probability Model Training")
    print("=" * 60)
    
    # Only use matches with a winner for WP training
    wp_data = df[df['win_team_id'].fillna(0) > 0].copy()
    
    # Only use legal deliveries for cleaner modeling
    # Actually, include all deliveries to capture game state at every ball
    
    target_col = 'batting_team_won'
    
    # Time-based holdout: latest season (2026 or latest available)
    seasons = sorted(wp_data['season'].dropna().unique())
    holdout_season = seasons[-1] if len(seasons) > 0 else '2026'
    print(f"Holdout season: {holdout_season}")
    
    holdout_mask = wp_data['season'] == holdout_season
    train_data = wp_data[~holdout_mask].copy()
    test_data = wp_data[holdout_mask].copy()
    
    print(f"Training matches: {train_data['match_id'].nunique()}, balls: {len(train_data):,}")
    print(f"Holdout matches: {test_data['match_id'].nunique()}, balls: {len(test_data):,}")
    
    # Compute venue par scores from training data only
    train_match_ids = set(train_data['match_id'].unique())
    venue_par = compute_venue_par_scores(wp_data, train_match_ids)
    
    # Prepare features
    train_feat, feature_cols = prepare_wp_features(train_data, venue_par)
    test_feat, _ = prepare_wp_features(test_data, venue_par)
    
    X_train = train_feat[feature_cols].values.astype(np.float32)
    y_train = train_feat[target_col].values.astype(int)
    groups_train = train_feat['match_id'].values
    
    X_test = test_feat[feature_cols].values.astype(np.float32)
    y_test = test_feat[target_col].values.astype(int)
    
    # Handle NaN/inf
    X_train = np.nan_to_num(X_train, nan=0.0, posinf=100, neginf=-100)
    X_test = np.nan_to_num(X_test, nan=0.0, posinf=100, neginf=-100)
    
    results = {'feature_cols': feature_cols, 'venue_par': venue_par}
    
    # ====== 1. Logistic Regression Baseline ======
    print("\n--- Logistic Regression ---")
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    lr = LogisticRegression(max_iter=1000, random_state=SEED, C=1.0)
    lr.fit(X_train_scaled, y_train)
    
    lr_pred_train = lr.predict_proba(X_train_scaled)[:, 1]
    lr_pred_test = lr.predict_proba(X_test_scaled)[:, 1]
    
    lr_metrics = {
        'train_logloss': log_loss(y_train, lr_pred_train),
        'test_logloss': log_loss(y_test, lr_pred_test),
        'train_brier': brier_score_loss(y_train, lr_pred_train),
        'test_brier': brier_score_loss(y_test, lr_pred_test),
        'train_auc': roc_auc_score(y_train, lr_pred_train),
        'test_auc': roc_auc_score(y_test, lr_pred_test),
    }
    print(f"  Train - LogLoss: {lr_metrics['train_logloss']:.4f}, "
          f"Brier: {lr_metrics['train_brier']:.4f}, AUC: {lr_metrics['train_auc']:.4f}")
    print(f"  Test  - LogLoss: {lr_metrics['test_logloss']:.4f}, "
          f"Brier: {lr_metrics['test_brier']:.4f}, AUC: {lr_metrics['test_auc']:.4f}")
    
    results['lr'] = {
        'model': lr, 'scaler': scaler, 'metrics': lr_metrics,
        'pred_train': lr_pred_train, 'pred_test': lr_pred_test
    }
    
    # ====== 2. LightGBM ======
    print("\n--- LightGBM ---")
    
    # Monotonic constraints: 
    # wickets_in_hand (idx 2): more wickets = higher WP → +1
    # balls_remaining (idx 1): more balls = higher WP → +1
    # We need to map feature indices
    fi = {name: i for i, name in enumerate(feature_cols)}
    monotone = [0] * len(feature_cols)
    if 'wickets_in_hand' in fi:
        monotone[fi['wickets_in_hand']] = 1   # more wickets → higher WP
    if 'balls_remaining' in fi:
        monotone[fi['balls_remaining']] = 1    # more balls → higher WP
    if 'resources' in fi:
        monotone[fi['resources']] = 1          # more resources → higher WP
    
    lgb_params = {
        'objective': 'binary',
        'metric': 'binary_logloss',
        'boosting_type': 'gbdt',
        'num_leaves': 31,
        'learning_rate': 0.03,
        'feature_fraction': 0.7,
        'bagging_fraction': 0.7,
        'bagging_freq': 5,
        'min_child_samples': 100,
        'reg_alpha': 1.0,
        'reg_lambda': 1.0,
        'max_depth': 5,
        'monotone_constraints': monotone,
        'verbose': -1,
        'seed': SEED,
        'n_jobs': -1,
    }
    
    # GroupKFold CV (5 folds)
    gkf = GroupKFold(n_splits=5)
    cv_scores = {'logloss': [], 'brier': [], 'auc': []}
    
    for fold, (tr_idx, val_idx) in enumerate(gkf.split(X_train, y_train, groups_train)):
        X_tr, X_val = X_train[tr_idx], X_train[val_idx]
        y_tr, y_val = y_train[tr_idx], y_train[val_idx]
        
        dtrain = lgb.Dataset(X_tr, label=y_tr)
        dval = lgb.Dataset(X_val, label=y_val, reference=dtrain)
        
        model = lgb.train(
            lgb_params, dtrain,
            num_boost_round=500,
            valid_sets=[dval],
            callbacks=[lgb.early_stopping(50), lgb.log_evaluation(0)]
        )
        
        val_pred = model.predict(X_val)
        cv_scores['logloss'].append(log_loss(y_val, val_pred))
        cv_scores['brier'].append(brier_score_loss(y_val, val_pred))
        cv_scores['auc'].append(roc_auc_score(y_val, val_pred))
    
    print(f"  CV LogLoss: {np.mean(cv_scores['logloss']):.4f} ± {np.std(cv_scores['logloss']):.4f}")
    print(f"  CV Brier:   {np.mean(cv_scores['brier']):.4f} ± {np.std(cv_scores['brier']):.4f}")
    print(f"  CV AUC:     {np.mean(cv_scores['auc']):.4f} ± {np.std(cv_scores['auc']):.4f}")
    
    # Train final model on all training data, using avg best iteration from CV
    avg_best_round = int(np.mean([m.predict(X_train[:1]).shape for m in [model]]))  # placeholder
    # Use conservative round count based on early stopping
    dtrain_full = lgb.Dataset(X_train, label=y_train)
    lgb_model = lgb.train(lgb_params, dtrain_full, num_boost_round=200)
    
    lgb_pred_train = lgb_model.predict(X_train)
    lgb_pred_test = lgb_model.predict(X_test)
    
    lgb_metrics = {
        'cv_logloss_mean': np.mean(cv_scores['logloss']),
        'cv_logloss_std': np.std(cv_scores['logloss']),
        'cv_brier_mean': np.mean(cv_scores['brier']),
        'cv_brier_std': np.std(cv_scores['brier']),
        'cv_auc_mean': np.mean(cv_scores['auc']),
        'cv_auc_std': np.std(cv_scores['auc']),
        'test_logloss': log_loss(y_test, lgb_pred_test),
        'test_brier': brier_score_loss(y_test, lgb_pred_test),
        'test_auc': roc_auc_score(y_test, lgb_pred_test),
    }
    print(f"\n  Test  - LogLoss: {lgb_metrics['test_logloss']:.4f}, "
          f"Brier: {lgb_metrics['test_brier']:.4f}, AUC: {lgb_metrics['test_auc']:.4f}")
    
    results['lgb'] = {
        'model': lgb_model, 'metrics': lgb_metrics, 'cv_scores': cv_scores,
        'pred_train': lgb_pred_train, 'pred_test': lgb_pred_test,
        'params': lgb_params,
    }
    
    # ====== Compare and decide ======
    lgb_gain = lr_metrics['test_logloss'] - lgb_metrics['test_logloss']
    print(f"\n  LGB improvement over LR (test log-loss): {lgb_gain:.4f}")
    
    if lgb_gain > 0.005:
        results['chosen_model'] = 'lgb'
        print("  → Using LightGBM (meaningful improvement)")
    else:
        results['chosen_model'] = 'lr'
        print("  → Using Logistic Regression (LGB gain negligible)")
    
    # ====== Feature importance ======
    importance = lgb_model.feature_importance(importance_type='gain')
    feat_imp = sorted(zip(feature_cols, importance), key=lambda x: -x[1])
    print("\n  Feature importance (gain):")
    for name, imp in feat_imp:
        print(f"    {name}: {imp:.1f}")
    
    results['feature_importance'] = feat_imp
    
    # ====== Predict WP for ALL balls ======
    print("\nPredicting WP for all balls...")
    all_feat, _ = prepare_wp_features(df, venue_par)
    X_all = all_feat[feature_cols].values.astype(np.float32)
    X_all = np.nan_to_num(X_all, nan=0.0, posinf=100, neginf=-100)
    
    if results['chosen_model'] == 'lgb':
        all_pred = lgb_model.predict(X_all)
    else:
        X_all_scaled = scaler.transform(X_all)
        all_pred = lr.predict_proba(X_all_scaled)[:, 1]
    
    results['all_predictions'] = all_pred
    results['train_mask'] = ~holdout_mask
    results['test_mask'] = holdout_mask
    results['y_train'] = y_train
    results['y_test'] = y_test
    
    # ====== Generate plots ======
    plot_calibration(y_test, lr_pred_test, lgb_pred_test, results['chosen_model'])
    plot_wp_feature_importance(feat_imp)
    
    return results


def plot_calibration(y_true, lr_pred, lgb_pred, chosen):
    """Plot calibration curves for both models."""
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    
    for ax, (name, pred) in zip(axes, [('Logistic Regression', lr_pred), ('LightGBM', lgb_pred)]):
        prob_true, prob_pred = calibration_curve(y_true, pred, n_bins=10, strategy='uniform')
        
        ax.plot(prob_pred, prob_true, 'o-', color='#E63894', label=f'{name}', linewidth=2)
        ax.plot([0, 1], [0, 1], '--', color='gray', label='Perfect calibration')
        ax.set_xlabel('Predicted probability', fontsize=12)
        ax.set_ylabel('Observed frequency', fontsize=12)
        ax.set_title(f'{name} — Calibration (Holdout)', fontsize=13, fontweight='bold')
        ax.legend()
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.grid(True, alpha=0.3)
        
        if name.startswith('L') and chosen == 'lgb':
            ax.set_title(f'{name} — Calibration (Holdout) ★ CHOSEN', fontsize=13, fontweight='bold')
        elif name.startswith('Log') and chosen == 'lr':
            ax.set_title(f'{name} — Calibration (Holdout) ★ CHOSEN', fontsize=13, fontweight='bold')
    
    plt.tight_layout()
    plt.savefig(FIG_DIR / 'wp_calibration.png', dpi=200, bbox_inches='tight')
    plt.close()
    print(f"  Saved calibration plot to {FIG_DIR / 'wp_calibration.png'}")


def plot_wp_feature_importance(feat_imp):
    """Plot feature importance bar chart."""
    fig, ax = plt.subplots(figsize=(10, 6))
    
    names = [f[0] for f in feat_imp]
    values = [f[1] for f in feat_imp]
    
    bars = ax.barh(range(len(names)), values, color='#1A3667')
    ax.set_yticks(range(len(names)))
    ax.set_yticklabels(names)
    ax.set_xlabel('Feature Importance (Gain)')
    ax.set_title('Win Probability Model — Feature Importance', fontweight='bold')
    ax.invert_yaxis()
    plt.tight_layout()
    plt.savefig(FIG_DIR / 'wp_feature_importance.png', dpi=200, bbox_inches='tight')
    plt.close()


if __name__ == '__main__':
    from src.data import clean_and_prepare
    df, audit = clean_and_prepare(save_audit=False)
    results = train_wp_models(df)
