#!/usr/bin/env python3
"""
Generate Word reports:
  1. Full report (all statuses)
  2. Active-only report (故障 / 維修中 / 待確認)
Both with complete English translations.
"""
import urllib.request, json, datetime, sys, os
from docx import Document
from docx.shared import Pt, RGBColor, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

# ── Config ───────────────────────────────────────────────────────────────────
API_KEY    = "AIzaSyBRNMZFCSnWk1X_HZMuDa_ym-Zvwk9ei-U"
PROJECT_ID = "fics-6e2cd"
BASE_URL   = f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/(default)/documents"
TODAY      = datetime.date.today().isoformat()
# 輸出目錄：預設為腳本所在目錄，可用環境變數 REPORT_OUT_DIR 覆寫
SCRATCHPAD = os.environ.get("REPORT_OUT_DIR", os.path.dirname(os.path.abspath(__file__)))

# ── Rotations (57 cars) ───────────────────────────────────────────────────────
ROTATIONS = [
    ("第一輪 1st Rotation",  ["CN360","CN359","CN358","CN357","CN356","CN353","CN370","CN369","NMS382","NMS381","NMS383"]),
    ("第二輪 2nd Rotation",  ["CN362","CN320","CN321","CN309","CN302","CN305","CN301","CN344","CN329","CN323","CN303","CN319","CN308","CN310","CN314"]),
    ("第三輪 3rd Rotation",  ["CN324","CN337","CN327","CN347","CN326","CN346","CN361","CN355","CN342","CN311","CN330","CN341","CN348","CN354","CN331"]),
    ("第四輪 4th Rotation",  ["CN343","CN345","CN312","CN339","CN340","CN336","CN307","CN313","CN364","CN322","CN325","CN306","CN338","CN304","CN363","CN328"]),
]

# ── Status ────────────────────────────────────────────────────────────────────
# 均完成：網站清點功能（2026-07-07 起）寫入的狀態，排最前
STATUS_ORDER = {"均完成":-1,"已修復完成":0,"故障":1,"維修中":2,"待確認":3}
STATUS_ZH_EN = {
    "均完成":    ("均完成",   "All Clear"),
    "故障":      ("故障",     "Fault"),
    "已修復完成": ("已修復完成","Fixed"),
    "維修中":    ("維修中",    "Under Repair"),
    "待確認":    ("待確認",    "Pending"),
}
STATUS_COLOR = {
    "均完成":    RGBColor(0x16,0x8A,0x3E),
    "故障":      RGBColor(0xC0,0x00,0x00),
    "已修復完成": RGBColor(0x0E,0x74,0x90),
    "維修中":    RGBColor(0x7B,0x3F,0x00),
    "待確認":    RGBColor(0x1F,0x49,0x7D),
}
STATUS_BG = {
    "均完成":    "F0FDF4",
    "故障":      "FFF5F5",
    "已修復完成": "F0FDFC",
    "維修中":    "FFFBF0",
    "待確認":    "F5F7FF",
}
ACTIVE_STATUSES = {"故障","維修中","待確認"}

# ── Colors ────────────────────────────────────────────────────────────────────
NAVY  = RGBColor(0x1A,0x23,0x32)
BLUE  = RGBColor(0x2D,0x4A,0x8A)
WHITE = RGBColor(0xFF,0xFF,0xFF)
TEAL  = RGBColor(0x0E,0x74,0x90)
BROWN = RGBColor(0x92,0x40,0x0E)
GRAY  = RGBColor(0xAA,0xAA,0xAA)

# ── Column widths (twips) ─────────────────────────────────────────────────────
C_NO = 267; C_ST = 889; C_ZH = 2312; C_EN = 2934; C_RP = 1156; C_WT = 1156
COL_WIDTHS = [C_NO, C_ST, C_ZH, C_EN, C_RP, C_WT]
PAGE_W = sum(COL_WIDTHS)  # 8714

