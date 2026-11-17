# Data Audit Report — SupeRR Selector S2

## 1. Raw Data Summary

- Total balls in ball_by_ball.csv: **200,999**
- Unique matches in ball_by_ball: **867**
- Matches in matches.csv: **883**
- Total competitions: **141**
- Total unique players: **1217**
- Innings values: [1, 2, 3, 4]
- Super over balls (innings 3/4): **38**

## 2. Format Split

- T20 (IPL) matches: **401**
- T20I matches: **482**

## 3. Extras Analysis

### How `runs` column works:
- `runs` = runs scored off the bat by the batter
- `extras1_runs` = runs from the extra (1 for a wide, leg-bye runs, etc.)
- `extras_2_runs` = additional extras (overthrows, etc.)

- Wides: **7,714** balls
- No-balls (Overstep): **576** balls
- Leg-byes: **2,748** balls
- Byes: **529** balls
- Other extras: **264** balls
- Penalty: **1** ball

### Leg-bye runs check:
- Leg-bye balls with runs > 0: 1
- Leg-bye balls with runs = 0: 2747

### Bye runs check:
- Bye balls with runs > 0: 0
- Bye balls with runs = 0: 529

### Rules applied:
- **Batter runs** = `runs` column (already 0 on legbye/bye balls in the data)
- **Bowler conceded** = batter_runs + extras from wides + extras from no-balls
- **Byes and leg-byes** credited to team total, NOT batter or bowler
- **Legal delivery** = any ball that is not a wide or no-ball

## 4. Dismissals

- Total wickets: **10,881**
- Bowler-credited wickets: **10,272**
- Non-striker run-outs: **271**

### By type:
- Caught: 7,557 (✅ bowler)
- Bowled: 1,775 (✅ bowler)
- LBW: 709 (✅ bowler)
- RunOut: 600 (❌ not bowler)
- Stump: 214 (✅ bowler)
- Hit Wicket: 17 (✅ bowler)
- Retire Out: 6 (❌ not bowler)
- Obstracting the field: 2 (❌ not bowler)
- Obstructing the field: 1 (❌ not bowler)

### Rules applied:
- Bowler gets credit for: Bowled, Caught, LBW, Stump, Hit Wicket
- Bowler does NOT get credit for: RunOut, Retire Out, Obstructing the field
- Non-striker run-outs attributed to dismissed_player_id (not striker)

## 5. Duplicate Check

- Duplicate rows by (match_id, innings, innings_ball_num): **0**
- Duplicate rows by (match_id, innings, overid, over_ball_num): **0**

## 6. Name Collisions

- Players with same name but different IDs: **7**
- Resolution: always key on `player_id`, never on name

### Examples:
- **Abdul Samad**: [{'player_id': 7446, 'player_name': 'Abdul Samad', 'team_name': 'Sunrisers Hyderabad'}, {'player_id': 6922, 'player_name': 'Abdul Samad', 'team_name': 'Pakistan A'}, {'player_id': 7446, 'player_name': 'Abdul Samad', 'team_name': 'Lucknow Super Giants'}, {'player_id': 6922, 'player_name': 'Abdul Samad', 'team_name': 'Pakistan'}]
- **Bashir Ahmad**: [{'player_id': 39479, 'player_name': 'Bashir Ahmad', 'team_name': 'Afghanistan A'}, {'player_id': 29833, 'player_name': 'Bashir Ahmad', 'team_name': 'Afghanistan'}]
- **Basil Hameed**: [{'player_id': 8638, 'player_name': 'Basil Hameed', 'team_name': 'United Arab Emirates'}, {'player_id': 39444, 'player_name': 'Basil Hameed', 'team_name': 'United Arab Emirates'}]
- **Haider Ali**: [{'player_id': 7338, 'player_name': 'Haider Ali', 'team_name': 'Pakistan'}, {'player_id': 7338, 'player_name': 'Haider Ali', 'team_name': 'Pakistan A'}, {'player_id': 28756, 'player_name': 'Haider Ali', 'team_name': 'United Arab Emirates'}]
- **Mohammad Ali**: [{'player_id': 3083, 'player_name': 'Mohammad Ali', 'team_name': 'Pakistan'}, {'player_id': 20229, 'player_name': 'Mohammad Ali', 'team_name': 'Pakistan'}]

## 7. Multi-Team Players

- Players appearing for multiple teams: **372**
- This is expected (IPL franchise + national team)

## 8. DLS/Revised Matches

- Matches with revised target: **23**
- Handling: use revised_target and revised overs for pressure/RRR calculations

## 9. Abandoned/No-Result Matches

- Count: **40**
- Results: ['Match Abandoned', 'No Result', 'No Result', 'Match Abandoned', 'Match Abandoned']
- Handling: excluded from all analysis

## 10. Matches Without Winner

- Count: **1**
- Handling: kept in dataset but excluded from WP model training

## 11. Stage Distribution

- League: 620
- Others: 226
- Final: 12
- Qualifier: 10
- Super 4: 6
- Eliminator: 5
- Semi Final: 4

## 12. Cleaning Summary

- **Before cleaning**: 200,999 balls, 867 matches
- **After cleaning**: 199,988 balls, 843 matches
- **Legal balls**: 191,727

### By format (post-clean):
- T20: 392 matches
- T20I: 451 matches