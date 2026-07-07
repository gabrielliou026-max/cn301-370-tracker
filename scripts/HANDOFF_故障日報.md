# DT&E 故障日報 & 追蹤網站 — 專案交接文件 (Handoff)

> 這份文件用於把「故障追蹤網站（73G/74G/75G 三單位）+ DT&E 故障日報」維護工作轉移到新的對話框。
> 貼上或附上此檔給新對話，即可無縫接手。
> 最後更新：2026-07-07

---

## ✅ Firestore 規則已於 2026-07-06 更新（7/8 到期問題已解除）

現行規則（無到期日、只開放 faultData）：

```
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    // 只開放 faultData，其他路徑一律拒絕
    match /faultData/{car} {
      allow read, write: if true;
    }
  }
}
```

- 更新前已按網站「📥 備份」下載 JSON 快照
- faultData 仍為公開可讀寫（與改版前相同）
- 資料庫另有 `carStatus`、`missionOps` 兩個 collection，已被此規則封鎖
  （2026-07-06 使用者確認只開 faultData；若日後有工具壞掉，到 Console 規則加開即可）
- 進一步防外人寫入：建議 Google 登入＋email 白名單（write 限白名單、
  read 維持 `if true` 公開，日報腳本免改）；網站端需加登入流程

---

## ⚠️ 0. 資料保護規則（給接手的 AI：務必遵守）

**Firestore `faultData` 的故障紀錄是使用者核心資產，預設唯讀。**

1. **禁止寫入 Firestore**：不得對 `faultData` 執行任何寫入（POST / PATCH / DELETE / commit / updateMask）。
   報告腳本只做 GET 讀取，請維持這個設計，不要加入寫入邏輯。
2. **要改資料庫，先明確確認**：只有在使用者「明講」要修改某筆資料時才動，動之前先列出要改什麼、請使用者確認。
3. **改網站/腳本走分支 + 先確認**：修改 `index.html` 或 `scripts/` 前，先說明改動範圍，
   使用者同意後才 commit / push；合併上線（merge 到 main）前再確認一次。
4. **不要把金鑰再寫死擴散**：API key 屬 Firebase web key，勿再複製到新檔案。

---

## 1. 專案組成

| 部分 | 說明 |
|---|---|
| **追蹤網站** | `index.html` 單檔，GitHub Pages 部署（main 分支），多人即時填報故障 |
| **日報腳本** | `scripts/gen_word_report.py`，抓 Firestore 產 Word 故障日報（中英對照） |

---

## 2. 關鍵檔案位置（已全部 commit 進 repo，不再依賴 scratchpad）

| 檔案 | 路徑 | 用途 |
|---|---|---|
| **主產製腳本** | `scripts/gen_word_report.py` | 抓 Firestore → 產 Word。**最重要的檔案** |
| 比對腳本 | `scripts/compare_report.py` | 比對 PDF 基準 vs 現行 Firestore 資料 |
| 網站主檔 | `index.html` | GitHub Pages 單檔網站 |
| 本文件 | `scripts/HANDOFF_故障日報.md` | 交接文件 |

> 產出的 `.docx` 報告與 `pdf_baseline.json` 屬每日產物，不進 repo（見 `scripts/.gitignore`）。

---

## 3. Firebase / Firestore 設定

```
API_KEY    = "AIzaSyBRNMZFCSnWk1X_HZMuDa_ym-Zvwk9ei-U"
PROJECT_ID = "fics-6e2cd"
BASE_URL   = https://firestore.googleapis.com/v1/projects/fics-6e2cd/databases/(default)/documents
Collection = faultData   (每個 doc = 一台車，doc id = 車號如 CN301)
```

**抓取方式**：REST API，`GET {BASE_URL}/faultData?key={API_KEY}&pageSize=200`

**⚠️ 三單位共用同一個 `faultData` collection（2026-07-07 起）**：
73G/74G/75G 的車在同一 collection，以車號（doc id）區分，範圍互不重疊：

| 單位 | 車號範圍 | 台數 | 網址 |
|---|---|---|---|
| 73G | CN301–370（扣 EXCLUDED 16 台）＋ NMS381/382/383 | 57 | 預設或 `?unit=73G` |
| 74G | CN501–514, 519–531, 536–546 ＋ NMS581/582 | 40 | `?unit=74G` |
| 75G | CN401–414, 419–431, 436–446 ＋ NMS481/482 | 40 | `?unit=75G` |

- 如此設計是因現行規則只開放 `faultData`，共用可免改規則
- **新增單位/車輛時務必確認車號不與其他單位重複**（`index.html` 的 `UNITS` 設定）
- 日報腳本 `pageSize=200`：三單位全掛滿約 137 docs，仍在上限內；再擴充需注意分頁
- **日報腳本目前只產 73G**（`ROTATIONS` 只列 73G 車；74G/75G 的 docs 抓下來但不會出現在報告）

