"""
test_cricket_logic.py - Unit tests for core cricket logic rules in SupeRR Selector S2.

Tests:
1. Legal ball counting (excludes wides and no-balls from batter balls faced and over counts).
2. Bowler credit rules (extras: wides/no-balls charged to bowler; byes/leg-byes to team only).
3. Bowler wicket credit (bowled, caught, lbw, stump, hit-wicket credited; run-out, retired not credited).
4. Revised target handling (rain-reduced / DLS matches).
5. Chase required run rate (RRR) computation.
"""

import unittest
import pandas as pd
import numpy as np
from src.data import (
    BOWLER_CREDIT_DISMISSALS,
    BOWLER_NON_CREDIT_DISMISSALS,
    ILLEGAL_DELIVERY_EXTRAS,
    BOWLER_CHARGED_EXTRAS,
    compute_ball_level_runs,
    compute_innings_state
)


class TestCricketLogic(unittest.TestCase):
    
    def test_legal_ball_and_extras_accounting(self):
        """Verify that wides and no-balls are not legal balls, and bowler economy is exact."""
        mock_data = pd.DataFrame([
            # Ball 1: Dot ball
            {'match_id': 1, 'innings': 1, 'innings_ball_num': 1, 'runs': 0, 'extras_type': np.nan, 'extras1_runs': 0, 'extras_2_runs': 0, 'is_wicket': False, 'dismissal_type': np.nan},
            # Ball 2: Wide (1 extra run, 0 batter runs)
            {'match_id': 1, 'innings': 1, 'innings_ball_num': 2, 'runs': 0, 'extras_type': 'wide', 'extras1_runs': 1, 'extras_2_runs': 0, 'is_wicket': False, 'dismissal_type': np.nan},
            # Ball 3: Leg bye (2 runs) - must NOT credit batter, must NOT charge bowler
            {'match_id': 1, 'innings': 1, 'innings_ball_num': 3, 'runs': 2, 'extras_type': 'legbyes', 'extras1_runs': 2, 'extras_2_runs': 0, 'is_wicket': False, 'dismissal_type': np.nan},
            # Ball 4: Bye (1 run) - must NOT credit batter, must NOT charge bowler
            {'match_id': 1, 'innings': 1, 'innings_ball_num': 4, 'runs': 1, 'extras_type': 'byes', 'extras1_runs': 1, 'extras_2_runs': 0, 'is_wicket': False, 'dismissal_type': np.nan},
            # Ball 5: No-ball with 4 runs off the bat
            {'match_id': 1, 'innings': 1, 'innings_ball_num': 5, 'runs': 4, 'extras_type': 'Overstep', 'extras1_runs': 1, 'extras_2_runs': 0, 'is_wicket': False, 'dismissal_type': np.nan},
            # Ball 6: Six off the bat
            {'match_id': 1, 'innings': 1, 'innings_ball_num': 6, 'runs': 6, 'extras_type': np.nan, 'extras1_runs': 0, 'extras_2_runs': 0, 'is_wicket': False, 'dismissal_type': np.nan},
        ])
        
        result = compute_ball_level_runs(mock_data)
        
        # 1. Legal delivery checks
        self.assertTrue(result.loc[0, 'is_legal_delivery'])
        self.assertFalse(result.loc[1, 'is_legal_delivery'], "Wide must not be a legal delivery")
        self.assertTrue(result.loc[2, 'is_legal_delivery'], "Legbye is a legal delivery")
        self.assertTrue(result.loc[3, 'is_legal_delivery'], "Bye is a legal delivery")
        self.assertFalse(result.loc[4, 'is_legal_delivery'], "No-ball must not be a legal delivery")
        self.assertTrue(result.loc[5, 'is_legal_delivery'])
        
        # 2. Batter runs
        self.assertEqual(result.loc[0, 'batter_runs'], 0)
        self.assertEqual(result.loc[1, 'batter_runs'], 0)
        self.assertEqual(result.loc[2, 'batter_runs'], 0, "Legbye runs must not credit batter")
        self.assertEqual(result.loc[3, 'batter_runs'], 0, "Bye runs must not credit batter")
        self.assertEqual(result.loc[4, 'batter_runs'], 4, "Runs off bat on no-ball credit batter")
        self.assertEqual(result.loc[5, 'batter_runs'], 6)
        
        # 3. Bowler runs conceded
        self.assertEqual(result.loc[0, 'bowler_runs_conceded'], 0)
        self.assertEqual(result.loc[1, 'bowler_runs_conceded'], 1, "Wide run charged to bowler")
        self.assertEqual(result.loc[2, 'bowler_runs_conceded'], 0, "Legbyes NOT charged to bowler")
        self.assertEqual(result.loc[3, 'bowler_runs_conceded'], 0, "Byes NOT charged to bowler")
        self.assertEqual(result.loc[4, 'bowler_runs_conceded'], 5, "No-ball (4 bat + 1 nb) charged to bowler")
        self.assertEqual(result.loc[5, 'bowler_runs_conceded'], 6)
        
    def test_bowler_wicket_credit(self):
        """Verify bowler credit rules for different dismissal modes."""
        mock_data = pd.DataFrame([
            {'match_id': 1, 'innings': 1, 'innings_ball_num': 1, 'runs': 0, 'extras_type': np.nan, 'extras1_runs': 0, 'extras_2_runs': 0, 'is_wicket': True, 'dismissal_type': 'Bowled'},
            {'match_id': 1, 'innings': 1, 'innings_ball_num': 2, 'runs': 0, 'extras_type': np.nan, 'extras1_runs': 0, 'extras_2_runs': 0, 'is_wicket': True, 'dismissal_type': 'Caught'},
            {'match_id': 1, 'innings': 1, 'innings_ball_num': 3, 'runs': 0, 'extras_type': np.nan, 'extras1_runs': 0, 'extras_2_runs': 0, 'is_wicket': True, 'dismissal_type': 'LBW'},
            {'match_id': 1, 'innings': 1, 'innings_ball_num': 4, 'runs': 0, 'extras_type': np.nan, 'extras1_runs': 0, 'extras_2_runs': 0, 'is_wicket': True, 'dismissal_type': 'Stump'},
            {'match_id': 1, 'innings': 1, 'innings_ball_num': 5, 'runs': 0, 'extras_type': np.nan, 'extras1_runs': 0, 'extras_2_runs': 0, 'is_wicket': True, 'dismissal_type': 'RunOut'},
            {'match_id': 1, 'innings': 1, 'innings_ball_num': 6, 'runs': 0, 'extras_type': np.nan, 'extras1_runs': 0, 'extras_2_runs': 0, 'is_wicket': True, 'dismissal_type': 'Retire Out'},
            {'match_id': 1, 'innings': 1, 'innings_ball_num': 7, 'runs': 0, 'extras_type': np.nan, 'extras1_runs': 0, 'extras_2_runs': 0, 'is_wicket': True, 'dismissal_type': 'Obstructing the field'},
        ])
        
        result = compute_ball_level_runs(mock_data)
        
        self.assertTrue(result.loc[0, 'is_bowler_wicket'])
        self.assertTrue(result.loc[1, 'is_bowler_wicket'])
        self.assertTrue(result.loc[2, 'is_bowler_wicket'])
        self.assertTrue(result.loc[3, 'is_bowler_wicket'])
        self.assertFalse(result.loc[4, 'is_bowler_wicket'], "RunOut must not be credited to bowler")
        self.assertFalse(result.loc[5, 'is_bowler_wicket'], "Retire Out must not be credited to bowler")
        self.assertFalse(result.loc[6, 'is_bowler_wicket'], "Obstructing field must not be credited to bowler")

    def test_revised_target_and_rrr(self):
        """Verify DLS revised target and required run rate calculations."""
        # 14-over chase of 130
        df = pd.DataFrame([
            {
                'match_id': 100, 'innings': 2, 'innings_ball_num': 1,
                'total_runs': 1, 'batter_runs': 1, 'is_legal_delivery': True,
                'is_wicket': False, 'total_overs': 14.0, 'total_balls_innings': 84,
                'revised_target': 130, 'first_innings_total': 180,
                'overid': 1, 'batting_team_id': 1, 'win_team_id': 1
            },
            {
                'match_id': 100, 'innings': 2, 'innings_ball_num': 2,
                'total_runs': 4, 'batter_runs': 4, 'is_legal_delivery': True,
                'is_wicket': False, 'total_overs': 14.0, 'total_balls_innings': 84,
                'revised_target': 130, 'first_innings_total': 180,
                'overid': 1, 'batting_team_id': 1, 'win_team_id': 1
            }
        ])
        
        state = compute_innings_state(df)
        
        # Before ball 1: 0 runs scored, 84 balls remaining, target 130
        self.assertEqual(state.loc[0, 'chase_target'], 130)
        self.assertEqual(state.loc[0, 'cum_total_runs'], 0)
        self.assertEqual(state.loc[0, 'balls_remaining'], 84)
        self.assertEqual(state.loc[0, 'runs_needed'], 130)
        # RRR = 130 / (84/6) = 130 / 14 = 9.2857
        self.assertAlmostEqual(state.loc[0, 'required_run_rate'], 130 / 14.0, places=3)
        
        # Before ball 2: 1 run scored, 83 balls remaining, target 130
        self.assertEqual(state.loc[1, 'cum_total_runs'], 1)
        self.assertEqual(state.loc[1, 'balls_remaining'], 83)
        self.assertEqual(state.loc[1, 'runs_needed'], 129)
        self.assertAlmostEqual(state.loc[1, 'required_run_rate'], 129 / (83 / 6.0), places=3)


if __name__ == '__main__':
    unittest.main()

