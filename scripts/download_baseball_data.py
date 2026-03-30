#!/usr/bin/env python3
"""
Download MLB baseball data via pybaseball and save as Parquet files (zstd compressed).

Output layout (Hive-partitioned):
  data/pybaseball/statcast/Season={year}/Month={month:02d}/statcast.parquet
  data/pybaseball/batting_stats/Season={year}/batting_stats.parquet
  data/pybaseball/pitching_stats/Season={year}/pitching_stats.parquet
  data/pybaseball/batting_stats_bref/Season={year}/batting_stats_bref.parquet
  data/pybaseball/pitching_stats_bref/Season={year}/pitching_stats_bref.parquet
  data/pybaseball/team_batting/Season={year}/team_batting.parquet
  data/pybaseball/team_pitching/Season={year}/team_pitching.parquet
  data/pybaseball/standings/Season={year}/standings.parquet
  data/pybaseball/schedule/Season={year}/Team={team}/schedule.parquet
  data/pybaseball/player_ids/player_ids.parquet

pybaseball installation (pip releases may lag; install from source):
  git clone https://github.com/jldbc/pybaseball
  cd pybaseball && pip install -e .

Examples:
  # Download pitch-level Statcast data for 2024 (chunked month-by-month, Mar–Oct)
  python scripts/download_baseball_data.py --start-season 2024 --datasets statcast

  # Download batting + pitching stats for 2022–2024
  python scripts/download_baseball_data.py --start-season 2022 --end-season 2024 \\
      --datasets batting_stats pitching_stats

  # Download team-level stats
  python scripts/download_baseball_data.py --start-season 2024 \\
      --datasets team_batting team_pitching

  # Download game-by-game schedule/record for specific teams
  python scripts/download_baseball_data.py --start-season 2024 \\
      --datasets schedule --teams NYY BOS LAD

  # Download division standings
  python scripts/download_baseball_data.py --start-season 2024 --datasets standings

  # Download player ID reference table (no season needed)
  python scripts/download_baseball_data.py --datasets player_ids

  # List available datasets
  python scripts/download_baseball_data.py --list-datasets
"""

import argparse
import calendar
import re
import sys
from pathlib import Path
from typing import List, Optional

import pandas as pd

try:
    import pybaseball
    from pybaseball import (
        statcast,
        batting_stats,
        pitching_stats,
        batting_stats_bref,
        pitching_stats_bref,
        team_batting,
        team_pitching,
        standings,
        schedule_and_record,
        chadwick_register,
    )
    from pybaseball import cache as pb_cache
except ImportError:
    print(
        "ERROR: pybaseball not found. Install it from source:\n"
        "  git clone https://github.com/jldbc/pybaseball\n"
        "  cd pybaseball && pip install -e .",
        file=sys.stderr,
    )
    sys.exit(1)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "pybaseball"

DATASET_TYPES = [
    "statcast",
    "batting_stats",
    "pitching_stats",
    "batting_stats_bref",
    "pitching_stats_bref",
    "team_batting",
    "team_pitching",
    "standings",
    "schedule",
    "player_ids",
]

DATASET_DESCRIPTIONS = {
    "statcast":            "Pitch-level Statcast data (2008+). Chunked by month; very large.",
    "batting_stats":       "FanGraphs player batting stats; one row per player-season.",
    "pitching_stats":      "FanGraphs player pitching stats; one row per player-season.",
    "batting_stats_bref":  "Baseball Reference player batting stats (2008+).",
    "pitching_stats_bref": "Baseball Reference player pitching stats (2008+).",
    "team_batting":        "FanGraphs team batting stats; one row per team-season.",
    "team_pitching":       "FanGraphs team pitching stats; one row per team-season.",
    "standings":           "Division standings per season (1969+).",
    "schedule":            "Game-by-game schedule and W/L record per team. Requires --teams.",
    "player_ids":          "Chadwick register: MLBAM/FG/BBRef/Retrosheet player IDs. No season needed.",
}

# Datasets that require --start-season
SEASON_REQUIRED = {
    "statcast",
    "batting_stats",
    "pitching_stats",
    "batting_stats_bref",
    "pitching_stats_bref",
    "team_batting",
    "team_pitching",
    "standings",
    "schedule",
}