**文件結構**（每個 doc = 一台車）：
- 文件層級欄位（字串，**解析時需略過**）：
  - `updatedAt`：最後儲存時間（ISO 8601）
  - `updatedBy`：最後儲存人員名字（2026-07-05 新增）
- 故障項目（map 型態，key 為隨機 id 如 `f1782292280888zls`）：
  `status`, `desc`, `person`(修復人員), `witness`(見證人)

> `gen_word_report.py` 以 `"mapValue" not in fval` 過濾欄位，
> `updatedAt`/`updatedBy` 均為字串會自動略過，**腳本無需修改**。
> 未來若新增其他文件層級欄位，維持字串型態即可相容。

---

## 4. 輪次分組 (57 車，依網站為準)

網站有 `EXCLUDED` set 排除 16 台，故 **總車數 = 57**（不是 70）。

```python
ROTATIONS = [
    ("第一輪 1st Rotation",  ["CN360","CN359","CN358","CN357","CN356","CN353","CN370","CN369","NMS382","NMS381","NMS383"]),  # 11
    ("第二輪 2nd Rotation",  ["CN362","CN320","CN321","CN309","CN302","CN305","CN301","CN344","CN329","CN323","CN303","CN319","CN308","CN310","CN314"]),  # 15
    ("第三輪 3rd Rotation",  ["CN324","CN337","CN327","CN347","CN326","CN346","CN361","CN355","CN342","CN311","CN330","CN341","CN348","CN354","CN331"]),  # 15
    ("第四輪 4th Rotation",  ["CN343","CN345","CN312","CN339","CN340","CN336","CN307","CN313","CN364","CN322","CN325","CN306","CN338","CN304","CN363","CN328"]),  # 16
]
```

**EXCLUDED (網站排除，不列入報告)**：
`CN315,316,317,318, 332,333,334,335, 349,350,351,352, 365,366,367,368`

---

## 5. 狀態定義與排序

```python
STATUS_ORDER = {"已修復完成":0, "故障":1, "維修中":2, "待確認":3}   # Word 報告表格內排序用
```

| 中文 | English | 顏色 (RGB) |
|---|---|---|
| 故障 | Fault | C00000 (紅) |
| 已修復完成 | Fixed | 0E7490 (青) |
| 維修中 | Under Repair | 7B3F00 (棕) |
| 待確認 | Pending | 1F497D (藍) |

> 網站顯示排序與報告不同：故障 → 維修中 → 待確認 → 已修復完成 → 均完成
> （`index.html` 的 `STATUS_SORT`），修改任一邊時注意兩者是刻意不同的。

---

## 6. 報告版面規格

- **A4 直式**，導覽色系：NAVY=1A2332, BLUE=2D4A8A, TEAL=0E7490(人員), BROWN=92400E(見證)
- **摘要表 6 欄**（順序固定）：
  `總車數 Total Cars` → `有紀錄車廂 Cars w/ Records` → `故障` → `已修復完成` → `維修中` → `待確認`
  - 第一欄「總車數」為 `TOTAL_CARS=57` 固定值，第二欄為實際有紀錄車數
- **故障表格 6 欄**（twips 欄寬，總計 8714，用 `tblLayout:fixed`+`tblGrid`+`tcW` 防溢出）：
  ```
  C_NO=267(#) | C_ST=889(狀態) | C_ZH=2312(中文) | C_EN=2934(English) | C_RP=1156(人員) | C_WT=1156(見證)
  ```
- 車廂標題：藍色左側色條 + 車號；輪次標題：深藍底白字
- 無紀錄車廂顯示「無故障紀錄 No fault records」

---

## 7. 翻譯機制

`gen_word_report.py` 內含 `ZH_EN` 字典（**200+ 筆**）涵蓋所有故障描述。
`translate(zh)` 找不到時回傳原文，並在執行結束印出 WARNING 列出未翻譯項目。

**新增翻譯的標準流程**：
1. 執行腳本，看是否印出 `WARNING: N untranslated descriptions`
2. 若有，跑小腳本比對 Firestore 所有 desc vs `ZH_EN` keys 找出缺漏
3. 把新的中英對照補進 `ZH_EN` 字典結尾（`}` 前）
4. 重跑腳本，確認無 WARNING

---

## 8. 產製指令

```bash
cd scripts
python3 gen_word_report.py
# 輸出：故障日報_YYYY-MM-DD.docx (TODAY 用系統當天日期)
```

**相依套件**：`python-docx`（Word）、`PyMuPDF`/`fitz`（讀 PDF 比對用）

**已知非致命警告**：
`FutureWarning: Truth-testing of elements...`（`tbl.find(qn("w:tblPr")) or ...` 造成）— 不影響輸出。

