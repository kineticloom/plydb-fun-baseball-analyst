# Baseball Data Dictionary

Reference for the Parquet files written by `scripts/download_baseball_data.py`
via pybaseball.

Files are written in Hive-partitioned layout under `data/pybaseball/`. The
`Season` column is always the primary temporal join key. Player identity is
linked through MLBAM IDs (Statcast) or player names (FanGraphs/BBRef), with
`player_ids` as the cross-system bridge table.

---

## Table of contents

- [statcast](#statcastparquet)
- [batting\_stats](#batting_statsparquet)
- [pitching\_stats](#pitching_statsparquet)
- [batting\_stats\_bref](#batting_stats_brefparquet)
- [pitching\_stats\_bref](#pitching_stats_brefparquet)
- [team\_batting](#team_battingparquet)
- [team\_pitching](#team_pitchingparquet)
- [standings](#standingsparquet)
- [schedule](#scheduleparquet)
- [player\_ids](#player_idsparquet)
- [PlyDB table names](#plydb-table-names)
- [Common join patterns](#common-join-patterns)

---

## `statcast.parquet`

**Path:** `data/pybaseball/statcast/Season={year}/Month={month}/statcast.parquet`

One row per pitch. The richest dataset: every pitch thrown in MLB since 2008
with physical measurements, plate location, batted ball metrics, game state,
and outcome. Statcast-specific fields (exit velocity, spin rate, launch angle)
are only populated from **2015 onward**.

To filter to regular season only: `WHERE game_type = 'R'`.
To filter to plate appearance outcomes: `WHERE events IS NOT NULL`.
To filter to balls in play: `WHERE type = 'X'`.

### Identity and game context

| Column | Type | Description |
|---|---|---|
| `game_pk` | `int64` | MLB game unique identifier |
| `game_date` | `date` | Game date (YYYY-MM-DD) |
| `game_year` | `int64` | Season year |
| `game_type` | `string` | `'R'`=regular season, `'F'`=wild card, `'D'`=division series, `'L'`=LCS, `'W'`=World Series |
| `home_team` | `string` | Home team abbreviation (e.g. `'NYY'`, `'LAD'`) |
| `away_team` | `string` | Away team abbreviation |
| `inning` | `int64` | Inning number (1-indexed; extra innings exceed 9) |
| `inning_topbot` | `string` | `'Top'` = away team batting; `'Bot'` = home team batting |
| `at_bat_number` | `int64` | Plate appearance number within the game (1-indexed) |
| `pitch_number` | `int64` | Pitch number within the current plate appearance |

### Player identity

| Column | Type | Description |
|---|---|---|
| `batter` | `int64` | MLBAM numeric ID of the batter. Join to `player_ids.key_mlbam` to get name |
| `pitcher` | `int64` | MLBAM numeric ID of the pitcher. Join to `player_ids.key_mlbam` to get name |
| `player_name` | `string` | Pitcher's name (format: `"Last, First"`). This is the **pitcher**, not the batter |
| `stand` | `string` | Batter handedness: `'L'` or `'R'` |
| `p_throws` | `string` | Pitcher throwing arm: `'L'` or `'R'` |
| `home_score` | `int64` | Home team score before the pitch |
| `away_score` | `int64` | Away team score before the pitch |

### Count and game state

| Column | Type | Description |
|---|---|---|
| `balls` | `int64` | Ball count before this pitch (0–3) |
| `strikes` | `int64` | Strike count before this pitch (0–2) |
| `outs_when_up` | `int64` | Outs when this batter came to the plate (0, 1, or 2) |
| `on_1b` | `int64` | MLBAM ID of runner on first base, or NULL if empty |
| `on_2b` | `int64` | MLBAM ID of runner on second base, or NULL if empty |
| `on_3b` | `int64` | MLBAM ID of runner on third base, or NULL if empty |

### Pitch outcome

| Column | Type | Description |
|---|---|---|
| `type` | `string` | Simplified outcome: `'S'`=strike, `'B'`=ball, `'X'`=ball in play |
| `description` | `string` | Per-pitch result: `'ball'`, `'called_strike'`, `'swinging_strike'`, `'foul'`, `'foul_tip'`, `'hit_into_play'`, etc. |
| `events` | `string` | Plate appearance outcome — **NULL on all non-final pitches**. Values: `'single'`, `'double'`, `'triple'`, `'home_run'`, `'strikeout'`, `'walk'`, `'hit_by_pitch'`, `'field_out'`, `'grounded_into_double_play'`, `'sac_fly'`, `'field_error'`, etc. |
| `zone` | `int64` | Strike zone region bucket (1–9 = in-zone, 11–14 = out-of-zone edges) |
| `bb_type` | `string` | Batted ball type: `'ground_ball'`, `'fly_ball'`, `'line_drive'`, `'popup'`. NULL if not a ball in play |
| `hit_location` | `int64` | Fielding position of the fielder who made the play (1–9), or NULL |
| `if_fielding_alignment` | `string` | Infield alignment: `'Standard'`, `'Shift'`, `'Strategic'` |
| `of_fielding_alignment` | `string` | Outfield alignment: `'Standard'`, `'4th outfielder'`, `'Strategic'` |

### Pitch physics

| Column | Type | Description |
|---|---|---|
| `pitch_type` | `string` | Pitch type code: `'FF'`=4-seam fastball, `'SI'`=sinker, `'FC'`=cutter, `'SL'`=slider, `'CH'`=changeup, `'CU'`=curveball, `'FS'`=splitter, `'KC'`=knuckle curve, `'KN'`=knuckleball |
| `pitch_name` | `string` | Human-readable pitch name, e.g. `"4-Seam Fastball"`, `"Slider"` |
| `release_speed` | `float64` | Velocity at release (mph) |
| `effective_speed` | `float64` | Perceived velocity accounting for extension (mph) |
| `release_spin_rate` | `float64` | Spin rate at release (rpm) |
| `spin_axis` | `int64` | Spin axis direction (0–360 degrees) |
| `release_extension` | `float64` | Distance from rubber to release point (feet); higher = more extension |
| `release_pos_x` | `float64` | Horizontal release position (feet), from catcher's perspective |
| `release_pos_y` | `float64` | Distance from home plate to release point (feet) |
| `release_pos_z` | `float64` | Vertical release height (feet above ground) |
| `pfx_x` | `float64` | Horizontal movement vs. spinless pitch (inches); positive = arm-side for RHP |
| `pfx_z` | `float64` | Vertical movement vs. spinless pitch (inches); positive = rise |
| `vx0` / `vy0` / `vz0` | `float64` | Initial pitch velocity components (ft/s) at y=50 feet |
| `ax` / `ay` / `az` | `float64` | Pitch acceleration components (ft/s²) |

### Plate location

| Column | Type | Description |
|---|---|---|
| `plate_x` | `float64` | Horizontal position at front of plate (feet); 0=center; positive=toward right-hand batter |
| `plate_z` | `float64` | Vertical position at front of plate (feet above ground) |
| `sz_top` | `float64` | Top of the batter's strike zone (feet) for this PA |
| `sz_bot` | `float64` | Bottom of the batter's strike zone (feet) for this PA |

### Batted ball metrics (2015+)

| Column | Type | Description |
|---|---|---|
| `launch_speed` | `float64` | Exit velocity off the bat (mph). NULL before 2015 |
| `launch_angle` | `float64` | Vertical launch angle (degrees): negative=groundball, 10–25=line drive, 25–50=fly ball. NULL before 2015 |
| `launch_speed_angle` | `int64` | Contact quality code: `1`=weak, `2`=topped, `3`=under, `4`=flare/burner, `5`=solid contact, `6`=barrel |
| `hit_distance_sc` | `float64` | Projected hit distance (feet) |
| `hc_x` | `float64` | Hit coordinate X (pixels, spray chart scale) |
| `hc_y` | `float64` | Hit coordinate Y (pixels, spray chart scale) |

### Expected stats and run value (2015+)

| Column | Type | Description |
|---|---|---|
| `estimated_ba_using_speedangle` | `float64` | Expected batting average (xBA) based on launch speed and angle |
| `estimated_woba_using_speedangle` | `float64` | Expected wOBA (xwOBA) based on launch speed and angle |
| `woba_value` | `float64` | wOBA run value for this PA outcome. Average over PAs to compute wOBA. NULL on non-PA-ending pitches |
| `woba_denom` | `float64` | wOBA denominator flag (1 if this PA counts toward wOBA, 0 otherwise) |
| `babip_value` | `float64` | BABIP contribution of this outcome |
| `iso_value` | `float64` | Isolated power contribution of this outcome |
| `delta_run_exp` | `float64` | Change in run expectancy from this pitch (positive = batter gained) |
| `delta_home_win_exp` | `float64` | Change in home team win probability from this pitch |

---

## `batting_stats.parquet`

**Path:** `data/pybaseball/batting_stats/Season={year}/batting_stats.parquet`

FanGraphs season-level batting statistics. One row per player per season
(when downloaded with `ind=1`). Includes traditional counting stats, rate
stats, park-adjusted metrics, plate discipline, and WAR. Players traded
mid-season have one row per team plus a totals row with `Team = '---'`.

Statcast-era fields (Hard%, Barrel%, xwOBA) are NULL before ~2015.

### Key columns

| Column | Type | Description |
|---|---|---|
| `Season` | `int64` | Season year |
| `Name` | `string` | Player full name |
| `Team` | `string` | Team abbreviation (FanGraphs format); `'---'` = multi-team totals |
| `Age` | `int64` | Age as of June 30 |
| `G` | `int64` | Games played |
| `PA` | `int64` | Plate appearances |
| `AB` | `int64` | At-bats |
| `H` | `int64` | Hits |
| `1B` | `int64` | Singles |
| `2B` | `int64` | Doubles |
| `3B` | `int64` | Triples |
| `HR` | `int64` | Home runs |
| `R` | `int64` | Runs scored |
| `RBI` | `int64` | Runs batted in |
| `BB` | `int64` | Walks |
| `IBB` | `int64` | Intentional walks |
| `SO` | `int64` | Strikeouts |
| `HBP` | `int64` | Hit by pitch |
| `SB` | `int64` | Stolen bases |
| `CS` | `int64` | Caught stealing |
| `AVG` | `float64` | Batting average (H/AB) |
| `OBP` | `float64` | On-base percentage |
| `SLG` | `float64` | Slugging percentage |
| `OPS` | `float64` | On-base plus slugging |
| `wOBA` | `float64` | Weighted on-base average (~.320 = league average) |
| `wRC+` | `float64` | **Park-adjusted offense. 100 = league average. Best cross-park/era batting metric.** |
| `BABIP` | `float64` | Batting average on balls in play |
| `ISO` | `float64` | Isolated power (SLG − AVG) |
| `BB%` | `float64` | Walk rate (~8.5% = league average) |
| `K%` | `float64` | Strikeout rate (~22% = league average) |
| `BB/K` | `float64` | Walk-to-strikeout ratio |
| `LD%` | `float64` | Line drive rate |
| `GB%` | `float64` | Ground ball rate |
| `FB%` | `float64` | Fly ball rate |
| `IFFB%` | `float64` | Infield fly ball rate |
| `HR/FB` | `float64` | Home run per fly ball rate |
| `Hard%` | `float64` | Hard contact rate (Statcast: barrel% more precise) |
| `Med%` | `float64` | Medium contact rate |
| `Soft%` | `float64` | Soft contact rate |
| `Pull%` | `float64` | Pull rate (% of batted balls pulled) |
| `Cent%` | `float64` | Centered batted ball rate |
| `Oppo%` | `float64` | Opposite field rate |
| `O-Swing%` | `float64` | Chase rate (swings on pitches outside strike zone) |
| `Z-Swing%` | `float64` | Zone swing rate |
| `Swing%` | `float64` | Overall swing rate |
| `O-Contact%` | `float64` | Contact rate on pitches outside zone |
| `Z-Contact%` | `float64` | Contact rate on pitches in zone |
| `Contact%` | `float64` | Overall contact rate on swings |
| `Zone%` | `float64` | Rate of pitches seen in the strike zone |
| `SwStr%` | `float64` | Swinging strike rate |
| `F-Strike%` | `float64` | First-pitch strike rate (as seen by batter) |
| `WAR` | `float64` | FanGraphs WAR (fWAR): offense + baserunning + defense |
| `Dollars` | `float64` | Estimated market value in dollars |
| `IDfg` | `int64` | FanGraphs player ID. Matches `player_ids.key_fangraphs` |

---

## `pitching_stats.parquet`

**Path:** `data/pybaseball/pitching_stats/Season={year}/pitching_stats.parquet`

FanGraphs season-level pitching statistics. One row per player per season.
Includes traditional stats, ERA estimators (FIP, xFIP, SIERA), pitch mix,
batted ball profile, plate discipline, and WAR.

### Key columns

| Column | Type | Description |
|---|---|---|
| `Season` | `int64` | Season year |
| `Name` | `string` | Player full name |
| `Team` | `string` | Team abbreviation |
| `Age` | `int64` | Age as of June 30 |
| `W` | `int64` | Wins |
| `L` | `int64` | Losses |
| `ERA` | `float64` | Earned run average. Affected by defense and luck |
| `G` | `int64` | Games pitched |
| `GS` | `int64` | Games started |
| `SV` | `int64` | Saves |
| `BS` | `int64` | Blown saves |
| `IP` | `float64` | Innings pitched |
| `TBF` | `int64` | Total batters faced |
| `H` | `int64` | Hits allowed |
| `HR` | `int64` | Home runs allowed |
| `BB` | `int64` | Walks |
| `SO` | `int64` | Strikeouts |
| `WHIP` | `float64` | Walks + hits per inning pitched |
| `BABIP` | `float64` | Batting average on balls in play against |
| `LOB%` | `float64` | Left on base percentage (strand rate) |
| `K/9` | `float64` | Strikeouts per 9 innings |
| `BB/9` | `float64` | Walks per 9 innings |
| `K/BB` | `float64` | Strikeout-to-walk ratio |
| `HR/9` | `float64` | Home runs per 9 innings |
| `K%` | `float64` | Strikeout rate per batter faced |
| `BB%` | `float64` | Walk rate per batter faced |
| `K-BB%` | `float64` | **K% minus BB%. Best single command+stuff rate metric** |
| `FIP` | `float64` | **Fielding Independent Pitching. ERA-scale, defense-neutral. Lower is better** |
| `xFIP` | `float64` | Expected FIP (normalises HR/FB to league average) |
| `SIERA` | `float64` | Skill-Interactive ERA. Most accurate FG ERA estimator |
| `GB%` | `float64` | Ground ball rate induced |
| `FB%` | `float64` | Fly ball rate induced |
| `LD%` | `float64` | Line drive rate allowed |
| `HR/FB` | `float64` | Home run per fly ball rate (~11% = league avg; regresses) |
| `SwStr%` | `float64` | Swinging strike rate induced |
| `O-Swing%` | `float64` | Chase rate induced (opposing batters swinging out of zone) |
| `Z-Swing%` | `float64` | Zone swing rate |
| `Contact%` | `float64` | Contact rate on swings against |
| `Zone%` | `float64` | Rate of pitches thrown in the strike zone |
| `F-Strike%` | `float64` | First-pitch strike rate |
| `FA%` | `float64` | 4-seam fastball usage share |
| `vFA` | `float64` | 4-seam fastball average velocity (mph) |
| `SI%` | `float64` | Sinker usage share |
| `vSI` | `float64` | Sinker average velocity |
| `CT%` | `float64` | Cutter usage share |
| `vCT` | `float64` | Cutter average velocity |
| `CH%` | `float64` | Changeup usage share |
| `vCH` | `float64` | Changeup average velocity |
| `SL%` | `float64` | Slider usage share |
| `vSL` | `float64` | Slider average velocity |
| `CU%` | `float64` | Curveball usage share |
| `vCU` | `float64` | Curveball average velocity |
| `WAR` | `float64` | FanGraphs WAR (fWAR) using FIP |
| `IDfg` | `int64` | FanGraphs player ID. Matches `player_ids.key_fangraphs` |

---

## `batting_stats_bref.parquet`

**Path:** `data/pybaseball/batting_stats_bref/Season={year}/batting_stats_bref.parquet`

Baseball Reference season-level batting statistics (2008+). One row per player.
Useful as a cross-reference to FanGraphs data. **Note:** the pybaseball
`batting_stats_bref` output does not include `OPS+`; use FanGraphs
`batting_stats` (`wRC+`) for park-adjusted batting metrics.

Team column is `Tm` (not `Team`). Player MLBAM ID is in `mlbID`.

### Key columns

| Column | Type | Description |
|---|---|---|
| `Name` | `string` | Player full name |
| `Age` | `int64` | Age |
| `Tm` | `string` | Team abbreviation (Baseball Reference format) |
| `Lev` | `string` | Level (e.g. `'MLB'`) |
| `G` | `int64` | Games played |
| `PA` | `int64` | Plate appearances |
| `AB` | `int64` | At-bats |
| `R` | `int64` | Runs |
| `H` | `int64` | Hits |
| `2B` | `int64` | Doubles |
| `3B` | `int64` | Triples |
| `HR` | `int64` | Home runs |
| `RBI` | `int64` | RBI |
| `SB` | `int64` | Stolen bases |
| `CS` | `int64` | Caught stealing |
| `BB` | `int64` | Walks |
| `SO` | `int64` | Strikeouts |
| `BA` | `float64` | Batting average |
| `OBP` | `float64` | On-base percentage |
| `SLG` | `float64` | Slugging |
| `OPS` | `float64` | On-base plus slugging |
| `GDP` | `int64` | Grounded into double plays |
| `HBP` | `int64` | Hit by pitch |
| `SH` | `int64` | Sacrifice hits |
| `SF` | `int64` | Sacrifice flies |
| `IBB` | `int64` | Intentional walks |
| `mlbID` | `int64` | MLBAM player ID. Matches `player_ids.key_mlbam` and `statcast.batter/pitcher` |

---

## `pitching_stats_bref.parquet`

**Path:** `data/pybaseball/pitching_stats_bref/Season={year}/pitching_stats_bref.parquet`

Baseball Reference season-level pitching statistics (2008+). One row per player.
**Note:** the pybaseball `pitching_stats_bref` output does not include `ERA+`;
use FanGraphs `pitching_stats` (`FIP`, `xFIP`) for park-adjusted metrics.

Team column is `Tm` (not `Team`). Player MLBAM ID is in `mlbID`.

### Key columns

| Column | Type | Description |
|---|---|---|
| `Name` | `string` | Player full name |
| `Age` | `int64` | Age |
| `Tm` | `string` | Team abbreviation (Baseball Reference format) |
| `Lev` | `string` | Level (e.g. `'MLB'`) |
| `W` | `int64` | Wins |
| `L` | `int64` | Losses |
| `ERA` | `float64` | Earned run average |
| `G` | `int64` | Games |
| `GS` | `int64` | Games started |
| `SV` | `int64` | Saves |
| `IP` | `float64` | Innings pitched |
| `H` | `int64` | Hits allowed |
| `R` | `int64` | Runs allowed |
| `ER` | `int64` | Earned runs |
| `HR` | `int64` | Home runs allowed |
| `BB` | `int64` | Walks |
| `IBB` | `int64` | Intentional walks |
| `SO` | `int64` | Strikeouts |
| `HBP` | `int64` | Hit by pitch |
| `BF` | `int64` | Batters faced |
| `WHIP` | `float64` | Walks + hits per inning |
| `BAbip` | `float64` | Batting average on balls in play against |
| `SO9` | `float64` | Strikeouts per 9 innings |
| `SO/W` | `float64` | Strikeout-to-walk ratio |
| `GB/FB` | `float64` | Ground ball to fly ball ratio |
| `mlbID` | `int64` | MLBAM player ID. Matches `player_ids.key_mlbam` and `statcast.pitcher` |

---

## `team_batting.parquet`

**Path:** `data/pybaseball/team_batting/Season={year}/team_batting.parquet`

FanGraphs team-level batting statistics. One row per team per season. Same
columns as `batting_stats` but aggregated across the full roster. Use for
franchise-level offensive comparisons.

Key columns: `Season`, `Team`, `G`, `PA`, `HR`, `R`, `RBI`, `AVG`, `OBP`,
`SLG`, `wOBA`, `wRC+`, `BB%`, `K%`, `WAR`. See `batting_stats` column
definitions for semantics.

---

## `team_pitching.parquet`

**Path:** `data/pybaseball/team_pitching/Season={year}/team_pitching.parquet`

FanGraphs team-level pitching statistics (all pitchers combined). One row per
team per season. Same columns as `pitching_stats` but aggregated across the
full staff. Use for franchise pitching comparisons.

Key columns: `Season`, `Team`, `ERA`, `FIP`, `xFIP`, `WHIP`, `K%`, `BB%`,
`K-BB%`, `GB%`, `SwStr%`, `WAR`. See `pitching_stats` column definitions for
semantics.

---

## `standings.parquet`

**Path:** `data/pybaseball/standings/Season={year}/standings.parquet`

Division standings from Baseball Reference. One row per team. All divisions
concatenated with a `DivisionIndex` column. Covers 1969 (when divisions were
introduced) to present.

### Division index mapping (post-1994)

| DivisionIndex | Division |
|---|---|
| `0` | AL East |
| `1` | AL Central |
| `2` | AL West |
| `3` | NL East |
| `4` | NL Central |
| `5` | NL West |

> Pre-1994 seasons had only two divisions per league. Pre-1969 had no
> divisions. DivisionIndex values for these eras will differ.

### Columns

| Column | Type | Description |
|---|---|---|
| `Season` | `int64` | Season year (added by download script) |
| `DivisionIndex` | `int64` | Division identifier (see mapping above) |
| `Tm` | `string` | Full team name (e.g. `'New York Yankees'`). May include suffix markers for clinching (e.g. `'x-New York Yankees'`) |
| `W` | `int64` | Wins |
| `L` | `int64` | Losses |
| `W-L%` | `float64` | Win percentage (e.g. `0.580`) |
| `GB` | `float64` | Games behind the division leader. `0.0` for the leader itself |

---

## `schedule.parquet`

**Path:** `data/pybaseball/schedule/Season={year}/Team={team}/schedule.parquet`

Game-by-game schedule and results from Baseball Reference. One row per game.
Covers completed and (for in-progress seasons) upcoming games.

### Columns

| Column | Type | Description |
|---|---|---|
| `Season` | `int64` | Season year (added by download script) |
| `Team` | `string` | Team abbreviation (added by download script) |
| `Gm#` | `int64` | Game number within the season |
| `Date` | `string` | Game date string (may include day of week) |
| `Tm` | `string` | Tracked team abbreviation |
| `Home_Away` | `string` | `'@'` = away game; `'Home'` = home game |
| `Opp` | `string` | Opponent team abbreviation |
| `W/L` | `string` | Result: `'W'`, `'L'`, `'T'`, `'W-wo'` (walk-off win), `'L-wo'` |
| `R` | `int64` | Runs scored by tracked team |
| `RA` | `int64` | Runs allowed |
| `Inn` | `int64` | Innings played (9 for regulation; higher for extras) |
| `W-L` | `string` | Running season record after this game, e.g. `'40-30'` |
| `Rank` | `int64` | Division standing rank after this game |
| `GB` | `string` | Games behind division leader after this game |
| `Win` | `string` | Winning pitcher name |
| `Loss` | `string` | Losing pitcher name |
| `Save` | `string` | Save pitcher name (empty if no save) |
| `Time` | `string` | Game duration (H:MM format) |
| `D/N` | `string` | `'D'` = day game; `'N'` = night game |
| `Attendance` | `int64` | Paid attendance |
| `Streak` | `int64` | Win/loss streak at end of game. Positive = win streak length; negative = loss streak length |

---

## `player_ids.parquet`

**Path:** `data/pybaseball/player_ids/player_ids.parquet`

Chadwick Bureau cross-system player ID register. One row per person. Contains
every person in the Chadwick database, not just MLB players.

This is the **essential bridge table** for joining Statcast data (which uses
numeric MLBAM IDs) to player names and to FanGraphs or BBRef data.

### Key columns

| Column | Type | Description |
|---|---|---|
| `key_mlbam` | `int64` | MLBAM (MLB Advanced Media) numeric ID. Used in Statcast's `batter` and `pitcher` columns |
| `key_retro` | `string` | Retrosheet ID (e.g. `'troutm001'`) |
| `key_bbref` | `string` | Baseball Reference ID (e.g. `'troutmi01'`) |
| `key_fangraphs` | `int64` | FanGraphs ID. Matches `IDfg` in `batting_stats` and `pitching_stats` |
| `name_last` | `string` | Last name |
| `name_first` | `string` | First name |
| `mlb_played_first` | `int64` | First MLB season |
| `mlb_played_last` | `int64` | Most recent MLB season |

---

## PlyDB table names

When querying via PlyDB using `plydb-config-example.json`, table names use
the format `{database_key}.default.{database_key}`:

| Dataset | PlyDB table |
|---|---|
| Statcast | `statcast.default.statcast` |
| FanGraphs batting | `batting_stats.default.batting_stats` |
| FanGraphs pitching | `pitching_stats.default.pitching_stats` |
| BBRef batting | `batting_stats_bref.default.batting_stats_bref` |
| BBRef pitching | `pitching_stats_bref.default.pitching_stats_bref` |
| Team batting | `team_batting.default.team_batting` |
| Team pitching | `team_pitching.default.team_pitching` |
| Standings | `standings.default.standings` |
| Schedule | `schedule.default.schedule` |
| Player IDs | `player_ids.default.player_ids` |

---

## Common join patterns

### Look up batter name from Statcast

```sql
SELECT
    s.game_date,
    p.name_first || ' ' || p.name_last  AS batter_name,
    s.pitch_name,
    s.release_speed,
    s.launch_speed,
    s.launch_angle,
    s.events
FROM statcast.default.statcast s
JOIN player_ids.default.player_ids p
  ON s.batter = p.key_mlbam
WHERE s.events IS NOT NULL
  AND s.game_type = 'R'
  AND s.game_year = 2024
```

### Statcast barrel rate by pitcher (2015+)

```sql
SELECT
    p.name_first || ' ' || p.name_last        AS pitcher_name,
    s.game_year                                AS season,
    COUNT(*)                                   AS batted_balls,
    SUM(CASE WHEN s.launch_speed_angle = 6
             THEN 1 ELSE 0 END)                AS barrels,
    ROUND(100.0 * SUM(CASE WHEN s.launch_speed_angle = 6
                           THEN 1 ELSE 0 END) / COUNT(*), 1) AS barrel_pct
FROM statcast.default.statcast s
JOIN player_ids.default.player_ids p
  ON s.pitcher = p.key_mlbam
WHERE s.type = 'X'
  AND s.game_type = 'R'
  AND s.game_year >= 2015
GROUP BY pitcher_name, season
HAVING COUNT(*) >= 100
ORDER BY season DESC, barrel_pct ASC
```

### FanGraphs batting: top wRC+ in a season

```sql
SELECT
    Season,
    Name,
    Team,
    PA,
    AVG,
    "wRC+",
    WAR
FROM batting_stats.default.batting_stats
WHERE Season = 2024
  AND PA >= 300
ORDER BY "wRC+" DESC
LIMIT 20
```

### FanGraphs pitching: FIP leaders (starters only)

```sql
SELECT
    Season,
    Name,
    Team,
    GS,
    IP,
    ERA,
    FIP,
    xFIP,
    "K%",
    "BB%",
    "K-BB%",
    WAR
FROM pitching_stats.default.pitching_stats
WHERE Season = 2024
  AND GS >= 10
  AND IP >= 50
ORDER BY FIP ASC
LIMIT 20
```

### Join FanGraphs stats to Statcast via player_ids

```sql
-- Average exit velocity for FanGraphs batting leaders
SELECT
    b.Name,
    b.Season,
    b."wRC+",
    b.WAR,
    AVG(s.launch_speed)  AS avg_exit_velo
FROM batting_stats.default.batting_stats b
JOIN player_ids.default.player_ids ids
  ON b.IDfg = ids.key_fangraphs
JOIN statcast.default.statcast s
  ON ids.key_mlbam = s.batter
 AND b.Season = s.game_year
WHERE b.Season = 2024
  AND b.PA >= 300
  AND s.type = 'X'
  AND s.game_type = 'R'
GROUP BY b.Name, b.Season, b."wRC+", b.WAR
ORDER BY avg_exit_velo DESC
```

### Standings: best win percentage by division

```sql
SELECT
    Season,
    DivisionIndex,
    Tm,
    W,
    L,
    "W-L%",
    GB
FROM standings.default.standings
WHERE Season BETWEEN 2019 AND 2024
ORDER BY Season, DivisionIndex, "W-L%" DESC
```

### Team win streak analysis from schedule

```sql
-- Longest win streaks for a team in a season
SELECT
    Season,
    Team,
    MAX(CAST(REPLACE(Streak, '+', '') AS INT))  AS longest_win_streak
FROM schedule.default.schedule
WHERE "W/L" IN ('W', 'W-wo')
GROUP BY Season, Team
ORDER BY longest_win_streak DESC
LIMIT 20
```

### BBRef pitching: dominant seasons by ERA (starters only)

> **Note:** `ERA+` is not available from the pybaseball `pitching_stats_bref`
> function. Use FanGraphs `pitching_stats` (`FIP`, `xFIP`) for park-adjusted
> metrics. BBRef data is useful for cross-referencing counting stats and WHIP.

```sql
SELECT
    Name,
    Season,
    Tm,
    W,
    L,
    IP,
    ERA,
    WHIP,
    SO,
    BB
FROM pitching_stats_bref.default.pitching_stats_bref
WHERE IP >= 100
ORDER BY ERA ASC
LIMIT 20
```