# Months to cover for Statcast (MLB regular season + playoffs span Mar–Oct)
STATCAST_MONTHS = list(range(3, 11))  # March (3) through October (10)

PARQUET_KWARGS = dict(compression="zstd", index=False)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def hive_val(val) -> str:
    """Sanitize a value for use in a Hive partition directory name (e.g. Key=Value)."""
    s = str(val).strip()
    s = re.sub(r"[^\w\s-]", "", s)   # drop chars problematic on most filesystems
    s = re.sub(r"[\s]+", "_", s)      # spaces → underscores
    return s


def save_parquet(df: pd.DataFrame, path: Path, meta: Optional[dict] = None) -> None:
    if df is None or df.empty:
        print(f"  [skip] {path.name} — no data")
        return
    if meta:
        for key, val in reversed(list(meta.items())):
            df.insert(0, key, val)
    # Coerce object columns that are mostly numeric (e.g. Attendance with sentinel
    # 'Unknown' values from Baseball Reference). Converts non-numeric values to NaN.
    for col in df.select_dtypes(include=["object", "str"]).columns:
        converted = pd.to_numeric(df[col], errors="coerce")
        n_non_null = df[col].notna().sum()
        if n_non_null > 0 and converted.notna().sum() / n_non_null > 0.5:
            df[col] = converted
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, **PARQUET_KWARGS)
    print(f"  [ok]   {path.relative_to(ROOT)}  ({len(df):,} rows, {path.stat().st_size // 1024} KB)")


# ---------------------------------------------------------------------------
# Per-dataset downloaders
# ---------------------------------------------------------------------------


def download_statcast(year: int) -> None:
    """Download pitch-level Statcast data for a season, one month at a time."""
    print(f"\nStatcast {year} — fetching month by month …")
    for month in STATCAST_MONTHS:
        _, last_day = calendar.monthrange(year, month)
        start_dt = f"{year}-{month:02d}-01"
        end_dt = f"{year}-{month:02d}-{last_day:02d}"
        out = (
            DATA_DIR
            / "statcast"
            / f"Season={hive_val(year)}"
            / f"Month={month:02d}"
            / "statcast.parquet"
        )
        if out.exists():
            print(f"  [skip] {out.relative_to(ROOT)} — already exists")
            continue
        print(f"  Fetching {start_dt} → {end_dt} …")
        try:
            df = statcast(start_dt=start_dt, end_dt=end_dt, verbose=False)
            save_parquet(df, out)
        except Exception as exc:
            print(f"  [error] statcast {start_dt}–{end_dt}: {exc}")


def download_batting_stats(year: int) -> None:
    out = DATA_DIR / "batting_stats" / f"Season={hive_val(year)}" / "batting_stats.parquet"
    if out.exists():
        print(f"  [skip] {out.relative_to(ROOT)} — already exists")
        return
    print(f"  batting_stats {year} …")
    try:
        df = batting_stats(start_season=year, end_season=year, qual=1, ind=1)
        save_parquet(df, out)
    except Exception as exc:
        print(f"  [error] batting_stats {year}: {exc}")


def download_pitching_stats(year: int) -> None:
    out = DATA_DIR / "pitching_stats" / f"Season={hive_val(year)}" / "pitching_stats.parquet"
    if out.exists():
        print(f"  [skip] {out.relative_to(ROOT)} — already exists")
        return
    print(f"  pitching_stats {year} …")
    try:
        df = pitching_stats(start_season=year, end_season=year, qual=1, ind=1)
        save_parquet(df, out)
    except Exception as exc:
        print(f"  [error] pitching_stats {year}: {exc}")


def download_batting_stats_bref(year: int) -> None:
    out = DATA_DIR / "batting_stats_bref" / f"Season={hive_val(year)}" / "batting_stats_bref.parquet"
    if out.exists():
        print(f"  [skip] {out.relative_to(ROOT)} — already exists")
        return
    print(f"  batting_stats_bref {year} …")
    try:
        df = batting_stats_bref(season=year)
        save_parquet(df, out)
    except Exception as exc:
        print(f"  [error] batting_stats_bref {year}: {exc}")