**最後一次產出（2026-07-02）**：總 283 項 = 故障 66 / 已修復 140 / 維修中 3 / 待確認 74，
總車數 57、有紀錄 54。

---

## 9. 網站功能現況（2026-07-05 大改版 PR #11–#15；2026-07-07 多單位）

### 清點模式（2026-07-07 新增）
- 車輛分類新增「**尚未檢查 unchecked**」＝雲端無任何紀錄的車（先前這類車被誤計入待確認）
- 統計卡共 6 張：總台數｜尚未檢查(灰)｜無故障(綠)｜故障(紅)｜維修中(橘)｜待確認(**藍**，原灰色不易辨識已改）
- 進度條改為「已檢查 Checked：X / N units」（有任何紀錄即算已檢查）
- 尚未檢查的車：狀態選單顯示灰色「**⬜ 尚未檢查 Unchecked**」（虛擬狀態 `__unchecked__`，
  不會寫入雲端），並有「**✓ 均完成 All Clear**」快速鍵一鍵標記（仍需按儲存送出）；
  該車一旦被編輯，選單即時切為待確認、快速鍵消失（`defaultTouched()`）
- `carCategory()` 判斷順序：無真實紀錄→unchecked；全為均完成/已修復→done；再依故障/維修中/待確認

### 單位切換（2026-07-07 新增）
- header 下方 [73G] [74G] [75G] 頁籤，網址參數 `?unit=74G`，無參數/亂填預設 73G
- 每單位獨立車廂清單、標題、統計、備份檔（`faultData_backup_74G_….json`）
- 74G/75G 暫不分輪次；74G/75G 沒有 EXCLUDED 概念（範圍縮排即排除）
- 見證人/更新人員名單三單位目前共用 `WITNESS_NAMES`，如需分單位再拆

### 填報流程
- 每台車可多筆故障，欄位：狀態下拉 / 描述 / 修復人員 /（已修復時）見證人
- **儲存需填更新人員**：確認視窗有下拉名單＋「其他 Other…」自訂輸入（必填、
  空白會被 `trim()` 擋下），名字記在 localStorage 下次自動帶入
- 儲存寫入文件層級 `updatedBy` + `updatedAt`

### 顯示
- Header 右上徽章顯示「🕐 最後更新 時間（人名）」（取全部車 updatedAt 最大值）
- 統計卡片可點擊篩選狀態（再點一次取消）；搜尋框可搜車號/故障描述
- 表頭 sticky；手機（≤640px）自動切換卡片式排版
- 雲端項目依 `STATUS_SORT` 排序顯示

### 防呆
- 未儲存變更離開頁面會警告（beforeunload）
- 連線狀態橫幅：載入中（藍）/ 連線失敗、10 秒逾時（紅）
- 多人同時編輯：快照只重繪有變動的車，正在編輯的車格延後重繪（不失焦）
- 右上「📥 備份」一鍵下載雲端資料 JSON 快照

### 重要歷史 bug（已修，PR #14）
`updateSaveBar()` 原版依賴 `#saveBarCount` id，innerHTML 重寫後 id 消失導致
第二次呼叫起全部拋錯 → 儲存後無法輸入下一筆。**改此函式時勿走回頭路。**

---

## 10. Git 資訊

- Repo: `gabrielliou026-max/cn301-370-tracker`
- 開發分支: `claude/read-markdown-file-6whg0i`（每次合併後重置到最新 main 再開工）
- 網站部署: `main` branch → GitHub Pages（單檔 `index.html`），**merge 到 main 即上線**
- 近期 PR：#11 網站優化 / #12 updatedBy / #13 人員選單 / #14 連續輸入修復 / #15 更新時間移頂端

---

## 11. 常見後續任務

- **產今日報告**：`cd scripts && python3 gen_word_report.py`
- **比對昨晚 vs 現在**：跑 `compare_report.py`，或重新解析 PDF 基準
- **補翻譯**：見第 7 節流程
- **調整輪次/排除車**：改 `gen_word_report.py` 的 `ROTATIONS`，與 `index.html` 的 `EXCLUDED` 保持一致
- **進一步防護（可選）**：Google 登入＋email 白名單規則（建議）或匿名登入（防護有限）；
  每筆故障加時間戳（使用者已知悉、暫緩）

---

## 12. 給新對話的開場提示 (建議貼這段)

> 我在維護 73G/74G/75G 三單位故障追蹤系統：網站 `index.html`（GitHub Pages，`?unit=` 切換單位）＋
> 日報腳本 `scripts/gen_word_report.py`（從 Firestore `faultData` 抓 73G 57 台車資料產 Word 報告）。
> 請先讀 repo 裡的 `scripts/HANDOFF_故障日報.md` 交接文件並遵守其資料保護規則。
> 今天請幫我：〔在此填入需求，例如「產今日報告並補齊翻譯」〕
