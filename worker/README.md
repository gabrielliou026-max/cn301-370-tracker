# 即時翻譯 Worker — 部署步驟

這個 Worker 是「回報後自動翻譯」功能的後端：`index.html` 存檔後，對詞庫
（`zh_en.json`）沒收錄的新故障描述呼叫這個 Worker，由它代為呼叫 Google
Cloud Translation API，Google 的金鑰只存在這裡，絕不出現在網站原始碼裡。

## 前置需求

1. **Google Cloud Translation API 金鑰**（在你們的 GCP 專案 `fics-6e2cd`）：
   - Google Cloud Console → 該專案 → 啟用「**Cloud Translation API**」
   - 綁定帳單帳戶（信用卡）——每月 50 萬字元免費，這系統用量遠低於此
   - 「憑證」→「建立憑證」→「API 金鑰」
   - **強烈建議限制此金鑰**：憑證設定 → API 限制 → 只勾選「Cloud Translation API」，
     避免金鑰外洩後被用在其他付費服務上
2. **Cloudflare 帳號**（已完成 ✓）

## 部署步驟

1. 登入 [Cloudflare Dashboard](https://dash.cloudflare.com) → 左側選單「Workers & Pages」
2. 「Create」→「Create Worker」，取個名字（例如 `fics-translate`），Deploy
3. 進入這個 Worker → 「Edit code」，把 `translate-worker.js` 的**全部內容**貼上覆蓋預設程式碼 → 「Deploy」
4. 回到 Worker 頁面 → 「Settings」→「Variables and Secrets」→「Add」，新增兩組（都選 **Secret** 類型，不要選 Text，避免在 Dashboard 明文顯示）：
   | 名稱 | 值 |
   |---|---|
   | `GOOGLE_TRANSLATE_API_KEY` | 上面申請的 Google API 金鑰 |
   | `SITE_SHARED_SECRET` | 自訂一串隨機字串（例如用密碼產生器產生 32 字元亂碼），作為基本防護避免這個網址被隨意呼叫 |
5. 存檔後，記下這個 Worker 的網址（形如 `https://fics-translate.<你的帳號>.workers.dev`）

## 部署完成後

把以下兩項告訴接手串接前端的 AI／開發者：
- Worker 網址
- 你設定的 `SITE_SHARED_SECRET` 值

前端 `index.html` 會用這組密鑰＋網址呼叫本 Worker。`SITE_SHARED_SECRET` 因為要被前端
（公開網頁原始碼）使用，**不是銀行等級的保密**，但足以擋掉隨機掃描與亂打——真正的
保護是 Google API 金鑰本身完全不會出現在任何前端程式碼或 GitHub repo 裡。

## 已驗證

`translate-worker.js` 已用 Node.js 模擬 9 種情境測試（缺授權/錯誤密鑰/OPTIONS 預檢/
空輸入/超過筆數上限/單筆過長/正常翻譯流程/缺金鑰設定/Google 端錯誤），全數通過。
