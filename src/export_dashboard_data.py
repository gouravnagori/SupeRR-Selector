"""
export_dashboard_data.py - Exports precomputed JSON datasets for the offline dashboard.
"""

import json
from pathlib import Path
import pandas as pd
import numpy as np

OUTPUT_DIR = Path(r"D:\SupeRR\outputs")
DASHBOARD_DATA_DIR = Path(r"D:\SupeRR\dashboard\public\data")
DASHBOARD_DATA_DIR.mkdir(parents=True, exist_ok=True)


def export_data():
    print("Exporting precomputed dashboard JSON files...")
    
    # 1. Batters
    batters = pd.read_csv(OUTPUT_DIR / 'batters_ranking.csv')
    top10_batters = pd.read_csv(OUTPUT_DIR / 'top10_batters.csv')
    
    # 2. Bowlers
    bowlers = pd.read_csv(OUTPUT_DIR / 'bowlers_ranking.csv')
    top10_bowlers = pd.read_csv(OUTPUT_DIR / 'top10_bowlers.csv')
    
    # 3. Sensitivity
    sens = pd.read_csv(OUTPUT_DIR / 'sensitivity_results.csv')
    
    # Convert NaN to None for JSON compliance
    bat_records = batters[batters['is_eligible']].fillna(0).to_dict(orient='records')
    top10_b_records = top10_batters.fillna(0).to_dict(orient='records')
    
    bowl_records = bowlers[bowlers['is_eligible']].fillna(0).to_dict(orient='records')
    top10_bw_records = top10_bowlers.fillna(0).to_dict(orient='records')
    
    sens_records = sens.fillna(0).to_dict(orient='records')
    
    # 4. Chase match for interactive scrubber (Match with high PI from pressure.py)
    # Let's extract ball-by-ball data of a famous close match
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
    
    # Pick the highest drama chase (Match 13512 or close chase)
    inn2 = df[df['innings'] == 2].copy()
    chase_matches = inn2.groupby('match_id').agg(
        mean_pi=('pressure_index', 'mean'),
        balls=('innings_ball_num', 'count')
    ).reset_index()
    qual = chase_matches[(chase_matches['balls'] >= 115) & (chase_matches['mean_pi'] > 0.38)]
    target_match_id = int(qual.sort_values('mean_pi', ascending=False).iloc[0]['match_id'])
    
    chase_balls = df[(df['match_id'] == target_match_id) & (df['innings'] == 2)].sort_values('innings_ball_num')
    chase_export = chase_balls[[
        'innings_ball_num', 'overid', 'over_ball_num', 'striker_name', 'bowler_name',
        'batter_runs', 'is_four', 'is_six', 'is_wicket', 'dismissal_type',
        'cum_total_runs', 'runs_needed', 'balls_remaining', 'required_run_rate',
        'wp', 'pressure_index', 'is_high_pressure'
    ]].fillna(0).to_dict(orient='records')
    
    # Write files
    with open(DASHBOARD_DATA_DIR / 'batters.json', 'w', encoding='utf-8') as f:
        json.dump(bat_records, f, indent=2)
    with open(DASHBOARD_DATA_DIR / 'top10_batters.json', 'w', encoding='utf-8') as f:
        json.dump(top10_b_records, f, indent=2)
        
    with open(DASHBOARD_DATA_DIR / 'bowlers.json', 'w', encoding='utf-8') as f:
        json.dump(bowl_records, f, indent=2)
    with open(DASHBOARD_DATA_DIR / 'top10_bowlers.json', 'w', encoding='utf-8') as f:
        json.dump(top10_bw_records, f, indent=2)
        
    with open(DASHBOARD_DATA_DIR / 'sensitivity.json', 'w', encoding='utf-8') as f:
        json.dump(sens_records, f, indent=2)
        
    with open(DASHBOARD_DATA_DIR / 'chase_sample.json', 'w', encoding='utf-8') as f:
        json.dump({
            'match_id': target_match_id,
            'balls': chase_export
        }, f, indent=2)
        
    print(f"Data exported successfully to {DASHBOARD_DATA_DIR}")


if __name__ == '__main__':
    export_data()

