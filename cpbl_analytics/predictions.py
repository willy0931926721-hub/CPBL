"""比賽勝率預測：純數據驅動的球隊實力評分與單場比賽勝率估算。

目的是給「投注分析」提供一個獨立、可驗證的機率估計，讓你可以拿這個數字
去跟你自己查到的盤口/賠率比較，找出數據跟賠率不一致、可能有價值的下注
機會。**這支程式本身不會、也不打算自動化串接任何博弈網站的賠率**——
中華職棒合法的賠率來源只有政府特許的台灣運動彩券，其賠率頁面本來就
需要會員登入、且有反爬蟲保護，直接嘗試繞過在技術上不可靠、在條款上也
很可能不被允許；至於非合法管道的賠率來源，這支程式不會去碰。這裡輸出
的永遠只是「我們自己算出來的機率」，賠率永遠要你自己提供或比對。

方法論（都是公開、有文獻根據的棒球分析方法，不是自創的黑盒子）：

1. **畢氏勝率期望值**（Pythagorean win expectation，見 sabermetrics.py 的
   `pythagorean_win_pct()`）：用球隊「真正」的得分/失分（加總全隊打者的
   「得分」欄位、投手的「失分」欄位，因為官網球隊戰績表本身沒有直接提供
   得失分），比球隊球季實際勝率更能反映真實實力——實際勝率會受一分差
   比賽的運氣成分影響，畢氏期望值把這個雜訊濾掉一部分。
2. **球隊實力評分（power rating）** = 畢氏期望勝率、球季實際勝率、近十場
   戰績勝率的加權平均（預設權重 0.5 / 0.3 / 0.2），同時反映「整體實力」
   跟「近期狀態」，任何一項缺資料時會自動把權重分給其他項目，而不是
   直接當成 0。
3. **主客場優勢**：用這支球隊自己在主場/客場的實際勝率（官網「主場戰績」
   「客場戰績」欄位本來就有）算出跟聯盟平均的落差，而不是套用 MLB 文獻
   常見的固定主場優勢係數——CPBL 的球場環境、賽制跟 MLB 不同，沒有理由
   照搬別的聯盟算出來的數字。
4. **兩隊對戰勝率**：用 log5 公式（Bill James）把兩隊的實力評分換算成
   單場比賽的勝率，是棒球分析界計算「非聯盟平均實力」兩隊對戰時常用的
   方法，公式見 `log5_win_probability()`。
5. **小樣本收斂（shrinkage）**：球季初期任何一項指標的樣本數都還很小，
   尤其是主客場戰績——「0 勝 0 和 3 敗」這種只有 3 場的客場成績，字面上
   是 0% 客場勝率，但這顯然不能直接當真，會讓 log5 算出來的對戰勝率出現
   不合理的 99%/1% 這種極端值。實際組成 power_rating、主客場優勢調整時，
   每一項指標都會依「樣本數（場次）」往聯盟平均收斂——場次越少，越把
   數字拉回中性值；場次越多，越信任這項指標本身的數字（見
   `_shrink_toward()`）。網頁版表格呈現的仍然是**原始、沒收斂過**的數字，
   收斂只發生在會影響預測機率的計算內部，不會偷偷竄改攤在畫面上給人看
   的統計數字。
6. **先發投手調整**：如果賽程資料裡有這場比賽的先發投手姓名（見
   `scraper/schedule.py` 的 `away_pitcher`/`home_pitcher`），會拿這位投手
   本季 ERA 跟「局數加權」的聯盟平均 ERA 比較，ERA 比聯盟平均低（表現
   好）就對他所在的球隊加分、反之扣分，換算成一個小幅度的勝率微調（見
   `_pitcher_edge()`）。這個微調刻意做得保守（`MAX_PITCHER_EDGE` 封頂）、
   而不是把先發投手的權重跟球隊整體實力打對折——先發投手固然重要，但
   單場比賽的結果同時取決於牛棚、當天打線手感、守備等一堆這裡完全沒
   建模的因素，把先發投手的影響力估得太高，反而會讓模型在「先發投手
   ERA 差很多、但其實牛棚更強的那隊」這種案例上，錯得比不調整還離譜。
   跟其他指標一樣，投手 ERA 本身也依「投球局數」做小樣本收斂——球季初期
   只投幾局的投手，字面上的 ERA 完全不能代表真實實力。找不到先發投手
   姓名、或姓名跟已抓到的投手數據對不上時，這個調整量就是 0（不影響
   其他因素的預測），不會讓整場預測失敗。

跟賠率／讓分盤口的比較，一律是「這支程式算出來的機率 vs. 你自己提供的
賠率」，需要你自己動手比對。**先發投手資料是猜測性寫法**：官網賽程頁
「未開賽」比賽卡片實際上會不會列出先發投手、用什麼結構列出來，這支程式
開發時所在的沙盒環境連不到官網，還沒辦法確認（見 `scraper/schedule.py`
檔案開頭的說明）——抓不到的話，這裡的評分就只反映兩支球隊的整體實力，
不會硬塞一個假的先發投手調整進去。
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from cpbl_analytics.sabermetrics import (
    pythagorean_win_pct,
    team_batting_aggregates,
    team_pitching_aggregates,
)

DEFAULT_WEIGHTS = (0.5, 0.3, 0.2)  # (畢氏期望值, 球季實際勝率, 近十場戰績)

# 小樣本收斂（shrinkage）用的「先驗場次數」：球季初期（例如目前只打了 13~14 場）
# 任何一項指標的樣本數都還太小，尤其是主客場戰績——像「0 勝 0 和 3 敗」這種只有
# 3 場的客場成績，字面上是 0% 客場勝率，但這顯然不能直接當成「這支球隊客場必輸」
# 的真實實力來用，會讓 log5 算出來的對戰勝率出現不合理的 99%/1% 這種極端值。
# 這裡用「往聯盟平均（或整體實力評分）收斂」的貝氏收斂法：樣本數越少，越把數字
# 拉回中性值；樣本數（場次）越多，越信任這項指標本身的數字。
SEASON_STAT_PRIOR_GAMES = 20  # 球季勝率／畢氏期望值收斂用的先驗場次數
RECENT_FORM_PRIOR_GAMES = 10  # 近十場戰績本身樣本數就小，先驗場次數也對應調低
HOME_AWAY_PRIOR_GAMES = 10  # 主／客場戰績通常只有個位數場次，收斂力道要更強

# 先發投手 ERA 收斂用的先驗局數：投越少局，ERA 越不可信、越把數字拉回
# 聯盟平均；20 局大約是先發投手 3~4 場先發的量，抓這個當「開始有點可信」
# 的門檻。
PITCHER_ERA_PRIOR_IP = 20.0
# ERA 每比「局數加權聯盟平均 ERA」低 1.00（表現越好），對戰勝率往有利於
# 他所在球隊的方向微調的幅度。這是參考「先發投手大約主導整場比賽三分之一
# 到一半勝負、其餘取決於牛棚／打線／守備」這個棒球分析界常見共識抓出來的
# 經驗係數，不是拿 CPBL 歷史資料迴歸出來的精確值，量級上刻意保守（見下面
# MAX_PITCHER_EDGE 的說明），避免用一個沒校正過的係數就讓預測機率大幅
# 偏移。
PITCHER_EDGE_PER_ERA_RUN = 0.03
# 先發投手調整量的上限：即使 ERA 差距極端（例如小樣本剛好 0.00 vs 10.00），
# 這個調整最多只會讓對戰勝率位移這麼多，避免單一因素（尤其是還沒充分驗證
# 過的猜測性資料）把整體預測機率推向不合理的極端值。
MAX_PITCHER_EDGE = 0.08


def _pitcher_lookup(pitching_df: pd.DataFrame) -> dict[str, tuple[float, float]]:
    """把投手數據表轉成 {球員姓名: (ERA, 投球局數)} 的查詢表，給
    `_pitcher_edge()` 用。

    用「姓名」當鍵，不是球員 ID——賽程頁抓到的先發投手欄位（見
    `scraper/schedule.py`）目前也只有姓名文字，官網頁面沒有提供可以
    跨頁面對應的球員 ID。理論上可能發生同名同姓，但目前沒有更可靠的
    對應方式，先以姓名為準；真的撞名的話，這裡會覆蓋成後面那筆的數字
    （不是刻意設計，是姓名沒有唯一性的已知限制）。
    """
    if pitching_df.empty:
        return {}
    lookup: dict[str, tuple[float, float]] = {}
    for _, row in pitching_df.iterrows():
        name = row.get("player_name")
        era = row.get("era")
        outs = row.get("innings_pitched_outs")
        if not name or pd.isna(era) or pd.isna(outs):
            continue
        lookup[name] = (float(era), float(outs) / 3.0)
    return lookup


def _league_avg_era(pitching_df: pd.DataFrame) -> float | None:
    """局數加權的聯盟平均 ERA：用「全聯盟自責分總和 / 全聯盟局數總和」重算，
    而不是把每個投手的 ERA 直接算術平均——後者會讓「只投一局、剛好無失分」
    這種 ERA=0.00 的極端小樣本，跟「投滿一整季」的先發投手在平均數裡權重
    相同，把聯盟平均拉歪。
    """
    if pitching_df.empty:
        return None
    total_outs = pitching_df["innings_pitched_outs"].sum()
    if not total_outs:
        return None
    return float(pitching_df["earned_runs"].sum()) * 27 / float(total_outs)


def _pitcher_edge(
    pitcher_name: str | None,
    *,
    pitcher_lookup: dict[str, tuple[float, float]],
    league_avg_era: float | None,
) -> float:
    """算出某位先發投手「相對局數加權聯盟平均 ERA」的優劣勢，轉成一個小幅度
    的對戰勝率調整量（正值＝對他所在的球隊加分）。

    ERA 本身先依投球局數做小樣本收斂（往聯盟平均拉），再跟聯盟平均的差距
    乘上 PITCHER_EDGE_PER_ERA_RUN、封頂在 MAX_PITCHER_EDGE，方法論細節見
    本檔案開頭 docstring 的第 6 點。

    找不到投手姓名、姓名對不上已知的投手數據、或聯盟平均 ERA 算不出來
    （例如這一輪投手數據剛好抓取失敗），一律回傳 0（沒有調整），不影響
    其他因素的預測——這個調整是額外的加值資訊，不應該因為它算不出來，
    就讓整場比賽的預測失敗。
    """
    if pitcher_name is None or league_avg_era is None or league_avg_era <= 0:
        return 0.0
    entry = pitcher_lookup.get(pitcher_name)
    if entry is None:
        return 0.0
    era, ip = entry
    shrunk_era = _shrink_toward(
        era, sample_size=ip, prior_strength=PITCHER_ERA_PRIOR_IP, prior_value=league_avg_era
    )
    edge = (league_avg_era - shrunk_era) * PITCHER_EDGE_PER_ERA_RUN
    return max(-MAX_PITCHER_EDGE, min(MAX_PITCHER_EDGE, edge))


def _wtl_stats(record: str | None) -> tuple[float | None, int]:
    """把「W-T-L」格式的戰績字串（例如「4-0-2」）拆成 (勝率, 有勝負結果的場次數)。

    官網「主場戰績」「客場戰績」「近十場戰績」都是這種格式（和局不計入分母）；
    格式不符合預期（例如空值、官網改版）時回傳 (None, 0)，讓呼叫端自己決定
    怎麼處理缺值，而不是在這裡默默假裝成 0 勝率。場次數會拿去做小樣本收斂
    （見 SEASON_STAT_PRIOR_GAMES 等常數的說明），不是只是附帶資訊。
    """
    if not record:
        return None, 0
    parts = record.split("-")
    if len(parts) != 3:
        return None, 0
    try:
        wins, _ties, losses = (int(p) for p in parts)
    except ValueError:
        return None, 0
    denom = wins + losses
    if denom == 0:
        return None, 0
    return wins / denom, denom


def _wtl_win_pct(record: str | None) -> float | None:
    """`_wtl_stats()` 只取勝率、不要場次數的簡化版本，給不需要做收斂的呼叫端用。"""
    return _wtl_stats(record)[0]


def _shrink_toward(
    value: float | None,
    *,
    sample_size: float,
    prior_strength: float,
    prior_value: float = 0.5,
) -> float:
    """貝氏收斂：樣本數 sample_size 越小，結果越靠近 prior_value；越大則越接近
    原始的 value 本身。value 是 None（完全沒有資料）時直接回傳 prior_value。

    公式等同於「先驗場次數 prior_strength、勝率剛好等於 prior_value」的一組
    假想場次，跟真實場次數加權平均——這是處理小樣本統計最基本、也最常見的
    做法，比直接相信「3 戰 0 勝」字面上的 0% 更合理。
    """
    if value is None or sample_size <= 0:
        return prior_value
    total = sample_size + prior_strength
    return (sample_size * value + prior_strength * prior_value) / total


def _weighted_average(values: list[tuple[float | None, float]]) -> float | None:
    """對 (數值, 權重) 這種 pair 的清單做加權平均，自動跳過數值是 None 的項目、
    並把權重重新正規化到剩下的項目上（而不是把缺值當成 0 分去拖低平均）。
    """
    present = [(v, w) for v, w in values if v is not None]
    if not present:
        return None
    total_weight = sum(w for _v, w in present)
    if total_weight == 0:
        return None
    return sum(v * w for v, w in present) / total_weight


@dataclass
class TeamPowerRating:
    team_name: str
    season_win_pct: float | None
    pythagorean_win_pct: float | None
    recent_form_win_pct: float | None
    home_win_pct: float | None
    away_win_pct: float | None
    power_rating: float


def compute_team_power_ratings(
    standings_df: pd.DataFrame,
    batting_df: pd.DataFrame,
    pitching_df: pd.DataFrame,
    *,
    weights: tuple[float, float, float] = DEFAULT_WEIGHTS,
) -> pd.DataFrame:
    """算出每支球隊的實力評分，回傳一個以 team_name 為主鍵的 DataFrame。

    需要同時有球隊戰績、打者數據、投手數據三份資料——畢氏期望值需要
    球隊層級的得分/失分，這兩個數字官網的戰績表本身沒有，得從打者的
    「得分」欄位、投手的「失分」欄位各自加總才能算出來（見
    sabermetrics.team_batting_aggregates / team_pitching_aggregates）。
    """
    if standings_df.empty:
        return pd.DataFrame(
            columns=[
                "team_name", "season_win_pct", "pythagorean_win_pct",
                "recent_form_win_pct", "home_win_pct", "away_win_pct", "power_rating",
            ]
        )

    team_runs_scored = (
        team_batting_aggregates(batting_df)[["team_name", "runs"]].rename(columns={"runs": "runs_scored"})
        if not batting_df.empty
        else pd.DataFrame(columns=["team_name", "runs_scored"])
    )
    team_runs_allowed = (
        team_pitching_aggregates(pitching_df)[["team_name", "runs_allowed"]]
        if not pitching_df.empty
        else pd.DataFrame(columns=["team_name", "runs_allowed"])
    )

    merged = standings_df.merge(team_runs_scored, on="team_name", how="left")
    merged = merged.merge(team_runs_allowed, on="team_name", how="left")

    league_home_pcts: list[float] = []
    league_away_pcts: list[float] = []
    rows: list[dict] = []
    for _, row in merged.iterrows():
        pyth = None
        if pd.notna(row.get("runs_scored")) and pd.notna(row.get("runs_allowed")):
            pyth = pythagorean_win_pct(row["runs_scored"], row["runs_allowed"])
        recent, recent_n = _wtl_stats(row.get("last_10"))
        home_pct, home_n = _wtl_stats(row.get("home_record"))
        away_pct, away_n = _wtl_stats(row.get("away_record"))
        if home_pct is not None:
            league_home_pcts.append(home_pct)
        if away_pct is not None:
            league_away_pcts.append(away_pct)
        season_games = int(row.get("games") or 0)
        rows.append(
            {
                "team_name": row["team_name"],
                # 這幾欄是「原始」統計數字（沒做收斂），給網頁版表格如實呈現用；
                # 收斂只用在下面算 power_rating／主客場優勢調整這種會直接影響
                # 預測機率的地方，不會偷偷竄改攤在畫面上給人看的原始數字。
                "season_win_pct": row.get("win_pct"),
                "pythagorean_win_pct": round(pyth, 3) if pyth is not None else None,
                "recent_form_win_pct": round(recent, 3) if recent is not None else None,
                "home_win_pct": round(home_pct, 3) if home_pct is not None else None,
                "away_win_pct": round(away_pct, 3) if away_pct is not None else None,
                # 收斂後的版本，只給下面組成 power_rating／主客場調整用。
                "_season_win_pct_shrunk": _shrink_toward(
                    row.get("win_pct"), sample_size=season_games, prior_strength=SEASON_STAT_PRIOR_GAMES
                ),
                "_pythagorean_shrunk": _shrink_toward(
                    pyth, sample_size=season_games, prior_strength=SEASON_STAT_PRIOR_GAMES
                ),
                "_recent_form_shrunk": _shrink_toward(
                    recent, sample_size=recent_n, prior_strength=RECENT_FORM_PRIOR_GAMES
                ),
                "_home_pct_shrunk": _shrink_toward(
                    home_pct, sample_size=home_n, prior_strength=HOME_AWAY_PRIOR_GAMES
                ),
                "_away_pct_shrunk": _shrink_toward(
                    away_pct, sample_size=away_n, prior_strength=HOME_AWAY_PRIOR_GAMES
                ),
            }
        )

    league_avg_home = sum(league_home_pcts) / len(league_home_pcts) if league_home_pcts else 0.5
    league_avg_away = sum(league_away_pcts) / len(league_away_pcts) if league_away_pcts else 0.5

    pyth_w, season_w, recent_w = weights
    for r in rows:
        r["power_rating"] = round(
            _weighted_average(
                [
                    (r["_pythagorean_shrunk"], pyth_w),
                    (r["_season_win_pct_shrunk"], season_w),
                    (r["_recent_form_shrunk"], recent_w),
                ]
            )
            or 0.5,
            3,
        )
        # 這支球隊主場/客場「相對聯盟平均」的優劣勢（用收斂後的數字算，理由
        # 同上：主客場戰績常常只有個位數場次，字面上的落差很容易只是雜訊），
        # 之後算對戰勝率時會用這個落差微調 log5 算出來的基礎機率。
        r["home_edge_vs_league"] = round(r["_home_pct_shrunk"] - league_avg_home, 3)
        r["away_edge_vs_league"] = round(r["_away_pct_shrunk"] - league_avg_away, 3)
        for internal_key in (
            "_season_win_pct_shrunk", "_pythagorean_shrunk", "_recent_form_shrunk",
            "_home_pct_shrunk", "_away_pct_shrunk",
        ):
            del r[internal_key]

    return pd.DataFrame(rows)


def log5_win_probability(rating_a: float, rating_b: float) -> float:
    """Bill James 的 log5 公式：兩支「非聯盟平均」實力球隊對戰時，A 隊的勝率。

    rating_a / rating_b 是兩隊各自對「聯盟平均球隊」的期望勝率（0~1）。
    兩隊實力完全相同時（rating_a == rating_b），結果會是 0.5，符合直覺。
    """
    rating_a = min(max(rating_a, 0.001), 0.999)
    rating_b = min(max(rating_b, 0.001), 0.999)
    numerator = rating_a - rating_a * rating_b
    denominator = rating_a + rating_b - 2 * rating_a * rating_b
    if denominator == 0:
        return 0.5
    return numerator / denominator


def predict_matchup(
    home_team: str,
    away_team: str,
    power_ratings: pd.DataFrame,
    *,
    home_pitcher: str | None = None,
    away_pitcher: str | None = None,
    pitcher_lookup: dict[str, tuple[float, float]] | None = None,
    league_avg_era: float | None = None,
) -> dict | None:
    """預測一場比賽的主客隊勝率。

    回傳 None 代表兩隊裡至少有一支球隊不在 power_ratings 裡（例如球隊名稱
    對不上、或那支球隊還沒有任何戰績資料），呼叫端應該把這種情況當成
    「這場比賽目前無法預測」處理，而不是硬塞一個 0.5/0.5 的假結果。

    home_pitcher／away_pitcher／pitcher_lookup／league_avg_era 都是選填的：
    有提供先發投手姓名、且姓名對得上 pitcher_lookup 裡的資料時，才會套用
    先發投手 ERA 調整（見本檔案開頭 docstring 第 6 點、`_pitcher_edge()`）；
    任何一項缺資料，這個調整量就是 0，預測仍然照樣算得出來，只是不包含
    先發投手因素。
    """
    ratings_by_team = power_ratings.set_index("team_name")
    if home_team not in ratings_by_team.index or away_team not in ratings_by_team.index:
        return None

    home = ratings_by_team.loc[home_team]
    away = ratings_by_team.loc[away_team]

    base_home_prob = log5_win_probability(home["power_rating"], away["power_rating"])

    # 主客場優勢調整：把主隊的「主場優於聯盟平均」幅度，跟客隊的
    # 「客場優於聯盟平均」幅度相減，當成對 log5 基礎機率的微調——
    # 只是加減，不是重新正規化，避免調整過頭讓機率跑出 [0, 1] 之外。
    home_field_adjustment = ((home["home_edge_vs_league"] or 0) - (away["away_edge_vs_league"] or 0)) / 2

    # 先發投手調整：邏輯跟主客場優勢調整一樣，是額外的加減微調，不是
    # 重新正規化。home_pitcher_edge/away_pitcher_edge 找不到資料時都是 0，
    # 兩者相減後這裡自然也是 0，不影響其他因素算出來的機率。
    lookup = pitcher_lookup or {}
    home_pitcher_edge = _pitcher_edge(home_pitcher, pitcher_lookup=lookup, league_avg_era=league_avg_era)
    away_pitcher_edge = _pitcher_edge(away_pitcher, pitcher_lookup=lookup, league_avg_era=league_avg_era)
    pitcher_adjustment = (home_pitcher_edge - away_pitcher_edge) / 2

    home_prob = min(max(base_home_prob + home_field_adjustment + pitcher_adjustment, 0.01), 0.99)

    return {
        "home_team": home_team,
        "away_team": away_team,
        "home_win_prob": round(home_prob, 3),
        "away_win_prob": round(1 - home_prob, 3),
        "home_power_rating": home["power_rating"],
        "away_power_rating": away["power_rating"],
        "home_pitcher": home_pitcher,
        "away_pitcher": away_pitcher,
        "home_pitcher_era": round(lookup[home_pitcher][0], 2) if home_pitcher in lookup else None,
        "away_pitcher_era": round(lookup[away_pitcher][0], 2) if away_pitcher in lookup else None,
    }


def _clean_optional_str(value) -> str | None:
    """把 pandas 讀出來的「空字串／NaN／None」統一收斂成 None，其餘原樣回傳。

    賽程 CSV／DataFrame 裡缺值不一定長同一個樣子——CSV 讀回來可能是空字串，
    DataFrame 原生缺值可能是 NaN（float），這裡統一處理成 None，呼叫端不用
    自己重複判斷好幾種「缺值」的寫法。
    """
    if value is None:
        return None
    if isinstance(value, float) and pd.isna(value):
        return None
    text = str(value).strip()
    return text or None


def predict_upcoming_games(
    schedule_df: pd.DataFrame,
    power_ratings: pd.DataFrame,
    pitching_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """從賽程資料裡挑出「還沒比出比分」的比賽，逐場算出勝率預測。

    「還沒比出比分」用 away_score／home_score 是否為缺值（NaN）判斷，
    而不是用 status 文字判斷——目前只確認過「已完賽」這個狀態值的真實
    文字，未開賽/延賽等其他狀態的官網真實文字還沒見過範例，比分缺值
    是目前唯一能確定、不會因為狀態文字改版就失效的判斷依據。

    pitching_df 是選填的：有提供的話，會拿來建立先發投手 ERA 查詢表跟
    局數加權聯盟平均 ERA，套用先發投手調整（見 `predict_matchup`）；
    不提供（或賽程資料裡本來就沒有 away_pitcher/home_pitcher 欄位）的話，
    預測仍然照舊算得出來，只是不包含先發投手因素。
    """
    columns = [
        "game_date", "away_team", "home_team", "venue",
        "home_win_prob", "away_win_prob", "home_power_rating", "away_power_rating",
        "away_pitcher", "home_pitcher", "away_pitcher_era", "home_pitcher_era",
    ]
    if schedule_df.empty:
        return pd.DataFrame(columns=columns)

    upcoming = schedule_df[schedule_df["home_score"].isna() & schedule_df["away_score"].isna()]

    pitcher_lookup = _pitcher_lookup(pitching_df) if pitching_df is not None else {}
    league_avg_era = _league_avg_era(pitching_df) if pitching_df is not None else None

    rows: list[dict] = []
    for _, game in upcoming.iterrows():
        home_pitcher = _clean_optional_str(game.get("home_pitcher"))
        away_pitcher = _clean_optional_str(game.get("away_pitcher"))
        prediction = predict_matchup(
            game["home_team"],
            game["away_team"],
            power_ratings,
            home_pitcher=home_pitcher,
            away_pitcher=away_pitcher,
            pitcher_lookup=pitcher_lookup,
            league_avg_era=league_avg_era,
        )
        if prediction is None:
            continue
        rows.append(
            {
                "game_date": game.get("game_date"),
                "venue": game.get("venue"),
                **prediction,
            }
        )

    return pd.DataFrame(rows, columns=columns)