# ── Complete translation dictionary ──────────────────────────────────────────
# 翻譯詞庫改為讀取 repo 根目錄的 zh_en.json（與網站共用的單一來源）
ZH_EN_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "zh_en.json")
with open(ZH_EN_PATH, encoding="utf-8") as _f:
    ZH_EN = json.load(_f)

def translate(zh):
    zh_clean = zh.strip()
    if zh_clean in ZH_EN:
        return ZH_EN[zh_clean]
    # Partial match fallback — return original if not found
    return zh_clean

# ── Firestore fetch ───────────────────────────────────────────────────────────
def fetch_all():
    url = f"{BASE_URL}/faultData?key={API_KEY}&pageSize=200"
    req = urllib.request.Request(url, headers={"Accept":"application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read())
    result = {}
    for doc in data.get("documents", []):
        car = doc["name"].split("/")[-1]
        fields = doc.get("fields", {})
        items = []
        for fid, fval in fields.items():
            if fid == "updatedAt": continue
            if "mapValue" not in fval: continue
            m = fval["mapValue"].get("fields", {})
            items.append({
                "id":      fid,
                "status":  m.get("status",  {}).get("stringValue", "待確認"),
                "desc":    m.get("desc",    {}).get("stringValue", ""),
                "person":  m.get("person",  {}).get("stringValue", ""),
                "witness": m.get("witness", {}).get("stringValue", ""),
            })
        if items:
            items.sort(key=lambda x: STATUS_ORDER.get(x["status"], 9))
            result[car] = items
    return result

# ── XML helpers ───────────────────────────────────────────────────────────────
def set_cell_bg(cell, hex_color):
    tcPr = cell._tc.get_or_add_tcPr()
    shd  = OxmlElement("w:shd")
    shd.set(qn("w:val"),   "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"),  hex_color)
    tcPr.append(shd)

def set_cell_width(cell, w):
    tcPr = cell._tc.get_or_add_tcPr()
    tcW  = OxmlElement("w:tcW")
    tcW.set(qn("w:w"),    str(w))
    tcW.set(qn("w:type"), "dxa")
    tcPr.append(tcW)

def set_table_fixed(table, widths):
    tbl   = table._tbl
    tblPr = tbl.find(qn("w:tblPr")) or OxmlElement("w:tblPr")
    if tbl.find(qn("w:tblPr")) is None:
        tbl.insert(0, tblPr)
    lay = OxmlElement("w:tblLayout"); lay.set(qn("w:type"), "fixed"); tblPr.append(lay)
    tw  = OxmlElement("w:tblW"); tw.set(qn("w:w"), str(sum(widths))); tw.set(qn("w:type"), "dxa"); tblPr.append(tw)
    tblGrid = OxmlElement("w:tblGrid")
    for w in widths:
        gc = OxmlElement("w:gridCol"); gc.set(qn("w:w"), str(w)); tblGrid.append(gc)
    tbl.insert(1, tblGrid)

def no_space(para):
    pPr = para._p.get_or_add_pPr()
    sp  = OxmlElement("w:spacing"); sp.set(qn("w:before"), "0"); sp.set(qn("w:after"), "0")
    pPr.append(sp)

def add_run(para, text, bold=False, italic=False, color=None, size=8, align=None):
    if align: para.alignment = align
    no_space(para)
    run = para.add_run(text)
    run.bold   = bold
    run.italic = italic
    run.font.size = Pt(size)
    if color: run.font.color.rgb = color
    return run

# ── Core document builder ─────────────────────────────────────────────────────
def build_doc(fault_data, active_only=False):
    # 只統計 ROTATIONS 範圍內的車：faultData collection 自 2026-07-07 起
    # 含 74G/75G 車輛，若不過濾，摘要數字會混入其他單位的項目
    cars_in_scope = {c for r in ROTATIONS for c in r[1]}
    fault_data = {k: v for k, v in fault_data.items() if k in cars_in_scope}

    doc = Document()

    for section in doc.sections:
        section.page_width    = Cm(21)
        section.page_height   = Cm(29.7)
        section.left_margin   = Cm(1.5)
        section.right_margin  = Cm(1.5)
        section.top_margin    = Cm(1.5)
        section.bottom_margin = Cm(1.5)

    style = doc.styles["Normal"]
    style.font.name = "Microsoft JhengHei"
    style.font.size = Pt(8)
    style.paragraph_format.space_before = Pt(0)
    style.paragraph_format.space_after  = Pt(0)

    # Title
    label_en = "Active Fault Report" if active_only else "Daily Fault Report"
    label_zh = "未修復故障報告" if active_only else "故障日報"
    p = doc.add_paragraph(); no_space(p); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(f"DT&E {label_zh} {label_en}"); r.bold = True; r.font.size = Pt(18); r.font.color.rgb = NAVY

    p2 = doc.add_paragraph(); no_space(p2); p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r2 = p2.add_run(f"日期 Date：{TODAY}"); r2.font.size = Pt(10); r2.font.color.rgb = RGBColor(0x44,0x55,0x66)

    if active_only:
        p3 = doc.add_paragraph(); no_space(p3); p3.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r3 = p3.add_run("（僅含故障 / 維修中 / 待確認　Active faults only: Fault / Under Repair / Pending）")
        r3.italic = True; r3.font.size = Pt(8.5); r3.font.color.rgb = RGBColor(0x66,0x66,0x66)

    # Summary
    def count(st):
        return sum(1 for car in fault_data for f in fault_data[car] if f["status"]==st and (not active_only or st in ACTIVE_STATUSES))

    total_cars = sum(1 for car in [c for r in ROTATIONS for c in r[1]]
                     if car in fault_data and any(f["status"] in ACTIVE_STATUSES for f in fault_data[car]))  \
                 if active_only else \
                 sum(1 for car in [c for r in ROTATIONS for c in r[1]] if car in fault_data)

    cnt_fault = count("故障"); cnt_fixed = count("已修復完成")
    cnt_wip   = count("維修中"); cnt_pend  = count("待確認")

    sp = doc.add_paragraph(); no_space(sp)
    sr = sp.add_run("摘要 Summary"); sr.bold = True; sr.font.size = Pt(11); sr.font.color.rgb = NAVY

    TOTAL_CARS = sum(len(r[1]) for r in ROTATIONS)  # 57

    if active_only:
        SUM_COLS = [
            ("總車數\nTotal Cars",          str(TOTAL_CARS), "2C3E50"),
            ("有紀錄車廂\nCars w/ Records", str(total_cars), "1A2332"),
            ("故障\nFault",                 str(cnt_fault),  "C00000"),
            ("維修中\nUnder Repair",        str(cnt_wip),    "7B3F00"),
            ("待確認\nPending",             str(cnt_pend),   "1F497D"),
        ]
        stbl = doc.add_table(rows=2, cols=5)
    else:
        SUM_COLS = [
            ("總車數\nTotal Cars",          str(TOTAL_CARS), "2C3E50"),
            ("有紀錄車廂\nCars w/ Records", str(total_cars), "1A2332"),
            ("故障\nFault",                 str(cnt_fault),  "C00000"),
            ("已修復完成\nFixed",            str(cnt_fixed),  "0E7490"),
            ("維修中\nUnder Repair",        str(cnt_wip),    "7B3F00"),
            ("待確認\nPending",             str(cnt_pend),   "1F497D"),
        ]
        stbl = doc.add_table(rows=2, cols=6)
    set_table_fixed(stbl, [PAGE_W // len(SUM_COLS)] * len(SUM_COLS))
    stbl.alignment = WD_TABLE_ALIGNMENT.CENTER

    cw = PAGE_W // len(SUM_COLS)
    for i,(label,val,bg) in enumerate(SUM_COLS):
        hc = stbl.rows[0].cells[i]; set_cell_bg(hc, bg); set_cell_width(hc, cw)
        hc.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        hp = hc.paragraphs[0]; hp.alignment = WD_ALIGN_PARAGRAPH.CENTER; no_space(hp)
        hr = hp.add_run(label); hr.bold = True; hr.font.size = Pt(7.5); hr.font.color.rgb = WHITE

        vc = stbl.rows[1].cells[i]; set_cell_width(vc, cw)
        vc.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        vp = vc.paragraphs[0]; vp.alignment = WD_ALIGN_PARAGRAPH.CENTER; no_space(vp)
        vr = vp.add_run(val); vr.bold = True; vr.font.size = Pt(18); vr.font.color.rgb = NAVY

    doc.add_paragraph()

    # Rotations
    for rot_label, cars in ROTATIONS:
        # Rotation header
        rt = doc.add_table(rows=1, cols=1); set_table_fixed(rt, [PAGE_W])
        rc = rt.rows[0].cells[0]; set_cell_bg(rc, "1A2332"); set_cell_width(rc, PAGE_W)
        rp = rc.paragraphs[0]; rp.alignment = WD_ALIGN_PARAGRAPH.LEFT; no_space(rp)
        rr = rp.add_run(f"DT&E {rot_label} ｜ 車廂數 Cars：{len(cars)}")
        rr.bold = True; rr.font.size = Pt(11); rr.font.color.rgb = WHITE

        for car in cars:
            items = fault_data.get(car, [])
            if active_only:
                items = [f for f in items if f["status"] in ACTIVE_STATUSES]

            # Car header
            ct = doc.add_table(rows=1, cols=2); set_table_fixed(ct, [80, PAGE_W-80])
            bc = ct.rows[0].cells[0]; set_cell_bg(bc, "2D4A8A"); set_cell_width(bc, 80); no_space(bc.paragraphs[0])
            nc = ct.rows[0].cells[1]; set_cell_width(nc, PAGE_W-80)
            # Remove border on name cell
            tcPr = nc._tc.get_or_add_tcPr()
            tcB  = OxmlElement("w:tcBorders")
            for side in ("top","left","bottom","right"):
                b = OxmlElement(f"w:{side}"); b.set(qn("w:val"),"nil"); b.set(qn("w:sz"),"0"); b.set(qn("w:space"),"0"); b.set(qn("w:color"),"auto"); tcB.append(b)
            tcPr.append(tcB)
            np2 = nc.paragraphs[0]; no_space(np2)
            nr  = np2.add_run(f" {car}"); nr.bold = True; nr.font.size = Pt(11); nr.font.color.rgb = NAVY

            if not items:
                if not active_only:
                    p = doc.add_paragraph(); no_space(p)
                    r = p.add_run("  無故障紀錄 No fault records"); r.italic = True; r.font.size = Pt(8); r.font.color.rgb = GRAY
                # In active_only mode, skip cars with no active faults silently
                continue

            tbl = doc.add_table(rows=1+len(items), cols=6)
            tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
            set_table_fixed(tbl, COL_WIDTHS)

            hdrs = ["#","狀態\nStatus","故障描述 (中文)","Fault Description (English)","修復人員\nRepaired by","見證人\nWitness"]
            for j,h in enumerate(hdrs):
                c = tbl.rows[0].cells[j]; set_cell_bg(c,"2D4A8A"); set_cell_width(c,COL_WIDTHS[j])
                c.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
                p = c.paragraphs[0]; p.alignment = WD_ALIGN_PARAGRAPH.CENTER; no_space(p)
                r = p.add_run(h); r.bold = True; r.font.size = Pt(7.5); r.font.color.rgb = WHITE

            for idx,f in enumerate(items):
                row = tbl.rows[1+idx]
                bg  = STATUS_BG.get(f["status"],"FFFFFF")
                zh_st, en_st = STATUS_ZH_EN.get(f["status"],(f["status"],""))
                sc  = STATUS_COLOR.get(f["status"], NAVY)

                # # col
                c0 = row.cells[0]; set_cell_bg(c0,bg); set_cell_width(c0,C_NO)
                c0.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
                p0 = c0.paragraphs[0]; p0.alignment = WD_ALIGN_PARAGRAPH.CENTER; no_space(p0)
                r0 = p0.add_run(str(idx+1)); r0.font.size = Pt(8); r0.font.color.rgb = RGBColor(0x55,0x55,0x55)

                # Status col
                c1 = row.cells[1]; set_cell_bg(c1,bg); set_cell_width(c1,C_ST)
                c1.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
                p1 = c1.paragraphs[0]; p1.alignment = WD_ALIGN_PARAGRAPH.CENTER; no_space(p1)
                r1a = p1.add_run(zh_st); r1a.bold = True; r1a.font.size = Pt(8); r1a.font.color.rgb = sc
                r1a.add_break()
                r1b = p1.add_run(en_st); r1b.font.size = Pt(7); r1b.font.color.rgb = RGBColor(0x66,0x66,0x66)

                # ZH desc
                c2 = row.cells[2]; set_cell_bg(c2,bg); set_cell_width(c2,C_ZH)
                c2.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
                p2 = c2.paragraphs[0]; no_space(p2)
                r2 = p2.add_run(f["desc"]); r2.font.size = Pt(8); r2.font.color.rgb = NAVY

                # EN desc
                c3 = row.cells[3]; set_cell_bg(c3,bg); set_cell_width(c3,C_EN)
                c3.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
                p3 = c3.paragraphs[0]; no_space(p3)
                r3 = p3.add_run(translate(f["desc"])); r3.font.size = Pt(8); r3.font.color.rgb = NAVY

                # Person
                c4 = row.cells[4]; set_cell_bg(c4,bg); set_cell_width(c4,C_RP)
                c4.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
                p4 = c4.paragraphs[0]; p4.alignment = WD_ALIGN_PARAGRAPH.CENTER; no_space(p4)
                pt  = f["person"].strip()
                if pt:
                    rr4 = p4.add_run(pt); rr4.bold = True; rr4.font.size = Pt(8); rr4.font.color.rgb = TEAL
                else:
                    rr4 = p4.add_run("—"); rr4.font.size = Pt(8); rr4.font.color.rgb = GRAY

                # Witness
                c5 = row.cells[5]; set_cell_bg(c5,bg); set_cell_width(c5,C_WT)
                c5.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
                p5 = c5.paragraphs[0]; p5.alignment = WD_ALIGN_PARAGRAPH.CENTER; no_space(p5)
                wt  = f["witness"].strip()
                if wt:
                    rr5 = p5.add_run(wt); rr5.bold = True; rr5.font.size = Pt(8); rr5.font.color.rgb = BROWN
                else:
                    rr5 = p5.add_run("—"); rr5.font.size = Pt(8); rr5.font.color.rgb = GRAY

        doc.add_paragraph()

    # Footer
    fp = doc.add_paragraph(); fp.alignment = WD_ALIGN_PARAGRAPH.CENTER; no_space(fp)
    fr = fp.add_run(f"本報告由系統自動產生 / Auto-generated on {TODAY}")
    fr.italic = True; fr.font.size = Pt(7.5); fr.font.color.rgb = GRAY

    return doc

# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Fetching Firestore data...")
    fault_data = fetch_all()
    print(f"  Got data for {len(fault_data)} cars")

    # Check untranslated
    missing = set()
    for items in fault_data.values():
        for f in items:
            d = f["desc"].strip()
            if d and d not in ZH_EN:
                missing.add(d)
    if missing:
        print(f"  WARNING: {len(missing)} untranslated descriptions (will show original)")

    out1 = f"{SCRATCHPAD}/故障日報_{TODAY}.docx"
    build_doc(fault_data, active_only=False).save(out1)
    print(f"OK: {out1}")