def download_pitching_stats_bref(year: int) -> None:
    out = DATA_DIR / "pitching_stats_bref" / f"Season={hive_val(year)}" / "pitching_stats_bref.parquet"
    if out.exists():
        print(f"  [skip] {out.relative_to(ROOT)} — already exists")
        return
    print(f"  pitching_stats_bref {year} …")
    try:
        df = pitching_stats_bref(season=year)
        save_parquet(df, out)
    except Exception as exc:
        print(f"  [error] pitching_stats_bref {year}: {exc}")


def download_team_batting(year: int) -> None:
    out = DATA_DIR / "team_batting" / f"Season={hive_val(year)}" / "team_batting.parquet"
    if out.exists():
        print(f"  [skip] {out.relative_to(ROOT)} — already exists")
        return
    print(f"  team_batting {year} …")
    try:
        df = team_batting(start_season=year, end_season=year, ind=1)
        save_parquet(df, out)
    except Exception as exc:
        print(f"  [error] team_batting {year}: {exc}")


def download_team_pitching(year: int) -> None:
    out = DATA_DIR / "team_pitching" / f"Season={hive_val(year)}" / "team_pitching.parquet"
    if out.exists():
        print(f"  [skip] {out.relative_to(ROOT)} — already exists")
        return
    print(f"  team_pitching {year} …")
    try:
        df = team_pitching(start_season=year, end_season=year, ind=1)
        save_parquet(df, out)
    except Exception as exc:
        print(f"  [error] team_pitching {year}: {exc}")


def download_standings(year: int) -> None:
    out = DATA_DIR / "standings" / f"Season={hive_val(year)}" / "standings.parquet"
    if out.exists():
        print(f"  [skip] {out.relative_to(ROOT)} — already exists")
        return
    print(f"  standings {year} …")
    try:
        # standings() returns a list of DataFrames, one per division.
        # Division order for post-1994: AL East, AL Central, AL West,
        #                               NL East, NL Central, NL West.
        division_frames = standings(season=year)
        frames = []
        for i, df in enumerate(division_frames):
            df = df.copy()
            df.insert(0, "DivisionIndex", i)
            frames.append(df)
        combined = pd.concat(frames, ignore_index=True)
        # W, L, W-L%, and GB come back as strings from pybaseball's HTML scrape.
        # Coerce to proper numeric types here so callers never need CAST.
        combined["W"] = pd.to_numeric(combined["W"], errors="coerce").astype("Int64")
        combined["L"] = pd.to_numeric(combined["L"], errors="coerce").astype("Int64")
        combined["W-L%"] = pd.to_numeric(combined["W-L%"], errors="coerce")
        # Division leader is '--'; treat as 0 games behind.
        combined["GB"] = pd.to_numeric(
            combined["GB"].replace("--", "0"), errors="coerce"
        )
        save_parquet(combined, out, meta={"Season": year})
    except Exception as exc:
        print(f"  [error] standings {year}: {exc}")


def download_schedule(year: int, team: str) -> None:
    out = (
        DATA_DIR
        / "schedule"
        / f"Season={hive_val(year)}"
        / f"Team={hive_val(team)}"
        / "schedule.parquet"
    )
    if out.exists():
        print(f"  [skip] {out.relative_to(ROOT)} — already exists")
        return
    print(f"  schedule {year} {team} …")
    try:
        # pybaseball's make_numeric uses .astype(float) which fails on pandas 2.x
        # Copy-on-Write when 'Unknown' attendance values aren't cleaned first.
        # Patch make_numeric in-place before the call to use pd.to_numeric instead.
        import pybaseball.team_results as _tr
        import numpy as np
        def _make_numeric_patched(data: pd.DataFrame) -> pd.DataFrame:
            if data["Attendance"].count() > 0:
                data = data.copy()
                data["Attendance"] = data["Attendance"].str.replace(",", "", regex=False)
            else:
                data = data.copy()
                data["Attendance"] = np.nan
            for col in ["R", "RA", "Inn", "Rank", "Attendance"]:
                data[col] = pd.to_numeric(data[col], errors="coerce")
            return data
        _orig = _tr.make_numeric
        _tr.make_numeric = _make_numeric_patched
        try:
            df = schedule_and_record(season=year, team=team)
        finally:
            _tr.make_numeric = _orig
        save_parquet(df, out, meta={"Season": year, "Team": team})
    except Exception as exc:
        print(f"  [error] schedule {year} {team}: {exc}")


