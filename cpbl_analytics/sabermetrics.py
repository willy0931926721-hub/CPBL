"""進階數據分析：在官網原始數據之上，計算職業分析師常用的衍生指標。

這裡的每一個「近似」指標都有明確標注（_approx 字尾或 docstring 說明），
因為像 wOBA、FIP 這類指標的正式係數，是用大聯盟逐年的實際得分環境跑迴歸
算出來的；中華職棒沒有公開對應的官方係數，所以這裡採用文獻上通用的
近似權重（Tom Tango 的 wOBA 簡化版、FIP 常數抓 3.10 這個常見預設值）。
拿來做「球員之間的相對排序、球隊之間的比較」是合理的，但不要把數字
直接當成跟 MLB 官方 wOBA 一樣精確的絕對值來引用。
"""
from __future__ import annotations

import pandas as pd

# 簡化版 wOBA 權重（Tom Tango, "The Book"，未逐年校正 CPBL 得分環境）
WOBA_WEIGHTS = {
    "bb": 0.69,
    "hbp": 0.72,
    "single": 0.89,
    "double": 1.27,
    "triple": 1.62,
    "hr": 2.10,
}
WOBA_SCALE = 1.15  # 讓 wOBA 的量尺跟 OBP 接近，方便閱讀

FIP_CONSTANT = 3.10  # 常見預設值；嚴謹分析應改用該球季聯盟平均 ERA 反推


def add_batting_advanced_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """在打者資料表上加上 ISO、BB%、K%、BABIP、近似 wOBA 等欄位。"""
    if df.empty:
        return df
    out = df.copy()
    singles = out["hits"] - out["doubles"] - out["triples"] - out["home_runs"]
    total_bases = singles + 2 * out["doubles"] + 3 * out["triples"] + 4 * out["home_runs"]

    pa = out.get("plate_appearances")
    if pa is None or pa.isna().all() or (pa == 0).all():
        pa = out["at_bats"] + out["walks"] + out["hit_by_pitch"] + out["sac_bunts"] + out["sac_flies"]
    out["pa_est"] = pa

    out["iso"] = (out["slg"] - out["avg"]).round(3)

    out["bb_rate"] = (out["walks"] / out["pa_est"].replace(0, pd.NA)).round(3)
    out["k_rate"] = (out["strikeouts"] / out["pa_est"].replace(0, pd.NA)).round(3)

    babip_denom = (out["at_bats"] - out["strikeouts"] - out["home_runs"] + out["sac_flies"]).replace(0, pd.NA)
    out["babip"] = ((out["hits"] - out["home_runs"]) / babip_denom).round(3)

    woba_num = (
        WOBA_WEIGHTS["bb"] * out["walks"]
        + WOBA_WEIGHTS["hbp"] * out["hit_by_pitch"]
        + WOBA_WEIGHTS["single"] * singles
        + WOBA_WEIGHTS["double"] * out["doubles"]
        + WOBA_WEIGHTS["triple"] * out["triples"]
        + WOBA_WEIGHTS["hr"] * out["home_runs"]
    )
    out["woba_approx"] = (woba_num / out["pa_est"].replace(0, pd.NA)).round(3)

    out["total_bases"] = total_bases
    return out


def add_pitching_advanced_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """在投手資料表上加上真正的十進位局數、K/9、BB/9、HR/9、近似 FIP 等欄位。"""
    if df.empty:
        return df
    out = df.copy()
    outs = out["innings_pitched_outs"].replace(0, pd.NA)
    ip_float = outs / 3.0
    out["ip_float"] = ip_float.round(3)

    out["k_per_9"] = (out["strikeouts"] * 27 / outs).round(2)
    out["bb_per_9"] = (out["walks"] * 27 / outs).round(2)
    out["hr_per_9"] = (out["home_runs_allowed"] * 27 / outs).round(2)
    out["k_bb_ratio"] = (out["strikeouts"] / out["walks"].replace(0, pd.NA)).round(2)

    if "whip" not in out.columns or out["whip"].isna().all():
        out["whip"] = ((out["walks"] + out["hits_allowed"]) * 3 / outs).round(3)

    fip_num = (
        13 * out["home_runs_allowed"]
        + 3 * (out["walks"] + out.get("hit_by_pitch", 0))
        - 2 * out["strikeouts"]
    )
    out["fip_approx"] = (fip_num / ip_float + FIP_CONSTANT).round(2)
    return out


def pythagorean_win_pct(runs_scored: float, runs_allowed: float, *, exponent: float = 1.83) -> float:
    """畢氏勝率期望值（Bill James 公式，指數採 Pythagenpat 常見的 1.83）。

    用得分/失分推算「理論上」應有的勝率，可以拿來跟球隊實際勝率比較，
    差距大代表這支球隊可能在一分差比賽中特別強/弱、牛棚特別穩/不穩等。
    """
    if runs_scored <= 0 and runs_allowed <= 0:
        return 0.5
    return runs_scored**exponent / (runs_scored**exponent + runs_allowed**exponent)


def team_batting_aggregates(batting_df: pd.DataFrame) -> pd.DataFrame:
    """把個別球員的打擊數據，加總成球隊層級的打擊數據。"""
    if batting_df.empty:
        return batting_df
    sum_cols = [
        "at_bats", "runs", "hits", "doubles", "triples", "home_runs", "rbi",
        "stolen_bases", "caught_stealing", "walks", "hit_by_pitch", "strikeouts",
    ]
    grouped = batting_df.groupby("team_name")[sum_cols].sum().reset_index()
    grouped["avg"] = (grouped["hits"] / grouped["at_bats"]).round(3)
    singles = grouped["hits"] - grouped["doubles"] - grouped["triples"] - grouped["home_runs"]
    tb = singles + 2 * grouped["doubles"] + 3 * grouped["triples"] + 4 * grouped["home_runs"]
    grouped["slg"] = (tb / grouped["at_bats"]).round(3)
    obp_denom = grouped["at_bats"] + grouped["walks"] + grouped["hit_by_pitch"]
    grouped["obp"] = ((grouped["hits"] + grouped["walks"] + grouped["hit_by_pitch"]) / obp_denom).round(3)
    grouped["ops"] = (grouped["obp"] + grouped["slg"]).round(3)
    return grouped.sort_values("ops", ascending=False)


def team_pitching_aggregates(pitching_df: pd.DataFrame) -> pd.DataFrame:
    """把個別投手數據，加總成球隊層級的投手數據。"""
    if pitching_df.empty:
        return pitching_df
    sum_cols = [
        "wins", "losses", "saves", "holds", "innings_pitched_outs", "hits_allowed",
        "home_runs_allowed", "walks", "strikeouts", "runs_allowed", "earned_runs",
    ]
    grouped = pitching_df.groupby("team_name")[sum_cols].sum().reset_index()
    outs = grouped["innings_pitched_outs"].replace(0, pd.NA)
    grouped["ip_float"] = (outs / 3.0).round(1)
    grouped["era"] = (grouped["earned_runs"] * 27 / outs).round(2)
    grouped["whip"] = ((grouped["walks"] + grouped["hits_allowed"]) * 3 / outs).round(3)
    grouped["k_per_9"] = (grouped["strikeouts"] * 27 / outs).round(2)
    return grouped.sort_values("era")
