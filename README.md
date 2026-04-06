# Baseball Analyst

Accompanying [blog post](https://www.plydb.com/blog/plydb-fun-baseball-analyst/).

---

Bring your own AI agent and ask questions about MLB data in plain English — no
SQL required.

```
> Which pitcher had the best strikeout-to-walk ratio over the last three seasons?
> What teams outperform their Pythagorean win expectation most consistently?
> How does Shohei Ohtani's exit velocity compare to league average by pitch type?
```

Under the hood: [pybaseball](https://github.com/jldbc/pybaseball) downloads the
data, [PlyDB](https://www.plydb.com/) gives your agent unified SQL access to
local data files, and your agent handles the rest — no warehouse, no ETL, no
cloud.

---

Demo with Claude

https://github.com/user-attachments/assets/c3d5c3da-fa46-48b5-918e-17e6b6584af2

---

## Workflow

1. [Install prerequisites](#step-1--install-prerequisites)
2. [Download baseball data](#step-2--download-baseball-data)
3. [Configure PlyDB](#step-3--configure-plydb)
4. [Start analyzing](#step-4--start-analyzing)

---

## Step 1 — Install prerequisites

### PlyDB

PlyDB is the database gateway that gives your AI agent unified SQL access to
local data files. Your agent translates your questions into SQL; PlyDB executes
them.

**New to PlyDB?** The [PlyDB quickstart](https://www.plydb.com/docs/quickstart/)
walks through installation, config, and your first queries end-to-end.

### pybaseball (Python)

The download script requires Python 3.8+ with `pandas` and `pyarrow`. Install
them first, then install pybaseball from source (pip releases lag the repo):

```bash
python -m pip install pandas pyarrow
git clone https://github.com/jldbc/pybaseball
cd pybaseball && python -m pip install -e .
```

> Use `python -m pip` (not bare `pip`) to ensure packages are installed into the
> same Python environment you'll use to run the script.

---

## Step 2 — Download baseball data

`scripts/download_baseball_data.py` fetches data via pybaseball and writes it as
Parquet files (zstd compressed) to `data/pybaseball/`.

### Output layout

```
data/pybaseball/
├── statcast/
│   └── Season={year}/
│       └── Month={month}/
│           └── statcast.parquet
├── batting_stats/
│   └── Season={year}/
│       └── batting_stats.parquet
├── pitching_stats/
│   └── Season={year}/
│       └── pitching_stats.parquet
├── batting_stats_bref/
│   └── Season={year}/
│       └── batting_stats_bref.parquet
├── pitching_stats_bref/
│   └── Season={year}/
│       └── pitching_stats_bref.parquet
├── team_batting/
│   └── Season={year}/
│       └── team_batting.parquet
├── team_pitching/
│   └── Season={year}/
│       └── team_pitching.parquet
├── standings/
│   └── Season={year}/
│       └── standings.parquet
├── schedule/
│   └── Season={year}/
│       └── Team={team}/
│           └── schedule.parquet
└── player_ids/
    └── player_ids.parquet
```

Re-running the script skips files that already exist, so downloads are
resumable.

### Quick examples

```bash
# List available datasets
python scripts/download_baseball_data.py --list-datasets

# Download pitch-level Statcast data for 2024 (chunked month-by-month)
python scripts/download_baseball_data.py --start-season 2024 --datasets statcast

# Download batting + pitching stats for 2022–2024
python scripts/download_baseball_data.py --start-season 2022 --end-season 2024 \
    --datasets batting_stats pitching_stats

# Download team-level batting and pitching stats
python scripts/download_baseball_data.py --start-season 2024 \
    --datasets team_batting team_pitching

# Download division standings for multiple seasons
python scripts/download_baseball_data.py --start-season 2020 --end-season 2024 \
    --datasets standings

# Download game-by-game schedule and record for specific teams
python scripts/download_baseball_data.py --start-season 2024 \
    --datasets schedule --teams NYY BOS LAD

# Download the player ID reference table (no season needed)
python scripts/download_baseball_data.py --datasets player_ids
```

### All options

| Flag              | Description                                            | Default                                                   |
| ----------------- | ------------------------------------------------------ | --------------------------------------------------------- |
| `--start-season`  | First season to download (required for most datasets)  | —                                                         |
| `--end-season`    | Last season to download inclusive                      | same as `--start-season`                                  |
| `--datasets`      | Dataset(s) to download (see below)                     | `batting_stats pitching_stats team_batting team_pitching` |
| `--teams`         | Team code(s) for the schedule dataset (e.g. `NYY BOS`) | —                                                         |
| `--list-datasets` | Print available datasets and exit                      | —                                                         |
| `--cache-dir`     | Enable pybaseball on-disk cache at this path           | disabled                                                  |

### Datasets

| Dataset               | Partition      | Source             | Description                                                             |
| --------------------- | -------------- | ------------------ | ----------------------------------------------------------------------- |
| `statcast`            | Season / Month | Baseball Savant    | One row per pitch; exit velocity, spin rate, launch angle, etc. (2008+) |
| `batting_stats`       | Season         | FanGraphs          | Player batting stats; one row per player-season                         |
| `pitching_stats`      | Season         | FanGraphs          | Player pitching stats; one row per player-season                        |
| `batting_stats_bref`  | Season         | Baseball Reference | Player batting stats (2008+)                                            |
| `pitching_stats_bref` | Season         | Baseball Reference | Player pitching stats (2008+)                                           |
| `team_batting`        | Season         | FanGraphs          | Team batting stats; one row per team-season                             |
| `team_pitching`       | Season         | FanGraphs          | Team pitching stats; one row per team-season                            |
| `standings`           | Season         | Baseball Reference | Division standings (1969+); all divisions concatenated                  |
| `schedule`            | Season / Team  | Baseball Reference | Game-by-game schedule and W/L record                                    |
| `player_ids`          | (none)         | Chadwick Bureau    | MLBAM, FanGraphs, BBRef, and Retrosheet IDs; static reference           |

> **Note on statcast size:** A full season of Statcast data is large — roughly
> 700,000+ pitches. The script chunks downloads by month and skips months
> already on disk, so you can stop and resume freely.

---

## Step 3 — Configure PlyDB

`plydb-config-example.json` contains a ready-to-use PlyDB config that registers
all ten datasets. Copy it and remove any tables for datasets you haven't
downloaded yet or do not plan to use in your analysis.

```bash
cp plydb-config-example.json plydb-config.json
```

---

## Step 4 — Start analyzing

Open Claude Code (or any PlyDB-compatible agent) in this directory and start
asking questions. The agent will translate your questions into SQL, run them
against the local Parquet files via PlyDB, and return results.

### Sample prompts

**Who actually wins the trade deadline?** Using the game-by-game schedule,
compare each team's win percentage and run differential before and after July 31
each season. Which franchises consistently improve after deadline acquisitions,
and which ones add payroll without moving the needle?

**Pitch mix evolution:** How has the league-wide share of four-seam fastballs
changed since 2015? Which starters have most dramatically shifted their arsenal
— and did the change correlate with better or worse outcomes?

**The platoon advantage by pitch type:** Does the left-on-left matchup advantage
hold equally for curveballs and sliders? Pull wOBA splits by batter/pitcher
handedness and pitch type across the Statcast era.

**Is the "bullpenning" era over?** Track average starter innings-per-appearance
by season. Which teams lead the trend back toward deeper starters, and are their
rotations actually performing better for it?

**Which parks are most pitcher-friendly right now?** Using Statcast pitch data,
compare barrel rate allowed and average xwOBA when pitchers are at home vs. away
over the last three seasons. Which ballparks consistently suppress or inflate
batted ball quality beyond what the season stats suggest?

**Prospect to superstar:** Using the player ID table to join Statcast and
FanGraphs data, identify the fastest rises from debut to peak wRC+ or FIP. Which
teams have been best at developing young players into impact contributors within
their first three seasons?

**Exit velocity arms race:** Plot the league-average barrel rate by season. Find
the pitchers who have maintained a below-average barrel rate allowed despite the
rising baseline — what do their pitch mixes have in common?

**The aging curve:** At what age does offensive production (wRC+) peak for
position players, and how does that compare to pitching performance (FIP) for
starters vs. relievers? Does the Statcast era show a different curve than the
pre-launch-angle era?

---

## Data sources

| Source                                                        | Description                                 |
| ------------------------------------------------------------- | ------------------------------------------- |
| [Baseball Savant](https://baseballsavant.mlb.com/)            | Statcast pitch-level data (via pybaseball)  |
| [FanGraphs](https://www.fangraphs.com/)                       | Advanced batting, pitching, and team stats  |
| [Baseball Reference](https://www.baseball-reference.com/)     | Standings, schedules, bref batting/pitching |
| [Chadwick Bureau](https://github.com/chadwickbureau/register) | Cross-system player ID register             |

---

## Reference

- [pybaseball documentation](https://github.com/jldbc/pybaseball/tree/master/docs)
  — full reference for all data acquisition functions
- [Statcast CSV field definitions](https://baseballsavant.mlb.com/csv-docs) —
  column-level reference for the statcast dataset
- [PlyDB documentation](https://www.plydb.com/docs/) — full PlyDB reference