def download_player_ids() -> None:
    out = DATA_DIR / "player_ids" / "player_ids.parquet"
    if out.exists():
        print(f"  [skip] {out.relative_to(ROOT)} — already exists")
        return
    print("  Downloading Chadwick player ID register …")
    try:
        df = chadwick_register()
        save_parquet(df, out)
    except Exception as exc:
        print(f"  [error] player_ids: {exc}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args():
    parser = argparse.ArgumentParser(
        description="Download MLB baseball data to Parquet files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--start-season",
        type=int,
        metavar="YEAR",
        help="First season to download, e.g. 2024.",
    )
    parser.add_argument(
        "--end-season",
        type=int,
        metavar="YEAR",
        help="Last season to download inclusive (default: same as --start-season).",
    )
    parser.add_argument(
        "--datasets",
        nargs="+",
        default=["batting_stats", "pitching_stats", "team_batting", "team_pitching"],
        choices=DATASET_TYPES,
        metavar="DATASET",
        help=(
            "Dataset(s) to download  "
            "(default: batting_stats pitching_stats team_batting team_pitching). "
            f"Choices: {', '.join(DATASET_TYPES)}"
        ),
    )
    parser.add_argument(
        "--teams",
        nargs="+",
        metavar="TEAM",
        help=(
            "Team code(s) for the schedule dataset (e.g. NYY BOS LAD). "
            "Required when --datasets includes schedule."
        ),
    )
    parser.add_argument(
        "--list-datasets",
        action="store_true",
        help="Print available datasets and their descriptions, then exit.",
    )
    parser.add_argument(
        "--cache-dir",
        metavar="PATH",
        help="Enable pybaseball on-disk cache at this directory path.",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    if args.list_datasets:
        print("\nAvailable datasets:\n")
        for name, desc in DATASET_DESCRIPTIONS.items():
            print(f"  {name:<24} {desc}")
        print()
        return

    # Validate: season required for most datasets
    needs_season = any(d in SEASON_REQUIRED for d in args.datasets)
    if needs_season and args.start_season is None:
        print(
            "ERROR: --start-season YEAR is required for the selected dataset(s).\n"
            "       (Only player_ids can be downloaded without a season.)",
            file=sys.stderr,
        )
        sys.exit(1)

    start = args.start_season
    end = args.end_season if args.end_season is not None else start
    if start and end and end < start:
        print("ERROR: --end-season must be >= --start-season.", file=sys.stderr)
        sys.exit(1)

    if "schedule" in args.datasets and not args.teams:
        print(
            "ERROR: --teams TEAM [TEAM ...] is required when downloading the schedule dataset.\n"
            "       Example: --teams NYY BOS LAD",
            file=sys.stderr,
        )
        sys.exit(1)

    # Configure pybaseball cache
    if args.cache_dir:
        pb_cache.enable(args.cache_dir)
        print(f"pybaseball cache enabled at {args.cache_dir}")

    # player_ids has no season dimension
    if "player_ids" in args.datasets:
        print("\nDownloading player ID register …")
        download_player_ids()

    # Season-scoped datasets
    if needs_season:
        for year in range(start, end + 1):
            print(f"\n{'='*60}\nSeason {year}\n{'='*60}")

            if "statcast" in args.datasets:
                download_statcast(year)

            if "batting_stats" in args.datasets:
                download_batting_stats(year)

            if "pitching_stats" in args.datasets:
                download_pitching_stats(year)

            if "batting_stats_bref" in args.datasets:
                download_batting_stats_bref(year)

            if "pitching_stats_bref" in args.datasets:
                download_pitching_stats_bref(year)

            if "team_batting" in args.datasets:
                download_team_batting(year)

            if "team_pitching" in args.datasets:
                download_team_pitching(year)

            if "standings" in args.datasets:
                download_standings(year)

            if "schedule" in args.datasets:
                for team in args.teams:
                    download_schedule(year, team)

    print("\nDone.")


if __name__ == "__main__":
    main()
