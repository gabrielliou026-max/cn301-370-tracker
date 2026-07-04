# DT&E 故障日報 — 專案交接文件 (Handoff)

> 這份文件用於把「DT&E 故障日報」產製工作轉移到新的對話框。
> 貼上或附上此檔給新對話，即可無縫接手。
> 最後更新：2026-07-04

---

## 1. 專案目標

從 Firebase Firestore 抓取 CN301–CN370 車廂的故障資料，產製 **DT&E 故障日報 (Daily Fault Report)** Word 文件，含**完整中英對照翻譯**，格式對齊既有 PDF 樣式。

---

## 2. 關鍵檔案位置

| 檔案 | 路徑 | 用途 |
|---|---|---|
| **主產製腳本** | `scratchpad/gen_word_report.py` | 抓 Firestore → 產 Word。**最重要的檔案** |
| 比對腳本 | `scratchpad/compare_report.py` | 比對 PDF 基準 vs 現行 Firestore 資料 |
| PDF 基準快照 | `scratchpad/pdf_baseline.json` | 解析出的昨晚 PDF 每車故障資料 |
| 產出報告 | `scratchpad/故障日報_YYYY-MM-DD.docx` | 每日產出 |
| 網站主檔 | `/home/user/cn301-370-tracker/index.html` | GitHub Pages 單檔網站 |

> scratchpad 完整路徑前綴：
> `/tmp/claude-0/-home-user-cn301-370-tracker/601937c1-2176-5d8c-aa25-0c267b631065/scratchpad/`
> ⚠️ 此為 session 專屬暫存區，**新 session 會清空**。若要保留 `gen_word_report.py`，
> 建議 commit 進 repo 或請使用者另存。

---

## 3. Firebase / Firestore 設定

```
API_KEY    = "AIzaSyBRNMZFCSnWk1X_HZMuDa_ym-Zvwk9ei-U"
PROJECT_ID = "fics-6e2cd"
BASE_URL   = https://firestore.googleapis.com/v1/projects/fics-6e2cd/databases/(default)/documents
Collection = faultData   (每個 doc = 一台車，doc id = 車號如 CN301)
```

**抓取方式**：REST API，`GET {BASE_URL}/faultData?key={API_KEY}&pageSize=200`

**每個 fault item 欄位**：`status`, `desc`, `person`(修復人員), `witness`(見證人)
- doc 內以 map 型態存放，`updatedAt` 欄位需略過。

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
STATUS_ORDER = {"已修復完成":0, "故障":1, "維修中":2, "待確認":3}   # 表格內排序用
```

| 中文 | English | 顏色 (RGB) |
|---|---|---|
| 故障 | Fault | C00000 (紅) |
| 已修復完成 | Fixed | 0E7490 (青) |
| 維修中 | Under Repair | 7B3F00 (棕) |
| 待確認 | Pending | 1F497D (藍) |

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
- 車廂標題：藍色左側色條 + 車號
- 輪次標題：深藍底白字
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

## 8. 最新狀態 (2026-07-02 報告)

| 指標 | 數值 |
|---|---|
| 總車數 Total Cars | 57 |
| 有紀錄車廂 | 54 |
| 故障 Fault | 66 |
| 已修復完成 Fixed | 140 |
| 維修中 Under Repair | 3 |
| 待確認 Pending | 74 |
| **總項目數** | **283** |

**與前一晚 PDF 相比的變化**（+8 項）：
- 已修復完成 +7、待確認 +1
- 狀態變動：CN336(+3修復)、CN340(+2修復)、CN347(+1修復)、CN311(+1修復)
- 待確認轉故障：CN306(+3)
- 新增待確認：CN303/308/328(各+3)、CN363(+2)、CN329(+1)
- 刪除重複項：CN353、CN322、CN364

---

## 9. 產製指令

```bash
cd <scratchpad>
python3 gen_word_report.py
# 輸出：故障日報_YYYY-MM-DD.docx (TODAY 用系統當天日期)
```

**相依套件**：`python-docx`（Word）、`PyMuPDF`/`fitz`（讀 PDF 比對用）

**已知非致命警告**：
`FutureWarning: Truth-testing of elements...`（`tbl.find(qn("w:tblPr")) or ...` 造成）— 不影響輸出。

---

## 10. Git 資訊

- Repo: `gabrielliou026-max/cn301-370-tracker`
- 開發分支: `claude/website-content-modify-pe7y5j`
- 網站部署: `main` branch → GitHub Pages（單檔 `index.html`）

---

## 11. 常見後續任務

- **產今日報告**：直接跑 `gen_word_report.py`（會用當天日期）
- **比對昨晚 vs 現在有無新增/更新**：跑 `compare_report.py`，或重新解析 PDF 基準
- **補翻譯**：見第 7 節流程
- **調整輪次/排除車**：改 `gen_word_report.py` 的 `ROTATIONS`，與 `index.html` 的 `EXCLUDED` 保持一致

---

## 12. 給新對話的開場提示 (建議貼這段)

> 我在做 DT&E 故障日報產製。主腳本是 `gen_word_report.py`（附上或在 scratchpad），
> 從 Firestore `faultData` collection 抓 57 台車故障資料產 Word 報告，含中英翻譯。
> 請參考這份 HANDOFF 文件。今天請幫我：〔在此填入需求，例如「產今日報告並補齊翻譯」〕
