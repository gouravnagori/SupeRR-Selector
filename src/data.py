"""
data.py - Data loading, cleaning, and feature engineering for SupeRR Selector S2.

Handles:
- Loading all CSVs from the data pack
- Legal ball definition (excluding wides and no-balls from batter balls faced)
- Extras attribution (byes/legbyes to team not batter, wides/no-balls to bowler)
- Bowler wicket credit (excluding run outs, retired, obstructing field)
- Super over exclusion
- DLS revised target/overs handling
- Abandoned match exclusion
- Duplicate detection and ID collision checks
- Role tagging (batting order, bowling phase)
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Tuple, Dict, Optional
import warnings

warnings.filterwarnings('ignore', category=FutureWarning)

SEED = 42
DATA_DIR = Path(r"D:\SupeRR\6af458274c1e8_data_pack\Data Pack")
OUTPUT_DIR = Path(r"D:\SupeRR\outputs")

# Dismissal types NOT credited to bowler
BOWLER_NON_CREDIT_DISMISSALS = {
    'RunOut', 'Retire Out', 'Obstracting the field', 'Obstructing the field',
    'Timed Out'  # not in data but handle defensively
}

# Dismissal types credited to bowler
BOWLER_CREDIT_DISMISSALS = {
    'Bowled', 'Caught', 'LBW', 'Stump', 'Hit Wicket'
}

# Extras that are NOT legal deliveries (don't count as balls faced by batter)
ILLEGAL_DELIVERY_EXTRAS = {'wide', 'Overstep'}  # Overstep = no-ball in this dataset

# Extras charged to bowler's economy
BOWLER_CHARGED_EXTRAS = {'wide', 'Overstep'}

# Extras NOT charged to batter or bowler (team extras)
TEAM_EXTRAS = {'legbyes', 'byes'}


def load_raw_data() -> Dict[str, pd.DataFrame]:
    """Load all raw CSV files from the data pack."""
    data = {
        'ball_by_ball': pd.read_csv(DATA_DIR / 'ball_by_ball.csv'),
        'matches': pd.read_csv(DATA_DIR / 'matches.csv'),
        'competitions': pd.read_csv(DATA_DIR / 'competitions.csv'),
        'teams': pd.read_csv(DATA_DIR / 'teams.csv'),
        'playing_eleven': pd.read_csv(DATA_DIR / 'playing_eleven.csv'),
        'player_mapping': pd.read_csv(DATA_DIR / 'competition_team_player_mapping.csv'),
    }
    return data


def audit_raw_data(data: Dict[str, pd.DataFrame]) -> Dict:
    """Run comprehensive data quality checks. Returns audit results dict."""
    bbb = data['ball_by_ball']
    matches = data['matches']
    comps = data['competitions']
    
    audit = {}
    
    # 1. Basic counts
    audit['raw_counts'] = {
        'total_balls': len(bbb),
        'total_matches_bbb': bbb['match_id'].nunique(),
        'total_matches_file': len(matches),
        'total_competitions': len(comps),
        'total_players': data['player_mapping']['player_id'].nunique(),
        'innings_values': sorted(bbb['innings'].unique().tolist()),
        'super_over_balls': int(bbb[bbb['innings'].isin([3, 4])].shape[0]),
    }
    
    # 2. Format split
    match_format = matches.merge(comps[['comp_id', 'match_format']], on='comp_id', how='left')
    audit['format_split'] = {
        'T20_IPL': int((match_format['match_format'] == 'T20').sum()),
        'T20I': int((match_format['match_format'] == 'T20I').sum()),
    }
    
    # 3. Extras analysis - determine if runs column includes extras
    # On a wide, the extras1_runs should be 1 (the wide itself) and runs should be the batter runs
    wide_balls = bbb[bbb['extras_type'] == 'wide']
    audit['extras_analysis'] = {
        'wide_count': len(wide_balls),
        'wide_extras1_runs_dist': wide_balls['extras1_runs'].value_counts().to_dict(),
        'wide_runs_dist': wide_balls['runs'].value_counts().head(5).to_dict(),
        'noball_count': int((bbb['extras_type'] == 'Overstep').sum()),
        'legbye_count': int((bbb['extras_type'] == 'legbyes').sum()),
        'bye_count': int((bbb['extras_type'] == 'byes').sum()),
        'other_extras': int((bbb['extras_type'] == 'other').sum()),
        'penalty_count': int((bbb['extras_type'] == 'Penalty').sum()),
    }
    
    # Check: on legbye balls, are runs > 0? If so, runs includes legbye runs (which shouldn't credit batter)
    lb_balls = bbb[bbb['extras_type'] == 'legbyes']
    audit['extras_analysis']['legbye_runs_nonzero'] = int((lb_balls['runs'] > 0).sum())
    audit['extras_analysis']['legbye_runs_zero'] = int((lb_balls['runs'] == 0).sum())
    
    # Check: on bye balls
    bye_balls = bbb[bbb['extras_type'] == 'byes']
    audit['extras_analysis']['bye_runs_nonzero'] = int((bye_balls['runs'] > 0).sum())
    audit['extras_analysis']['bye_runs_zero'] = int((bye_balls['runs'] == 0).sum())
    
    # 4. Dismissal analysis
    wicket_balls = bbb[bbb['is_wicket'] == True]
    audit['dismissals'] = {
        'total_wickets': len(wicket_balls),
        'by_type': wicket_balls['dismissal_type'].value_counts().to_dict(),
        'bowler_credited': int(wicket_balls[
            ~wicket_balls['dismissal_type'].isin(BOWLER_NON_CREDIT_DISMISSALS)
        ].shape[0]),
        'non_striker_runouts': int(wicket_balls[
            (wicket_balls['dismissal_type'] == 'RunOut') &
            (wicket_balls['dismissed_player_id'] != wicket_balls['striker_id'])
        ].shape[0]),
    }
    
    # 5. Duplicate ball check
    dup_key = ['match_id', 'innings', 'overid', 'over_ball_num']
    # For legal balls, there can be multiple deliveries per over_ball_num (wides/no-balls)
    # So we check innings_ball_num instead for true duplicates
    dup_key2 = ['match_id', 'innings', 'innings_ball_num']
    duplicates_ibb = bbb[bbb.duplicated(subset=dup_key2, keep=False)]
    audit['duplicates'] = {
        'by_innings_ball_num': len(duplicates_ibb),
        'by_over_ball': int(bbb.duplicated(subset=dup_key, keep=False).sum()),
    }
    
    # 6. Name collision check (same name, different player_id)
    pm = data['player_mapping']
    name_groups = pm.groupby('player_name')['player_id'].nunique()
    collisions = name_groups[name_groups > 1]
    audit['name_collisions'] = {
        'count': len(collisions),
        'examples': {name: pm[pm['player_name'] == name][['player_id', 'player_name', 'team_name']].drop_duplicates().to_dict('records')
                     for name in collisions.index[:5]}
    }
    
    # 7. Players across multiple teams
    player_teams = pm.groupby('player_id')['team_name'].apply(lambda x: sorted(x.unique().tolist()))
    multi_team = player_teams[player_teams.apply(len) > 1]
    audit['multi_team_players'] = {
        'count': len(multi_team),
        'examples': {int(pid): teams for pid, teams in list(multi_team.items())[:10]}
    }
    
    # 8. DLS/revised matches
    dls = matches[matches['revised_target'].fillna(0) > 0]
    audit['dls_matches'] = {
        'count': len(dls),
        'match_ids': dls['match_id'].tolist(),
    }
    
    # 9. Abandoned/no-result
    no_result = matches[matches['result'].str.contains('No Result|Abandoned|No result|abandoned', case=False, na=False)]
    audit['abandoned'] = {
        'count': len(no_result),
        'match_ids': no_result['match_id'].tolist(),
        'results': no_result['result'].tolist(),
    }
    
    # 10. Matches in bbb but not in matches file and vice versa
    bbb_matches = set(bbb['match_id'].unique())
    file_matches = set(matches['match_id'].unique())
    audit['match_coverage'] = {
        'in_bbb_not_matches': sorted(bbb_matches - file_matches),
        'in_matches_not_bbb': sorted(file_matches - bbb_matches),
    }
    
    # 11. Stage distribution
    audit['stages'] = matches['stage'].value_counts().to_dict()
    
    # 12. Season distribution
    match_format = matches.merge(comps[['comp_id', 'match_format', 'season']], on='comp_id', how='left')
    audit['season_format'] = match_format.groupby(['season', 'match_format']).size().to_dict()
    
    return audit


def compute_ball_level_runs(bbb: pd.DataFrame) -> pd.DataFrame:
    """
    Compute batter_runs and bowler_runs_conceded per ball.
    
    After inspection:
    - `runs` column = runs scored off the bat by the batter (0 on legbyes/byes)
    - `extras1_runs` = extra runs from the extras_type
    - `extras_2_runs` = additional extras (e.g., overthrows on a wide)
    
    Batter runs = `runs` (but 0 on legbyes and byes since those go to team)
    Bowler conceded = batter_runs + wide_runs + no_ball_runs (NOT byes/legbyes)
    Total runs on ball = runs + extras1_runs + extras_2_runs
    """
    df = bbb.copy()
    
    # Batter runs: the `runs` column on non-legbye/bye balls
    # On legbye/bye balls, `runs` appears to be 0 (batter didn't score)
    # but let's verify and handle explicitly
    df['batter_runs'] = df['runs'].copy()
    # On legbyes and byes, batter gets 0 credit
    df.loc[df['extras_type'].isin(['legbyes', 'byes']), 'batter_runs'] = 0
    
    # Is this a legal delivery? (not wide, not no-ball)
    df['is_legal_delivery'] = ~df['extras_type'].isin(ILLEGAL_DELIVERY_EXTRAS)
    
    # Bowler runs conceded = batter runs + extras from wides and no-balls
    df['bowler_extras'] = 0
    df.loc[df['extras_type'].isin(BOWLER_CHARGED_EXTRAS), 'bowler_extras'] = df.loc[
        df['extras_type'].isin(BOWLER_CHARGED_EXTRAS), 'extras1_runs'
    ]
    df['bowler_runs_conceded'] = df['batter_runs'] + df['bowler_extras']
    
    # Also add extras_2_runs for bowler if on a wide/no-ball (e.g., wide + overthrow)
    df.loc[df['extras_type'].isin(BOWLER_CHARGED_EXTRAS), 'bowler_runs_conceded'] += df.loc[
        df['extras_type'].isin(BOWLER_CHARGED_EXTRAS), 'extras_2_runs'
    ].fillna(0)
    
    # Total runs scored on this ball (for team score tracking)
    df['total_runs'] = df['runs'] + df['extras1_runs'].fillna(0) + df['extras_2_runs'].fillna(0)
    
    # Bowler-credited wicket
    df['is_bowler_wicket'] = (
        (df['is_wicket'] == True) & 
        (~df['dismissal_type'].isin(BOWLER_NON_CREDIT_DISMISSALS))
    )
    
    return df


def add_match_context(bbb: pd.DataFrame, matches: pd.DataFrame, 
                       comps: pd.DataFrame) -> pd.DataFrame:
    """Add match-level context: format, stage, knockout, revised overs/target."""
    df = bbb.copy()
    
    # Merge match info
    match_info = matches.merge(comps[['comp_id', 'match_format', 'season']], on='comp_id', how='left')
    match_cols = ['match_id', 'match_format', 'season', 'stage', 'knock_out', 
                  'venue_id', 'win_team_id', 'result',
                  'first_inn_revised_overs', 'second_inn_revised_overs', 'revised_target',
                  'toss_win_team_id', 'toss_opted']
    
    # Only keep columns that exist
    match_cols = [c for c in match_cols if c in match_info.columns]
    df = df.merge(match_info[match_cols], on='match_id', how='left')
    
    # Determine total overs for each innings
    df['total_overs'] = 20  # default T20
    
    # For revised matches, use revised overs
    mask_inn1_revised = (df['innings'] == 1) & (df['first_inn_revised_overs'].fillna(0) > 0)
    df.loc[mask_inn1_revised, 'total_overs'] = df.loc[mask_inn1_revised, 'first_inn_revised_overs']
    
    mask_inn2_revised = (df['innings'] == 2) & (df['second_inn_revised_overs'].fillna(0) > 0)
    df.loc[mask_inn2_revised, 'total_overs'] = df.loc[mask_inn2_revised, 'second_inn_revised_overs']
    
    # Total legal balls in the innings
    df['total_balls_innings'] = (df['total_overs'] * 6).astype(int)
    
    # Is knockout?
    df['is_knockout'] = df['knock_out'].fillna(0).astype(int)
    
    # Is final/semi/qualifier?
    df['is_final'] = df['stage'].isin(['Final']).astype(int)
    df['is_semifinal_or_qualifier'] = df['stage'].isin(['Semi Final', 'Qualifier', 'Eliminator']).astype(int)
    
    return df


def compute_innings_state(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute ball-by-ball innings state: cumulative score, wickets, balls bowled,
    run rate, required run rate (chase innings).
    
    IMPORTANT: All state variables are computed BEFORE the current ball is bowled
    (pre-ball state) to avoid look-ahead leakage.
    """
    # Sort by match, innings, ball sequence
    df = df.sort_values(['match_id', 'innings', 'innings_ball_num']).copy()
    
    # First, compute the first innings total for each match (needed for chase target)
    if 'first_innings_total' not in df.columns:
        first_inn_totals = (
            df[df['innings'] == 1]
            .groupby('match_id')['total_runs']
            .sum()
            .reset_index()
            .rename(columns={'total_runs': 'first_innings_total'})
        )
        df = df.merge(first_inn_totals, on='match_id', how='left')
        df['first_innings_total'] = df['first_innings_total'].fillna(0)
    
    # Chase target: first innings total + 1 (or revised_target if DLS)
    df['chase_target'] = np.where(
        df['innings'] == 2,
        np.where(
            df['revised_target'].fillna(0) > 0,
            df['revised_target'],
            df['first_innings_total'] + 1
        ),
        0
    )
    
    # Cumulative score BEFORE this ball (shift within match-innings group)
    df['cum_total_runs'] = (
        df.groupby(['match_id', 'innings'])['total_runs']
        .cumsum()
        .shift(1, fill_value=0)
    )
    # Fix: shift within group properly
    df['cum_total_runs'] = df.groupby(['match_id', 'innings'])['total_runs'].transform(
        lambda x: x.cumsum().shift(1, fill_value=0)
    )
    
    # Cumulative batter runs before this ball
    df['cum_batter_runs'] = df.groupby(['match_id', 'innings'])['batter_runs'].transform(
        lambda x: x.cumsum().shift(1, fill_value=0)
    )
    
    # Legal balls bowled BEFORE this ball
    df['legal_balls_before'] = df.groupby(['match_id', 'innings'])['is_legal_delivery'].transform(
        lambda x: x.cumsum().shift(1, fill_value=0)
    ).astype(int)
    
    # Wickets fallen BEFORE this ball
    df['wickets_before'] = df.groupby(['match_id', 'innings'])['is_wicket'].transform(
        lambda x: x.astype(int).cumsum().shift(1, fill_value=0)
    ).astype(int)
    
    # Balls remaining (legal balls)
    df['balls_remaining'] = df['total_balls_innings'] - df['legal_balls_before']
    df['balls_remaining'] = df['balls_remaining'].clip(lower=0)
    
    # Wickets in hand
    df['wickets_in_hand'] = 10 - df['wickets_before']
    df['wickets_in_hand'] = df['wickets_in_hand'].clip(lower=0)
    
    # Current run rate (runs per over so far)
    overs_bowled = df['legal_balls_before'] / 6.0
    df['current_run_rate'] = np.where(
        overs_bowled > 0,
        df['cum_total_runs'] / overs_bowled,
        0
    )
    
    # Runs needed (chase innings only)
    df['runs_needed'] = np.where(
        df['innings'] == 2,
        df['chase_target'] - df['cum_total_runs'],
        0
    )
    df['runs_needed'] = df['runs_needed'].clip(lower=0)
    
    # Required run rate (chase innings only)
    overs_remaining = df['balls_remaining'] / 6.0
    df['required_run_rate'] = np.where(
        (df['innings'] == 2) & (overs_remaining > 0),
        df['runs_needed'] / overs_remaining,
        0
    )
    
    # Resources-style interaction
    df['resources'] = df['wickets_in_hand'] * df['balls_remaining']
    
    # Phase: powerplay (overs 1-6), middle (7-15), death (16-20)
    df['phase'] = pd.cut(
        df['overid'],
        bins=[0, 6, 15, 25],  # 25 to handle any edge cases
        labels=['powerplay', 'middle', 'death'],
        right=True
    )
    
    # Is chase innings
    df['is_chase'] = (df['innings'] == 2).astype(int)
    
    # Did batting team win?
    df['batting_team_won'] = (df['batting_team_id'] == df['win_team_id']).astype(int)
    
    return df


