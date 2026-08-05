import { parse } from "csv-parse/sync";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";

/**
 * 讀取 data/latest/ 底下的資料快照（見 scripts/copy-data.mjs：build/dev
 * 之前會先把 repo 根目錄的 data/latest/ 複製一份進 web/data/latest/）。
 *
 * 這裡全部是同步、單純的檔案讀取（fs.readFileSync + JSON.parse／csv-parse），
 * 沒有非同步 I/O、沒有隨機性——Next.js 在沒有開啟 Cache Components 的
 * 預設模式下，這種「確定性操作」的 Server Component 會在建置時直接產生
 * 靜態內容，不需要額外的快取／Suspense 設定。GitHub Actions 排程爬蟲後
 * commit 新的 data/latest/ 快照，觸發 Vercel 重新建置，網站就會跟著更新。
 */

const DATA_DIR = path.join(process.cwd(), "data", "latest");

function readJson<T>(filename: string): T | null {
  const filePath = path.join(DATA_DIR, filename);
  if (!existsSync(filePath)) return null;
  return JSON.parse(readFileSync(filePath, "utf-8")) as T;
}

function readCsv<T extends Record<string, string>>(filename: string): T[] {
  const filePath = path.join(DATA_DIR, filename);
  if (!existsSync(filePath)) return [];
  const raw = readFileSync(filePath, "utf-8");
  return parse(raw, { columns: true, skip_empty_lines: true, bom: true }) as T[];
}

function toNumberOrNull(value: string | undefined): number | null {
  if (value === undefined || value === "" || value === "None") return null;
  const n = Number(value);
  return Number.isNaN(n) ? null : n;
}

export interface TeamStanding {
  rank: number | null;
  teamName: string;
  games: number;
  wins: number;
  losses: number;
  ties: number;
  winPct: number;
  gamesBehind: string | null;
  eliminationNumber: string | null;
  homeRecord: string | null;
  awayRecord: string | null;
  streak: string | null;
  last10: string | null;
}

export function getStandings(): TeamStanding[] {
  const rows = readCsv<Record<string, string>>("standings.csv");
  return rows
    .map((r) => ({
      rank: toNumberOrNull(r.rank),
      teamName: r.team_name,
      games: toNumberOrNull(r.games) ?? 0,
      wins: toNumberOrNull(r.wins) ?? 0,
      losses: toNumberOrNull(r.losses) ?? 0,
      ties: toNumberOrNull(r.ties) ?? 0,
      winPct: toNumberOrNull(r.win_pct) ?? 0,
      gamesBehind: r.games_behind || null,
      eliminationNumber: r.elimination_number || null,
      homeRecord: r.home_record || null,
      awayRecord: r.away_record || null,
      streak: r.streak || null,
      last10: r.last_10 || null,
    }))
    .sort((a, b) => b.winPct - a.winPct);
}

export interface ScheduleGame {
  gameDate: string;
  awayTeam: string;
  homeTeam: string;
  awayScore: number | null;
  homeScore: number | null;
  status: string;
  venue: string | null;
}

export function getSchedule(): ScheduleGame[] {
  const rows = readCsv<Record<string, string>>("schedule.csv");
  return rows.map((r) => ({
    gameDate: r.game_date,
    awayTeam: r.away_team,
    homeTeam: r.home_team,
    awayScore: toNumberOrNull(r.away_score),
    homeScore: toNumberOrNull(r.home_score),
    status: r.status || "",
    venue: r.venue || null,
  }));
}

export interface PowerRating {
  teamName: string;
  seasonWinPct: number | null;
  pythagoreanWinPct: number | null;
  recentFormWinPct: number | null;
  homeWinPct: number | null;
  awayWinPct: number | null;
  powerRating: number;
}

export function getPowerRatings(): PowerRating[] {
  const rows = readJson<Array<Record<string, number | string | null>>>("power_ratings.json") ?? [];
  return rows
    .map((r) => ({
      teamName: String(r.team_name),
      seasonWinPct: (r.season_win_pct as number) ?? null,
      pythagoreanWinPct: (r.pythagorean_win_pct as number) ?? null,
      recentFormWinPct: (r.recent_form_win_pct as number) ?? null,
      homeWinPct: (r.home_win_pct as number) ?? null,
      awayWinPct: (r.away_win_pct as number) ?? null,
      powerRating: Number(r.power_rating),
    }))
    .sort((a, b) => b.powerRating - a.powerRating);
}

export interface GamePrediction {
  gameDate: string;
  awayTeam: string;
  homeTeam: string;
  venue: string | null;
  homeWinProb: number;
  awayWinProb: number;
  homePowerRating: number;
  awayPowerRating: number;
  /** 先發投手姓名——資料來源是猜測性寫法，可能是 null（見 predictions.py 的說明）。 */
  awayPitcher: string | null;
  homePitcher: string | null;
  /** 先發投手本季 ERA（防禦率），對不到投手數據時是 null。 */
  awayPitcherEra: number | null;
  homePitcherEra: number | null;
}

export function getPredictions(): GamePrediction[] {
  const rows = readJson<Array<Record<string, number | string | null>>>("predictions.json") ?? [];
  return rows.map((r) => ({
    gameDate: String(r.game_date),
    awayTeam: String(r.away_team),
    homeTeam: String(r.home_team),
    venue: (r.venue as string) ?? null,
    homeWinProb: Number(r.home_win_prob),
    awayWinProb: Number(r.away_win_prob),
    homePowerRating: Number(r.home_power_rating),
    awayPowerRating: Number(r.away_power_rating),
    awayPitcher: (r.away_pitcher as string) ?? null,
    homePitcher: (r.home_pitcher as string) ?? null,
    awayPitcherEra: toNumberOrNull(r.away_pitcher_era == null ? undefined : String(r.away_pitcher_era)),
    homePitcherEra: toNumberOrNull(r.home_pitcher_era == null ? undefined : String(r.home_pitcher_era)),
  }));
}

export interface LastUpdated {
  scrapedAt: string | null;
  year: number | null;
}

export function getLastUpdated(): LastUpdated {
  const data = readJson<{ scraped_at: string; year: number | null }>("last_updated.json");
  return { scrapedAt: data?.scraped_at ?? null, year: data?.year ?? null };
}

/** 「信心等級」（1~5 顆星）：勝率跟 0.5 的差距越大，模型對這場比賽的判斷越有把握。 */
export function confidenceFromProb(prob: number): number {
  const distance = Math.abs(prob - 0.5) * 2; // 0~1
  return Math.max(1, Math.min(5, Math.round(1 + distance * 4)));
}
