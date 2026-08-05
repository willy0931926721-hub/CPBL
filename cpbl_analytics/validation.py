"""資料驗證模組：這是整支程式「確保抓到的東西是對的」的核心。

抓資料只是第一步，抓「對」才是重點。這個模組不相信官網頁面上顯示的
衍生數字（打擊率、防禦率、OPS...），而是用最基本的欄位（打數、安打、
局數、自責分...）重新算一次，跟官網顯示的數字互相比對——兩邊對得上，
才代表資料是可信的；對不上，代表 (a) 抓錯欄位、(b) 官網當下資料本身有
誤植、或 (c) 我們的欄位對應邏輯需要調整，三種狀況都值得攤在「資料驗證」
頁面上讓你自己判斷，而不是默默相信爬下來的每一個數字。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from cpbl_analytics.scraper.batting import BattingStat
from cpbl_analytics.scraper.pitching import PitchingStat
from cpbl_analytics.scraper.schedule import GameResult
from cpbl_analytics.scraper.standings import TeamStanding

Severity = Literal["error", "warning", "info"]


@dataclass
class CheckResult:
    name: str
    passed: bool
    severity: Severity
    message: str
    offending_items: list[str] = field(default_factory=list)


@dataclass
class ValidationReport:
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        return sum(1 for c in self.checks if not c.passed and c.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for c in self.checks if not c.passed and c.severity == "warning")

    @property
    def all_passed(self) -> bool:
        return self.error_count == 0

    def add(self, result: CheckResult) -> None:
        self.checks.append(result)


AVG_TOLERANCE = 0.002
RATE_TOLERANCE = 0.005
ERA_TOLERANCE = 0.05
WHIP_TOLERANCE = 0.02


def validate_batting_stats(stats: list[BattingStat]) -> ValidationReport:
    report = ValidationReport()

    # 1. 重複球員（同名同隊）
    seen = set()
    dupes = []
    for s in stats:
        key = (s.player_name, s.team_name)
        if key in seen:
            dupes.append(f"{s.player_name}（{s.team_name}）")
        seen.add(key)
    report.add(CheckResult(
        name="打者重複列檢查",
        passed=not dupes,
        severity="error",
        message="沒有重複的球員列" if not dupes else f"發現 {len(dupes)} 筆重複球員資料",
        offending_items=dupes,
    ))

    # 2. 安打數不可超過打數；二安+三安+全壘打不可超過安打數
    impossible = []
    for s in stats:
        if s.hits > s.at_bats:
            impossible.append(f"{s.player_name}: 安打({s.hits}) > 打數({s.at_bats})")
        if s.doubles + s.triples + s.home_runs > s.hits:
            impossible.append(
                f"{s.player_name}: 二安+三安+全壘打({s.doubles + s.triples + s.home_runs}) "
                f"> 安打({s.hits})"
            )
    report.add(CheckResult(
        name="打者基礎欄位邏輯一致性",
        passed=not impossible,
        severity="error",
        message="通過" if not impossible else f"發現 {len(impossible)} 筆不合理數據",
        offending_items=impossible,
    ))

    # 3. 打擊率 AVG = H / AB
    avg_mismatches = []
    for s in stats:
        if s.at_bats <= 0:
            continue
        computed = s.hits / s.at_bats
        if abs(computed - s.avg) > AVG_TOLERANCE:
            avg_mismatches.append(
                f"{s.player_name}: 官網 AVG={s.avg:.3f}, 由 H/AB 重算={computed:.3f}"
            )
    report.add(CheckResult(
        name="打擊率 AVG = 安打 / 打數 交叉驗證",
        passed=not avg_mismatches,
        severity="error",
        message="通過" if not avg_mismatches else f"發現 {len(avg_mismatches)} 筆打擊率對不上",
        offending_items=avg_mismatches,
    ))

    # 4. OBP = (H + BB + HBP) / (AB + BB + HBP + SF)
    obp_mismatches = []
    for s in stats:
        if s.obp is None:
            continue
        denom = s.at_bats + s.walks + s.hit_by_pitch + s.sac_flies
        if denom <= 0:
            continue
        computed = (s.hits + s.walks + s.hit_by_pitch) / denom
        if abs(computed - s.obp) > RATE_TOLERANCE:
            obp_mismatches.append(
                f"{s.player_name}: 官網 OBP={s.obp:.3f}, 重算={computed:.3f}"
            )
    report.add(CheckResult(
        name="上壘率 OBP 交叉驗證",
        passed=not obp_mismatches,
        severity="warning",
        message="通過" if not obp_mismatches else f"發現 {len(obp_mismatches)} 筆上壘率對不上",
        offending_items=obp_mismatches,
    ))

    # 5. SLG = 總壘打數 / AB
    slg_mismatches = []
    for s in stats:
        if s.slg is None or s.at_bats <= 0:
            continue
        singles = s.hits - s.doubles - s.triples - s.home_runs
        total_bases = singles + 2 * s.doubles + 3 * s.triples + 4 * s.home_runs
        computed = total_bases / s.at_bats
        if abs(computed - s.slg) > RATE_TOLERANCE:
            slg_mismatches.append(
                f"{s.player_name}: 官網 SLG={s.slg:.3f}, 重算={computed:.3f}"
            )
    report.add(CheckResult(
        name="長打率 SLG 交叉驗證",
        passed=not slg_mismatches,
        severity="warning",
        message="通過" if not slg_mismatches else f"發現 {len(slg_mismatches)} 筆長打率對不上",
        offending_items=slg_mismatches,
    ))

    # 6. OPS = OBP + SLG
    ops_mismatches = []
    for s in stats:
        if s.ops is None or s.obp is None or s.slg is None:
            continue
        computed = s.obp + s.slg
        if abs(computed - s.ops) > RATE_TOLERANCE:
            ops_mismatches.append(
                f"{s.player_name}: 官網 OPS={s.ops:.3f}, OBP+SLG={computed:.3f}"
            )
    report.add(CheckResult(
        name="OPS = OBP + SLG 交叉驗證",
        passed=not ops_mismatches,
        severity="warning",
        message="通過" if not ops_mismatches else f"發現 {len(ops_mismatches)} 筆 OPS 對不上",
        offending_items=ops_mismatches,
    ))

    return report


def validate_pitching_stats(stats: list[PitchingStat]) -> ValidationReport:
    report = ValidationReport()

    seen = set()
    dupes = []
    for s in stats:
        key = (s.player_name, s.team_name)
        if key in seen:
            dupes.append(f"{s.player_name}（{s.team_name}）")
        seen.add(key)
    report.add(CheckResult(
        name="投手重複列檢查",
        passed=not dupes,
        severity="error",
        message="沒有重複的球員列" if not dupes else f"發現 {len(dupes)} 筆重複球員資料",
        offending_items=dupes,
    ))

    # ERA = 自責分 * 9 / 局數
    era_mismatches = []
    for s in stats:
        if s.innings_pitched_outs <= 0:
            continue
        computed = s.earned_runs * 27 / s.innings_pitched_outs  # 27 = 9局*3出局
        if abs(computed - s.era) > ERA_TOLERANCE:
            era_mismatches.append(
                f"{s.player_name}: 官網 ERA={s.era:.2f}, 由自責分/局數重算={computed:.2f} "
                f"(局數={s.innings_pitched_display})"
            )
    report.add(CheckResult(
        name="防禦率 ERA 交叉驗證",
        passed=not era_mismatches,
        severity="error",
        message="通過" if not era_mismatches else f"發現 {len(era_mismatches)} 筆防禦率對不上",
        offending_items=era_mismatches,
    ))

    # WHIP = (四壞+被安打) / 局數
    whip_mismatches = []
    for s in stats:
        if s.whip is None or s.innings_pitched_outs <= 0:
            continue
        computed = (s.walks + s.hits_allowed) * 3 / s.innings_pitched_outs
        if abs(computed - s.whip) > WHIP_TOLERANCE:
            whip_mismatches.append(
                f"{s.player_name}: 官網 WHIP={s.whip:.2f}, 重算={computed:.2f}"
            )
    report.add(CheckResult(
        name="WHIP 交叉驗證",
        passed=not whip_mismatches,
        severity="warning",
        message="通過" if not whip_mismatches else f"發現 {len(whip_mismatches)} 筆 WHIP 對不上",
        offending_items=whip_mismatches,
    ))

    # 自責分不可大於失分
    impossible = [
        f"{s.player_name}: 自責分({s.earned_runs}) > 失分({s.runs_allowed})"
        for s in stats
        if s.earned_runs > s.runs_allowed
    ]
    report.add(CheckResult(
        name="投手基礎欄位邏輯一致性（自責分 <= 失分）",
        passed=not impossible,
        severity="error",
        message="通過" if not impossible else f"發現 {len(impossible)} 筆不合理數據",
        offending_items=impossible,
    ))

    return report


def validate_standings(standings: list[TeamStanding]) -> ValidationReport:
    report = ValidationReport()

    # 1. 隊伍名稱不重複
    names = [s.team_name for s in standings]
    dupes = [n for n in set(names) if names.count(n) > 1]
    report.add(CheckResult(
        name="球隊名稱重複檢查",
        passed=not dupes,
        severity="error",
        message="通過" if not dupes else f"發現重複球隊：{dupes}",
        offending_items=dupes,
    ))

    # 2. games == wins + losses + ties
    game_mismatches = [
        f"{s.team_name}: 出賽數({s.games}) != 勝+負+和({s.wins + s.losses + s.ties})"
        for s in standings
        if s.games != s.wins + s.losses + s.ties
    ]
    report.add(CheckResult(
        name="出賽數 = 勝+負+和 一致性檢查",
        passed=not game_mismatches,
        severity="error",
        message="通過" if not game_mismatches else f"發現 {len(game_mismatches)} 隊對不上",
        offending_items=game_mismatches,
    ))

    # 3. win_pct ≈ wins / (wins + losses)（不含和局）
    pct_mismatches = []
    for s in standings:
        denom = s.wins + s.losses
        if denom <= 0:
            continue
        computed = s.wins / denom
        if abs(computed - s.win_pct) > RATE_TOLERANCE:
            pct_mismatches.append(
                f"{s.team_name}: 官網勝率={s.win_pct:.3f}, 重算={computed:.3f}"
            )
    report.add(CheckResult(
        name="勝率 = 勝 / (勝+負) 交叉驗證",
        passed=not pct_mismatches,
        severity="error",
        message="通過" if not pct_mismatches else f"發現 {len(pct_mismatches)} 隊勝率對不上",
        offending_items=pct_mismatches,
    ))

    # 4. 全聯盟總勝場 == 總負場（每場決定勝負的比賽會產生一勝一負）
    total_wins = sum(s.wins for s in standings)
    total_losses = sum(s.losses for s in standings)
    balanced = total_wins == total_losses
    report.add(CheckResult(
        name="全聯盟勝場數 = 敗場數（雙人零和）檢查",
        passed=balanced,
        severity="warning",
        message=(
            "通過（總勝場與總敗場相等）"
            if balanced
            else f"總勝場={total_wins}，總敗場={total_losses}，兩者應相等"
                 "（若球季尚未結束、有補賽或和局計分方式特殊，此差異可能是正常現象，僅供留意）"
        ),
    ))

    return report


def validate_schedule(games: list[GameResult]) -> ValidationReport:
    report = ValidationReport()

    same_team = [
        f"{g.date}: {g.home_team} vs {g.away_team}" for g in games if g.home_team == g.away_team
    ]
    report.add(CheckResult(
        name="主客隊不可相同",
        passed=not same_team,
        severity="error",
        message="通過" if not same_team else f"發現 {len(same_team)} 場比賽主客隊相同",
        offending_items=same_team,
    ))

    negative_scores = [
        f"{g.date}: {g.away_team}({g.away_score}) @ {g.home_team}({g.home_score})"
        for g in games
        if (g.away_score is not None and g.away_score < 0)
        or (g.home_score is not None and g.home_score < 0)
    ]
    report.add(CheckResult(
        name="比分不可為負數",
        passed=not negative_scores,
        severity="error",
        message="通過" if not negative_scores else f"發現 {len(negative_scores)} 場比賽比分為負數",
        offending_items=negative_scores,
    ))

    return report


def run_all_checks(
    *,
    standings: list[TeamStanding] | None = None,
    batting: list[BattingStat] | None = None,
    pitching: list[PitchingStat] | None = None,
    schedule: list[GameResult] | None = None,
) -> dict[str, ValidationReport]:
    """一次跑完所有已提供資料的驗證，回傳給 CLI 或 Streamlit 頁面使用。"""
    reports: dict[str, ValidationReport] = {}
    if standings is not None:
        reports["standings"] = validate_standings(standings)
    if batting is not None:
        reports["batting"] = validate_batting_stats(batting)
    if pitching is not None:
        reports["pitching"] = validate_pitching_stats(pitching)
    if schedule is not None:
        reports["schedule"] = validate_schedule(schedule)
    return reports