def assign_batting_roles(df: pd.DataFrame, playing_eleven: pd.DataFrame) -> pd.DataFrame:
    """Assign batting role tags based on batting order from playing_eleven."""
    # Get batting order from playing_eleven
    pe_orders = playing_eleven[['match_id', 'player_id', 'batting_order', 'is_captain', 'is_wk']].copy()
    
    # Merge for striker
    df = df.merge(
        pe_orders.rename(columns={
            'player_id': 'striker_id',
            'batting_order': 'striker_batting_order_pe',
            'is_captain': 'striker_is_captain',
            'is_wk': 'striker_is_wk'
        }),
        on=['match_id', 'striker_id'],
        how='left'
    )
    
    # Use batting_order from bbb as fallback
    df['effective_batting_order'] = df['striker_batting_order_pe'].fillna(df['batting_order'])
    
    # Role assignment
    def batting_role(order):
        if pd.isna(order):
            return 'unknown'
        order = int(order)
        if order <= 2:
            return 'opener'
        elif order <= 5:
            return 'middle_order'
        else:
            return 'finisher'
    
    df['batting_role'] = df['effective_batting_order'].apply(batting_role)
    
    return df


def assign_bowling_roles(df: pd.DataFrame) -> pd.DataFrame:
    """Assign bowling phase roles based on when bowlers typically bowl."""
    # Compute each bowler's primary bowling phase from the data
    bowler_phase = (
        df[df['is_legal_delivery']]
        .groupby(['bowler_id', 'phase'])
        .size()
        .reset_index(name='balls')
    )
    
    # Get the phase where each bowler bowls the most
    bowler_primary = bowler_phase.sort_values('balls', ascending=False).drop_duplicates('bowler_id')
    bowler_primary = bowler_primary[['bowler_id', 'phase']].rename(columns={'phase': 'bowling_role'})
    
    df = df.merge(bowler_primary, on='bowler_id', how='left')
    
    return df


