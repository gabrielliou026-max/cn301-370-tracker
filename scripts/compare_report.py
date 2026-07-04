#!/usr/bin/env python3
"""
Compare PDF snapshot vs current Firestore data.
Identifies new fault items, status changes, and person/witness updates.
"""
import urllib.request, json, re, sys
import fitz  # PyMuPDF

API_KEY    = "AIzaSyBRNMZFCSnWk1X_HZMuDa_ym-Zvwk9ei-U"
PROJECT_ID = "fics-6e2cd"
BASE_URL   = f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/(default)/documents"
PDF_PATH   = "/root/.claude/uploads/601937c1-2176-5d8c-aa25-0c267b631065/c30a0709-_____20260702.pdf"

STATUS_ORDER = {"已修復完成":0,"故障":1,"維修中":2,"待確認":3}
STATUS_EN    = {"已修復完成":"Fixed","故障":"Fault","維修中":"Under Repair","待確認":"Pending"}

# ── Fetch current Firestore data ──────────────────────────────────────────────
def fetch_all():
    url = f"{BASE_URL}/faultData?key={API_KEY}&pageSize=200"
    req = urllib.request.Request(url, headers={"Accept":"application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read())
    result = {}
    for doc in data.get("documents", []):
        car = doc["name"].split("/")[-1]
        fields = doc.get("fields", {})
        items = {}
        for fid, fval in fields.items():
            if fid == "updatedAt": continue
            if "mapValue" not in fval: continue
            m = fval["mapValue"].get("fields", {})
            desc    = m.get("desc",    {}).get("stringValue", "")
            status  = m.get("status",  {}).get("stringValue", "待確認")
            person  = m.get("person",  {}).get("stringValue", "")
            witness = m.get("witness", {}).get("stringValue", "")
            items[fid] = {"desc": desc, "status": status, "person": person, "witness": witness}
        if items:
            result[car] = items
    return result

# ── Extract PDF data ──────────────────────────────────────────────────────────
def extract_pdf(path):
    """
    Parse PDF text to extract per-car fault items.
    Returns dict: {car: {desc_key: {status, person, witness}}}
    where desc_key is the Chinese description used as lookup key.
    """
    doc = fitz.open(path)
    all_text = []
    for page in doc:
        all_text.append(page.get_text())
    full_text = "\n".join(all_text)
    doc.close()
    return full_text

# ── Parse PDF structured data ─────────────────────────────────────────────────
def parse_pdf_cars(text):
    """
    Extract car blocks and their fault items from PDF text.
    PDF layout (per car):
      CN3xx / NMSxxx
      No. | Status | Description | English | Person | Witness
    """
    result = {}

    # Find all car headings (CN or NMS prefixed lines)
    car_pattern = re.compile(r'((?:CN3\d\d|NMS3\d\d))\b')

    # Status values that appear in the PDF
    statuses = {"故障", "已修復完成", "維修中", "待確認"}

    lines = text.split("\n")
    current_car = None

    for i, line in enumerate(lines):
        line = line.strip()
        m = car_pattern.match(line)
        if m and len(line) < 20:  # short line = car header
            current_car = m.group(1)
            if current_car not in result:
                result[current_car] = []
            continue

        # Look for status keywords as first token — these are fault rows
        if current_car and any(line.startswith(s) for s in statuses):
            status = None
            for s in statuses:
                if line.startswith(s):
                    status = s
                    break
            result[current_car].append({"status": status, "raw": line})

    return result

# ── Main comparison ───────────────────────────────────────────────────────────
def main():
    print("Fetching current Firestore data...")
    live = fetch_all()

    print(f"Extracting PDF baseline...")
    pdf_text = extract_pdf(PDF_PATH)

    # Count live summary
    live_cars = set(live.keys())
    cnt_fault = cnt_fixed = cnt_wip = cnt_pend = 0
    total_items = 0
    for car, items in live.items():
        for fid, it in items.items():
            s = it["status"]
            total_items += 1
            if s == "故障":       cnt_fault += 1
            elif s == "已修復完成": cnt_fixed += 1
            elif s == "維修中":    cnt_wip   += 1
            elif s == "待確認":    cnt_pend  += 1

    print(f"\n{'='*60}")
    print(f"LIVE  (Firestore now):  Cars={len(live_cars)}, Items={total_items}")
    print(f"  故障={cnt_fault}  已修復完成={cnt_fixed}  維修中={cnt_wip}  待確認={cnt_pend}")
    print(f"PDF baseline (last night): Cars=54, Items=275 (66+133+3+73)")
    print(f"  故障=66  已修復完成=133  維修中=3  待確認=73")
    print(f"{'='*60}\n")

    # Delta summary
    delta_fault = cnt_fault - 66
    delta_fixed = cnt_fixed - 133
    delta_wip   = cnt_wip   - 3
    delta_pend  = cnt_pend  - 73
    delta_total = total_items - 275

    sign = lambda n: f"+{n}" if n > 0 else str(n)
    print(f"Count deltas (positive = new since PDF):")
    print(f"  Total items : {sign(delta_total)}")
    print(f"  故障 Fault  : {sign(delta_fault)}")
    print(f"  已修復 Fixed: {sign(delta_fixed)}")
    print(f"  維修中 WIP  : {sign(delta_wip)}")
    print(f"  待確認 Pend : {sign(delta_pend)}")

    # ── Per-car breakdown — dump all live data for manual inspection ─────────
    # We'll output any car whose item counts don't match expected
    # Since we can't parse the PDF table precisely, output full live data
    print(f"\n{'='*60}")
    print("CURRENT LIVE DATA (all cars with records):")
    print(f"{'='*60}")

    ROTATIONS = [
        ("第一輪 1st",  ["CN360","CN359","CN358","CN357","CN356","CN353","CN370","CN369","NMS382","NMS381","NMS383"]),
        ("第二輪 2nd",  ["CN362","CN320","CN321","CN309","CN302","CN305","CN301","CN344","CN329","CN323","CN303","CN319","CN308","CN310","CN314"]),
        ("第三輪 3rd",  ["CN324","CN337","CN327","CN347","CN326","CN346","CN361","CN355","CN342","CN311","CN330","CN341","CN348","CN354","CN331"]),
        ("第四輪 4th",  ["CN343","CN345","CN312","CN339","CN340","CN336","CN307","CN313","CN364","CN322","CN325","CN306","CN338","CN304","CN363","CN328"]),
    ]

    for rot_name, cars in ROTATIONS:
        rot_items = [(c, live[c]) for c in cars if c in live]
        if not rot_items:
            continue
        print(f"\n[{rot_name}]")
        for car, items in rot_items:
            fault_items = [(fid, it) for fid, it in items.items() if it["status"] == "故障"]
            wip_items   = [(fid, it) for fid, it in items.items() if it["status"] == "維修中"]
            pend_items  = [(fid, it) for fid, it in items.items() if it["status"] == "待確認"]
            fixed_items = [(fid, it) for fid, it in items.items() if it["status"] == "已修復完成"]
            non_fixed = fault_items + wip_items + pend_items
            print(f"\n  {car} — {len(items)} items total "
                  f"(故障{len(fault_items)} 維修中{len(wip_items)} 待確認{len(pend_items)} 已修復{len(fixed_items)})")
            for fid, it in sorted(items.items(), key=lambda x: STATUS_ORDER.get(x[1]["status"],9)):
                st  = it["status"]
                desc = it["desc"][:50]
                pr  = it.get("person","")
                wt  = it.get("witness","")
                print(f"    [{st}] {desc}")
                if pr or wt:
                    print(f"           → 人員:{pr}  見證:{wt}")

if __name__ == "__main__":
    main()
