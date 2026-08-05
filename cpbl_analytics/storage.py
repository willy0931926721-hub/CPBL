"""SQLite 儲存層：每次爬蟲執行的資料快照 + 驗證報告，都會存下來。

刻意採「每次爬蟲都新增一批帶時間戳記的資料」而不是「就地覆蓋」，
理由：
1. 之後要看「球隊戰績隨球季的變化」這種趨勢分析，需要歷史快照。
2. 如果某次爬蟲抓到的資料驗證沒過，你可以回頭比對上一次成功的快照，
   而不是被一次寫壞的資料蓋掉。
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Iterator

import pandas as pd

from cpbl_analytics.config import DB_PATH
from cpbl_analytics.scraper.batting import BattingStat
from cpbl_analytics.scraper.pitching import PitchingStat
from cpbl_analytics.scraper.schedule import GameResult
from cpbl_analytics.scraper.standings import TeamStanding
from cpbl_analytics.validation import ValidationReport

SCHEMA = """
CREATE TABLE IF NOT EXISTS scrape_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dataset TEXT NOT NULL,
    scraped_at TEXT NOT NULL,
    year INTEGER,
    row_count INTEGER NOT NULL,
    error_count INTEGER NOT NULL,
    warning_count INTEGER NOT NULL,
    all_passed INTEGER NOT NULL,
    report_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS team_standings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scraped_at TEXT NOT NULL,
    year INTEGER,
    rank INTEGER,
    team_name TEXT NOT NULL,
    games INTEGER,
    wins INTEGER,
    losses INTEGER,
    ties INTEGER,
    win_pct REAL,
    games_behind TEXT,
    elimination_number TEXT,
    home_record TEXT,
    away_record TEXT,
    last_10 TEXT,
    streak TEXT
);

CREATE TABLE IF NOT EXISTS batting_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scraped_at TEXT NOT NULL,
    year INTEGER,
    player_name TEXT NOT NULL,
    team_name TEXT NOT NULL,
    games INTEGER,
    at_bats INTEGER,
    runs INTEGER,
    hits INTEGER,
    doubles INTEGER,
    triples INTEGER,
    home_runs INTEGER,
    rbi INTEGER,
    stolen_bases INTEGER,
    caught_stealing INTEGER,
    sac_bunts INTEGER,
    sac_flies INTEGER,
    walks INTEGER,
    intentional_walks INTEGER,
    hit_by_pitch INTEGER,
    strikeouts INTEGER,
    double_plays INTEGER,
    avg REAL,
    obp REAL,
    slg REAL,
    ops REAL,
    plate_appearances INTEGER
);

CREATE TABLE IF NOT EXISTS pitching_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scraped_at TEXT NOT NULL,
    year INTEGER,
    player_name TEXT NOT NULL,
    team_name TEXT NOT NULL,
    games INTEGER,
    games_started INTEGER,
    complete_games INTEGER,
    shutouts INTEGER,
    wins INTEGER,
    losses INTEGER,
    saves INTEGER,
    holds INTEGER,
    innings_pitched_outs INTEGER,
    hits_allowed INTEGER,
    home_runs_allowed INTEGER,
    walks INTEGER,
    intentional_walks INTEGER,
    hit_by_pitch INTEGER,
    strikeouts INTEGER,
    wild_pitches INTEGER,
    balks INTEGER,
    runs_allowed INTEGER,
    earned_runs INTEGER,
    era REAL,
    whip REAL
);

CREATE TABLE IF NOT EXISTS games (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scraped_at TEXT NOT NULL,
    game_date TEXT,
    away_team TEXT NOT NULL,
    home_team TEXT NOT NULL,
    away_score INTEGER,
    home_score INTEGER,
    status TEXT,
    venue TEXT,
    away_pitcher TEXT,
    home_pitcher TEXT
);
"""


#  (table, column, column 定義) 的清單：本機已經跑過舊版程式、已經有
# data/cpbl.db 檔案的人，`CREATE TABLE IF NOT EXISTS` 不會幫既有的表補上
# 新欄位（表已經存在，IF NOT EXISTS 直接跳過整個 CREATE 語句）。這裡用
# PRAGMA table_info 檢查欄位是否已存在，缺的話才補（ALTER TABLE ADD
# COLUMN），這樣不管是全新資料庫還是本機已經累積過歷史資料的舊資料庫，
# 都能正常寫入新欄位，不用整個刪掉重建。
_COLUMN_MIGRATIONS: list[tuple[str, str, str]] = [
    ("games", "away_pitcher", "TEXT"),
    ("games", "home_pitcher", "TEXT"),
]


def _apply_column_migrations(conn: sqlite3.Connection) -> None:
    for table, column, definition in _COLUMN_MIGRATIONS:
        existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
        if column not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # 這裡直接確保 schema 存在（executescript 裡每個 CREATE TABLE 都是
    # IF NOT EXISTS，重複執行沒有副作用），而不是要求呼叫端先手動呼叫
    # init_db()。理由：網頁版在雲端全新部署時，本機根本不會有人跑過
    # init_db()，如果沒有這一步，第一次讀取（例如「資料驗證」頁面）會直接
    # 因為「no such table」而整頁噴錯，而不是乾脆地顯示「尚無資料」。
    conn.executescript(SCHEMA)
    _apply_column_migrations(conn)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_connection() as conn:
        pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def save_scrape_run(
    *, dataset: str, report: ValidationReport, row_count: int, year: int | None = None
) -> None:
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO scrape_runs
               (dataset, scraped_at, year, row_count, error_count, warning_count,
                all_passed, report_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                dataset,
                _now(),
                year,
                row_count,
                report.error_count,
                report.warning_count,
                int(report.all_passed),
                json.dumps(
                    [
                        {
                            "name": c.name,
                            "passed": c.passed,
                            "severity": c.severity,
                            "message": c.message,
                            "offending_items": c.offending_items[:50],
                        }
                        for c in report.checks
                    ],
                    ensure_ascii=False,
                ),
            ),
        )


def save_standings(standings: list[TeamStanding], *, year: int | None = None) -> None:
    scraped_at = _now()
    with get_connection() as conn:
        conn.executemany(
            """INSERT INTO team_standings
               (scraped_at, year, rank, team_name, games, wins, losses, ties,
                win_pct, games_behind, elimination_number, home_record,
                away_record, last_10, streak)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    scraped_at, year, s.rank, s.team_name, s.games, s.wins, s.losses,
                    s.ties, s.win_pct, s.games_behind, s.elimination_number,
                    s.home_record, s.away_record, s.last_10, s.streak,
                )
                for s in standings
            ],
        )