def clean_and_prepare(save_audit: bool = True) -> Tuple[pd.DataFrame, Dict]:
    """
    Main pipeline: load, audit, clean, and prepare the ball-by-ball dataset.
    
    Returns:
        df: Cleaned DataFrame with all features
        audit: Audit results dictionary
    """
    print("Loading raw data...")
    data = load_raw_data()
    
    print("Running data audit...")
    audit = audit_raw_data(data)
    
    bbb = data['ball_by_ball']
    matches = data['matches']
    comps = data['competitions']
    pe = data['playing_eleven']
    
    # Record pre-cleaning counts
    audit['pre_clean'] = {
        'total_balls': len(bbb),
        'total_matches': bbb['match_id'].nunique(),
    }
    
    # 1. Exclude super overs
    print(f"Excluding super overs (innings 3, 4): {bbb[bbb['innings'].isin([3, 4])].shape[0]} balls")
    bbb = bbb[~bbb['innings'].isin([3, 4])].copy()
    
    # 2. Exclude abandoned/no-result matches
    no_result_ids = set(audit['abandoned']['match_ids'])
    if no_result_ids:
        print(f"Excluding abandoned/no-result matches: {len(no_result_ids)} matches")
        bbb = bbb[~bbb['match_id'].isin(no_result_ids)].copy()
    
    # 3. Also exclude matches not in matches file
    valid_match_ids = set(matches['match_id'])
    bbb = bbb[bbb['match_id'].isin(valid_match_ids)].copy()
    
    # 4. Compute ball-level runs
    print("Computing ball-level runs and bowler credits...")
    df = compute_ball_level_runs(bbb)
    
    # 5. Add match context
    print("Adding match context (format, stage, revised overs)...")
    df = add_match_context(df, matches, comps)
    
    # 6. Exclude matches with no result / win_team_id = 0 or NaN
    # These can't be used for WP model training
    no_winner = df[df['win_team_id'].fillna(0) == 0]['match_id'].unique()
    audit['no_winner_matches'] = {
        'count': len(no_winner),
        'match_ids': no_winner.tolist(),
    }
    
    # 7. Compute innings state
    print("Computing ball-by-ball innings state...")
    df = compute_innings_state(df)
    
    # 8. Assign roles
    print("Assigning batting and bowling roles...")
    df = assign_batting_roles(df, pe)
    df = assign_bowling_roles(df)
    
    # Record post-cleaning counts
    audit['post_clean'] = {
        'total_balls': len(df),
        'total_matches': df['match_id'].nunique(),
        'legal_balls': int(df['is_legal_delivery'].sum()),
        'format_split': df.groupby('match_format')['match_id'].nunique().to_dict(),
        'balls_by_format': df.groupby('match_format').size().to_dict(),
    }
    
    if save_audit:
        write_audit_report(audit)
    
    print(f"Done! {audit['post_clean']['total_balls']} balls across {audit['post_clean']['total_matches']} matches")
    return df, audit


