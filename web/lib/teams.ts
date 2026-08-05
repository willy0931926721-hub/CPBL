/**
 * 球隊名稱、對應色票、簡稱徽章文字。
 *
 * 色票跟 cpbl_analytics/app/utils.py 的 CATEGORICAL_PALETTE 用同一組
 * （dataviz 色彩驗證流程的 8 色分類色票），球隊順序也跟
 * cpbl_analytics/config.py 的 TEAM_NAMES 一致，這樣同一支球隊在 Python
 * 那邊的圖表（畢氏勝率、雷達圖）跟這個 Next.js 網站上永遠是同一個顏色，
 * 不會因為兩套程式碼各自分配顏色而對不上。
 *
 * 沒有使用真正的球隊隊徽圖檔——隊徽是各球團的註冊商標，這個專案沒有
 * 取得授權，改用「球隊色 + 一個代表字」的徽章，設計上乾淨、也沒有版權
 * 疑慮。
 */
export const TEAM_NAMES = [
  "中信兄弟",
  "統一7-ELEVEn獅",
  "樂天桃猿",
  "富邦悍將",
  "台鋼雄鷹",
  "味全龍",
] as const;

export type TeamName = (typeof TEAM_NAMES)[number];

const CATEGORICAL_PALETTE = [
  "#2a78d6", // 1 blue
  "#eb6834", // 2 orange
  "#1baf7a", // 3 aqua
  "#eda100", // 4 yellow
  "#e87ba4", // 5 magenta
  "#008300", // 6 green
  "#4a3aa7", // 7 violet
  "#e34948", // 8 red
];

const NEUTRAL_COLOR = "#898781";

// 每支球隊徽章上顯示的代表字（隊名裡最有辨識度的那個字）。
const TEAM_BADGE_LABEL: Record<string, string> = {
  中信兄弟: "兄弟",
  "統一7-ELEVEn獅": "統一獅",
  樂天桃猿: "樂天",
  富邦悍將: "富邦",
  台鋼雄鷹: "台鋼",
  味全龍: "味全",
};

export function teamColor(teamName: string): string {
  const index = TEAM_NAMES.indexOf(teamName as TeamName);
  if (index === -1) return NEUTRAL_COLOR;
  return CATEGORICAL_PALETTE[index % CATEGORICAL_PALETTE.length];
}

export function teamBadgeLabel(teamName: string): string {
  return TEAM_BADGE_LABEL[teamName] ?? teamName.slice(0, 2);
}