def save_batting(stats: list[BattingStat], *, year: int | None = None) -> None:
    scraped_at = _now()
    with get_connection() as conn:
        conn.executemany(
            """INSERT INTO batting_stats
               (scraped_at, year, player_name, team_name, games, at_bats, runs, hits,
                doubles, triples, home_runs, rbi, stolen_bases, caught_stealing,
                sac_bunts, sac_flies, walks, intentional_walks, hit_by_pitch,
                strikeouts, double_plays, avg, obp, slg, ops, plate_appearances)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            [
                (
                    scraped_at, year, s.player_name, s.team_name, s.games, s.at_bats,
                    s.runs, s.hits, s.doubles, s.triples, s.home_runs, s.rbi,
                    s.stolen_bases, s.caught_stealing, s.sac_bunts, s.sac_flies,
                    s.walks, s.intentional_walks, s.hit_by_pitch, s.strikeouts,
                    s.double_plays, s.avg, s.obp, s.slg, s.ops, s.plate_appearances,
                )
                for s in stats
            ],
        )


def save_pitching(stats: list[PitchingStat], *, year: int | None = None) -> None:
    scraped_at = _now()
    with get_connection() as conn:
        conn.executemany(
            """INSERT INTO pitching_stats
               (scraped_at, year, player_name, team_name, games, games_started,
                complete_games, shutouts, wins, losses, saves, holds,
                innings_pitched_outs, hits_allowed, home_runs_allowed, walks,
                intentional_walks, hit_by_pitch, strikeouts, wild_pitches, balks,
                runs_allowed, earned_runs, era, whip)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            [
                (
                    scraped_at, year, s.player_name, s.team_name, s.games,
                    s.games_started, s.complete_games, s.shutouts, s.wins, s.losses,
                    s.saves, s.holds, s.innings_pitched_outs, s.hits_allowed,
                    s.home_runs_allowed, s.walks, s.intentional_walks, s.hit_by_pitch,
                    s.strikeouts, s.wild_pitches, s.balks, s.runs_allowed,
                    s.earned_runs, s.era, s.whip,
                )
                for s in stats
            ],
        )


def save_schedule(games: list[GameResult]) -> None:
    scraped_at = _now()
    with get_connection() as conn:
        conn.executemany(
            """INSERT INTO games
               (scraped_at, game_date, away_team, home_team, away_score, home_score, status, venue,
                away_pitcher, home_pitcher)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    scraped_at, g.date, g.away_team, g.home_team, g.away_score, g.home_score,
                    g.status, g.venue, g.away_pitcher, g.home_pitcher,
                )
                for g in games
            ],
        )


def load_latest_schedule() -> pd.DataFrame:
    return _load_latest("games")


def _load_latest(table: str, *, year: int | None = None) -> pd.DataFrame:
    with get_connection() as conn:
        latest_ts_query = f"SELECT MAX(scraped_at) AS ts FROM {table}"
        params: list = []
        if year is not None:
            latest_ts_query += " WHERE year = ?"
            params.append(year)
        latest_ts = conn.execute(latest_ts_query, params).fetchone()["ts"]
        if latest_ts is None:
            return pd.DataFrame()
        query = f"SELECT * FROM {table} WHERE scraped_at = ?"
        params2 = [latest_ts]
        if year is not None:
            query += " AND year = ?"
            params2.append(year)
        return pd.read_sql_query(query, conn, params=params2)


def load_latest_standings(*, year: int | None = None) -> pd.DataFrame:
    return _load_latest("team_standings", year=year)


def load_latest_batting(*, year: int | None = None) -> pd.DataFrame:
    return _load_latest("batting_stats", year=year)


def load_latest_pitching(*, year: int | None = None) -> pd.DataFrame:
    return _load_latest("pitching_stats", year=year)


def load_scrape_runs(*, limit: int = 30) -> pd.DataFrame:
    with get_connection() as conn:
        return pd.read_sql_query(
            "SELECT * FROM scrape_runs ORDER BY scraped_at DESC LIMIT ?",
            conn,
            params=[limit],
        )
