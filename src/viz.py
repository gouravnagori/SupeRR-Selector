"""
viz.py - Visualizations for SupeRR Selector S2.
Generates:
- Top 10 Batters & Bowlers performance comparison charts
- RR fit and radar profiles
"""

import pandas as pd
import numpy as np
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns

OUTPUT_DIR = Path(r"D:\SupeRR\outputs")
FIG_DIR = OUTPUT_DIR / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)


def plot_top10_cards():
    bat = pd.read_csv(OUTPUT_DIR / 'top10_batters.csv')
    bowl = pd.read_csv(OUTPUT_DIR / 'top10_bowlers.csv')
    
    # 1. Batters Top 10 Horizontal Bar with 95% CIs
    fig, ax = plt.subplots(figsize=(12, 7))
    y_pos = np.arange(len(bat))[::-1]
    ratings = bat['final_pressure_rating'].values
    errors_low = np.maximum(0, ratings - bat['ci_lower'].values)
    errors_high = np.maximum(0, bat['ci_upper'].values - ratings)
    
    bars = ax.barh(y_pos, ratings, xerr=[errors_low, errors_high], color='#E63894', 
                   alpha=0.9, capsize=4, error_kw={'elinewidth': 1.5, 'ecolor': '#1A3667'})
    
    ax.set_yticks(y_pos)
    labels = [f"#{r['rank']} {r['striker_name']} ({r['role']}) - SR {r['sr_hp']:.1f}" for _, r in bat.iterrows()]
    ax.set_yticklabels(labels, fontsize=10, fontweight='bold')
    ax.set_xlabel('Final Pressure Rating (95% Clustered CI)', fontsize=11, fontweight='bold')
    ax.set_title('Top 10 T20 Batters Under Pressure (2022-2026)', fontsize=13, fontweight='bold')
    ax.grid(axis='x', alpha=0.3)
    
    for idx, (bar, rating) in enumerate(zip(bars, ratings)):
        ax.text(rating + 1.5, bar.get_y() + bar.get_height()/2, f"{rating:.2f}", va='center', fontweight='bold', fontsize=9)
        
    plt.tight_layout()
    plt.savefig(FIG_DIR / 'top10_batters_ranking.png', dpi=200, bbox_inches='tight')
    plt.close()
    
    # 2. Bowlers Top 10 Horizontal Bar with 95% CIs
    fig, ax = plt.subplots(figsize=(12, 7))
    y_pos = np.arange(len(bowl))[::-1]
    ratings_bw = bowl['final_pressure_rating'].values
    errors_low_bw = np.maximum(0, ratings_bw - bowl['ci_lower'].values)
    errors_high_bw = np.maximum(0, bowl['ci_upper'].values - ratings_bw)
    
    bars = ax.barh(y_pos, ratings_bw, xerr=[errors_low_bw, errors_high_bw], color='#1A3667', 
                   alpha=0.9, capsize=4, error_kw={'elinewidth': 1.5, 'ecolor': '#E63894'})
    
    ax.set_yticks(y_pos)
    labels = [f"#{r['rank']} {r['bowler_name']} ({r['role']}) - Econ {r['econ_hp']:.2f}" for _, r in bowl.iterrows()]
    ax.set_yticklabels(labels, fontsize=10, fontweight='bold')
    ax.set_xlabel('Final Pressure Rating (95% Clustered CI)', fontsize=11, fontweight='bold')
    ax.set_title('Top 10 T20 Bowlers Under Pressure (2022-2026)', fontsize=13, fontweight='bold')
    ax.grid(axis='x', alpha=0.3)
    
    for idx, (bar, rating) in enumerate(zip(bars, ratings_bw)):
        ax.text(rating + 1.2, bar.get_y() + bar.get_height()/2, f"{rating:.2f}", va='center', fontweight='bold', fontsize=9)
        
    plt.tight_layout()
    plt.savefig(FIG_DIR / 'top10_bowlers_ranking.png', dpi=200, bbox_inches='tight')
    plt.close()
    print("Top 10 summary ranking charts saved.")


if __name__ == '__main__':
    plot_top10_cards()