def write_audit_report(audit: Dict) -> None:
    """Write data audit results to markdown file."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    lines = [
        "# Data Audit Report — SupeRR Selector S2\n",
        "## 1. Raw Data Summary\n",
        f"- Total balls in ball_by_ball.csv: **{audit['raw_counts']['total_balls']:,}**",
        f"- Unique matches in ball_by_ball: **{audit['raw_counts']['total_matches_bbb']}**",
        f"- Matches in matches.csv: **{audit['raw_counts']['total_matches_file']}**",
        f"- Total competitions: **{audit['raw_counts']['total_competitions']}**",
        f"- Total unique players: **{audit['raw_counts']['total_players']}**",
        f"- Innings values: {audit['raw_counts']['innings_values']}",
        f"- Super over balls (innings 3/4): **{audit['raw_counts']['super_over_balls']}**\n",
        
        "## 2. Format Split\n",
        f"- T20 (IPL) matches: **{audit['format_split']['T20_IPL']}**",
        f"- T20I matches: **{audit['format_split']['T20I']}**\n",
        
        "## 3. Extras Analysis\n",
        "### How `runs` column works:",
        "- `runs` = runs scored off the bat by the batter",
        "- `extras1_runs` = runs from the extra (1 for a wide, leg-bye runs, etc.)",
        "- `extras_2_runs` = additional extras (overthrows, etc.)\n",
        f"- Wides: **{audit['extras_analysis']['wide_count']:,}** balls",
        f"- No-balls (Overstep): **{audit['extras_analysis']['noball_count']:,}** balls",
        f"- Leg-byes: **{audit['extras_analysis']['legbye_count']:,}** balls",
        f"- Byes: **{audit['extras_analysis']['bye_count']:,}** balls",
        f"- Other extras: **{audit['extras_analysis']['other_extras']:,}** balls",
        f"- Penalty: **{audit['extras_analysis']['penalty_count']}** ball\n",
        
        "### Leg-bye runs check:",
        f"- Leg-bye balls with runs > 0: {audit['extras_analysis']['legbye_runs_nonzero']}",
        f"- Leg-bye balls with runs = 0: {audit['extras_analysis']['legbye_runs_zero']}\n",
        
        "### Bye runs check:",
        f"- Bye balls with runs > 0: {audit['extras_analysis']['bye_runs_nonzero']}",
        f"- Bye balls with runs = 0: {audit['extras_analysis']['bye_runs_zero']}\n",
        
        "### Rules applied:",
        "- **Batter runs** = `runs` column (already 0 on legbye/bye balls in the data)",
        "- **Bowler conceded** = batter_runs + extras from wides + extras from no-balls",
        "- **Byes and leg-byes** credited to team total, NOT batter or bowler",
        "- **Legal delivery** = any ball that is not a wide or no-ball\n",
        
        "## 4. Dismissals\n",
        f"- Total wickets: **{audit['dismissals']['total_wickets']:,}**",
        f"- Bowler-credited wickets: **{audit['dismissals']['bowler_credited']:,}**",
        f"- Non-striker run-outs: **{audit['dismissals']['non_striker_runouts']}**\n",
        "### By type:",
    ]
    
    for dtype, count in sorted(audit['dismissals']['by_type'].items(), key=lambda x: -x[1]):
        credit = "✅ bowler" if dtype in BOWLER_CREDIT_DISMISSALS else "❌ not bowler"
        lines.append(f"- {dtype}: {count:,} ({credit})")
    
    lines.extend([
        "\n### Rules applied:",
        "- Bowler gets credit for: Bowled, Caught, LBW, Stump, Hit Wicket",
        "- Bowler does NOT get credit for: RunOut, Retire Out, Obstructing the field",
        "- Non-striker run-outs attributed to dismissed_player_id (not striker)\n",
    ])
    
    lines.extend([
        "## 5. Duplicate Check\n",
        f"- Duplicate rows by (match_id, innings, innings_ball_num): **{audit['duplicates']['by_innings_ball_num']}**",
        f"- Duplicate rows by (match_id, innings, overid, over_ball_num): **{audit['duplicates']['by_over_ball']}**\n",
    ])
    
    lines.extend([
        "## 6. Name Collisions\n",
        f"- Players with same name but different IDs: **{audit['name_collisions']['count']}**",
        "- Resolution: always key on `player_id`, never on name\n",
    ])
    
    if audit['name_collisions']['count'] > 0:
        lines.append("### Examples:")
        for name, records in list(audit['name_collisions']['examples'].items())[:5]:
            lines.append(f"- **{name}**: {records}")
        lines.append("")
    
    lines.extend([
        "## 7. Multi-Team Players\n",
        f"- Players appearing for multiple teams: **{audit['multi_team_players']['count']}**",
        "- This is expected (IPL franchise + national team)\n",
    ])
    
    lines.extend([
        "## 8. DLS/Revised Matches\n",
        f"- Matches with revised target: **{audit['dls_matches']['count']}**",
        "- Handling: use revised_target and revised overs for pressure/RRR calculations\n",
    ])
    
    lines.extend([
        "## 9. Abandoned/No-Result Matches\n",
        f"- Count: **{audit['abandoned']['count']}**",
    ])
    if audit['abandoned']['count'] > 0:
        lines.append("- Results: " + str(audit['abandoned']['results'][:5]))
    lines.append("- Handling: excluded from all analysis\n")
    
    if 'no_winner_matches' in audit:
        lines.extend([
            "## 10. Matches Without Winner\n",
            f"- Count: **{audit['no_winner_matches']['count']}**",
            "- Handling: kept in dataset but excluded from WP model training\n",
        ])
    
    lines.extend([
        "## 11. Stage Distribution\n",
    ])
    for stage, count in sorted(audit['stages'].items(), key=lambda x: -x[1]):
        lines.append(f"- {stage}: {count}")
    lines.append("")
    
    lines.extend([
        "## 12. Cleaning Summary\n",
        f"- **Before cleaning**: {audit['pre_clean']['total_balls']:,} balls, "
        f"{audit['pre_clean']['total_matches']} matches",
        f"- **After cleaning**: {audit['post_clean']['total_balls']:,} balls, "
        f"{audit['post_clean']['total_matches']} matches",
        f"- **Legal balls**: {audit['post_clean']['legal_balls']:,}",
    ])
    
    if 'format_split' in audit['post_clean']:
        lines.append("\n### By format (post-clean):")
        for fmt, count in audit['post_clean']['format_split'].items():
            lines.append(f"- {fmt}: {count} matches")
    
    with open(OUTPUT_DIR / 'data_audit.md', 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    
    print(f"Audit report written to {OUTPUT_DIR / 'data_audit.md'}")


if __name__ == '__main__':
    df, audit = clean_and_prepare()
    print("\n=== Post-Clean Summary ===")
    print(f"Total balls: {len(df):,}")
    print(f"Legal balls: {int(df['is_legal_delivery'].sum()):,}")
    print(f"Matches: {df['match_id'].nunique()}")
    print(f"Format split: {df.groupby('match_format')['match_id'].nunique().to_dict()}")

