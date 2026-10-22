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
5. **加完 Secret 後務必到「Deployments」分頁確認新版本已 Promote 成 Active**——
   Cloudflare 新版 Dashboard 加 Secret 只會建立新版本，**不會自動上線**，
   不做這步會一直卡在舊版本回應（踩過的坑，見下方「已知問題」）
6. 存檔後，記下這個 Worker 的網址（形如 `https://fics-translate.<你的帳號>.workers.dev`）

## 防濫用：每日翻譯字元上限（強烈建議設定）

`SITE_SHARED_SECRET` 因為要給前端用，一定會出現在公開網頁原始碼裡，
不是真正的保密機制——有心人抓到網址+密鑰後可以繞過網站直接呼叫，
例如拿去翻譯整篇論文。加一道「不管誰呼叫、一天總翻譯字元數超過上限
（程式內 `DAILY_CHAR_CAP`，預設 20,000 字元）就全部拒絕」的硬性防線：

1. Cloudflare Dashboard → 左側「**Storage & Databases**」→「**KV**」
2. 「Create namespace」，取名例如 `fics-translate-usage` → Create
3. 回到這個 Worker（`ics-translate`）→「**Settings**」→「**Bindings**」→「Add」
4. 選「**KV Namespace**」，Variable name 填 **`USAGE_KV`**（大小寫要一致，程式碼用這個名字讀取），
   選剛剛建立的命名空間 → 存檔
5. 一樣要到「Deployments」分頁 Promote 新版本才會生效

未綁定 `USAGE_KV` 時此限制不生效（向下相容），但**強烈建議設定**，
這是目前唯一能真正擋住「密鑰外流後被拿去大量翻譯」的防線。

## 額外建議：Google Cloud 帳單預算提醒

即使有上述每日上限，也建議在 Google Cloud Console 設一道保險：
1. Google Cloud Console → 左側選單「**Billing**」→「**Budgets & alerts**」
2. 「Create budget」，範圍選這個專案（`fics-6e2cd`）
3. 金額設一個很低的門檻（例如 **1 美元**）
4. 「Actions」勾選 email 通知（預設 50%/90%/100% 時提醒）
5. 存檔——之後只要花費接近 1 美元就會收到 email，遠早於真正產生大筆帳單前就能察覺異常

## 部署完成後

把以下兩項告訴接手串接前端的 AI／開發者：
- Worker 網址
- 你設定的 `SITE_SHARED_SECRET` 值

前端 `index.html` 會用這組密鑰＋網址呼叫本 Worker。`SITE_SHARED_SECRET` 因為要被前端
（公開網頁原始碼）使用，**不是銀行等級的保密**，但足以擋掉隨機掃描與亂打——真正的
保護是 Google API 金鑰本身完全不會出現在任何前端程式碼或 GitHub repo 裡。

## 已知問題（踩過的坑）

Cloudflare 新版 Dashboard 在 Settings 加 Secret／Variable 後，**不會自動把新版本設為
Active**，還是舊版本在跑（即使 Settings 頁面顯示新值已存在）。每次改完 Secret 或
Bindings，都要到「**Deployments**」分頁，找最新那筆版本的「...」選單點「**Promote
version**」，否則改動不會生效、會一直回應舊行為（例如密鑰改了還是回 401）。

## 已驗證

- `translate-worker.js` 已用 Node.js 模擬 9 種情境測試（缺授權/錯誤密鑰/OPTIONS 預檢/
  空輸入/超過筆數上限/單筆過長/正常翻譯流程/缺金鑰設定/Google 端錯誤），全數通過。
- 每日字元上限（2026-08-17 新增）另以模擬 KV 測試 5 種情境（未綁 KV 不限制／正常用量
  累計正確／超過上限拒絕且不誤扣額度／剛好卡邊界放行／模擬持續大量呼叫在額度內被
  正確攔停），全數通過。
- 實際部署（Cloudflare + 真實 Google Translation API）已由使用者以 curl 實測成功。

## 2026-10-20：專有名詞修正（無線電機 → radio）

使用者回報很多「無線電機」相關故障被 Google 翻成 wireless（甚至 "wireless motor"），
應該要是 radio（車上的無線電收發機，不是馬達）。查詞庫 `zh_en.json` 本身沒問題，
問題出在**沒被詞庫完全比對到、因此送去 Google 即時翻譯**的新故障描述——Google
不懂這個領域術語，逐字翻成 wireless。

修法是在這支 Worker 裡新增 `TERM_FIXES`：拿到 Google 的翻譯結果後，依原文（中文）
是否含「無線電機」且不含「無線AP／無線基地台」（這兩個才是真的該翻成 wireless 的
情境，要排除掉避免誤改），命中就把英文輸出裡的 wireless 相關字詞換成 radio。
已用實際回報的兩個例句驗證修正正確、且不影響無線AP的翻譯。

**改完程式碼後，照上方「部署步驟」把新內容貼回 Cloudflare Dashboard 並記得
「Promote version」**（見上方「已知問題」），不然線上還是跑舊版、不會修正。

新增其他類似的術語誤譯時，比照 `TERM_FIXES` 裡「無線電機」這筆的格式加新項目即可，
不需要改其他邏輯。

## 2026-10-22：專有名詞修正（缺 → lack，而非 missing）

使用者指出「缺」(東西廠商該給卻沒給、沒附上) 翻成 missing 語感不太對，應該要用
lack/lacking——missing 比較像「原本有、後來不見了」(對應「遺失」)，缺的情境是
「本來就該有但一直沒有」，用 lack 才貼切。

- **詞庫**（`zh_en.json`）：手動修正了 12 筆含「缺」的既有條目，依句型用
  `X lacks Y`（有主詞）或 `Lack of Y`（無主詞、句首）改寫，不是機械式換字
  （另有一筆「缺失表」是「瑕疵/缺陷紀錄表」的意思，跟「缺少東西」無關，沒有動它）
- **Worker**：`TERM_FIXES` 新增一筆，依原文是否含「缺」且不含「缺失」命中，
  把英文輸出裡的 missing 換成 lacking（排除「缺失」避免誤改到不同意思的詞）。
  這筆保留原字首大小寫（句首的 Missing 會變 Lacking，不會變小寫開頭）
- 同時把 `applyTermFixes()` 的取代邏輯改成會保留大小寫，**連帶修好了無線電機
  那筆原本句首會被換成小寫 "radio..." 的小瑕疵**
- 已驗證：「缺」觸發 lacking、「遺失」不受影響仍是 missing（兩者語意本來就不同，
  這是刻意的）、「缺失」排除規則正常運作

**改完程式碼後一樣要照上方「部署步驟」貼回 Cloudflare 並 Promote version。**
已存在 Firestore 的舊翻譯不會自動回溯更新，道理同上一節。
