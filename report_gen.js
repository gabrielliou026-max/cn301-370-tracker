// ── 故障日報 Word 產生器（瀏覽器版）───────────────────────────────────────────
// 與 scripts/gen_word_report.py 的 build_doc() 對應：產出的 word/document.xml
// 需與 Python 版位元組一致（含 python-docx 重複 tblGrid/tcW 的輸出習慣，勿「修正」），
// 版型改動時兩邊必須同步修改，並重跑位元組比對驗證。
// 依賴：vendor/jszip.min.js、report_template.docx（模板部件）、zh_en.json（翻譯詞庫）

(function () {
  "use strict";

  // ── 與 Python 版同步的常數 ──
  const RG_STATUS_ORDER = { "均完成": -1, "已修復完成": 0, "故障": 1, "維修中": 2, "待確認": 3 };
  const RG_STATUS_ZH_EN = {
    "均完成":     ["均完成", "All Clear"],
    "故障":       ["故障", "Fault"],
    "已修復完成": ["已修復完成", "Fixed"],
    "維修中":     ["維修中", "Under Repair"],
    "待確認":     ["待確認", "Pending"],
  };
  const RG_STATUS_COLOR = { "均完成": "168A3E", "故障": "C00000", "已修復完成": "0E7490", "維修中": "7B3F00", "待確認": "1F497D" };
  const RG_STATUS_BG    = { "均完成": "F0FDF4", "故障": "FFF5F5", "已修復完成": "F0FDFC", "維修中": "FFFBF0", "待確認": "F5F7FF" };
  const NAVY = "1A2332";
  const COL_WIDTHS = [267, 889, 2312, 2934, 1156, 1156];
  const PAGE_W = 8714;
  const SUM_CW = Math.floor(PAGE_W / 6); // 1452

  const ROTATIONS_73G = [
    ["第一輪 1st Rotation", ["CN360","CN359","CN358","CN357","CN356","CN353","CN370","CN369","NMS382","NMS381","NMS383"]],
    ["第二輪 2nd Rotation", ["CN362","CN320","CN321","CN309","CN302","CN305","CN301","CN344","CN329","CN323","CN303","CN319","CN308","CN310","CN314"]],
    ["第三輪 3rd Rotation", ["CN324","CN337","CN327","CN347","CN326","CN346","CN361","CN355","CN342","CN311","CN330","CN341","CN348","CN354","CN331"]],
    ["第四輪 4th Rotation", ["CN343","CN345","CN312","CN339","CN340","CN336","CN307","CN313","CN364","CN322","CN325","CN306","CN338","CN304","CN363","CN328"]],
  ];

  // ── XML 工具（模仿 python-docx 的輸出行為）──
  function escX(s) {
    return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }
  // 前後有空白時 python-docx 會加 xml:space="preserve"
  function wt(t) {
    const pres = t !== t.trim() ? ' xml:space="preserve"' : "";
    return `<w:t${pres}>${escX(t)}</w:t>`;
  }
  // run 內文字：\n → <w:br/>；空字串不產生 <w:t>
  function runText(t) {
    return String(t).split("\n").map(seg => (seg ? wt(seg) : "")).join("<w:br/>");
  }

  const PREFIX = `<?xml version='1.0' encoding='UTF-8' standalone='yes'?>\n<w:document xmlns:wpc="http://schemas.microsoft.com/office/word/2010/wordprocessingCanvas" xmlns:mo="http://schemas.microsoft.com/office/mac/office/2008/main" xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" xmlns:mv="urn:schemas-microsoft-com:mac:vml" xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math" xmlns:v="urn:schemas-microsoft-com:vml" xmlns:wp14="http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing" xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" xmlns:w10="urn:schemas-microsoft-com:office:word" xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml" xmlns:wpg="http://schemas.microsoft.com/office/word/2010/wordprocessingGroup" xmlns:wpi="http://schemas.microsoft.com/office/word/2010/wordprocessingInk" xmlns:wne="http://schemas.microsoft.com/office/word/2006/wordml" xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape" mc:Ignorable="w14 wp14"><w:body>`;
  const SUFFIX = `<w:sectPr w:rsidR="00FC693F" w:rsidRPr="0006063C" w:rsidSect="00034616"><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="850" w:right="850" w:bottom="850" w:left="850" w:header="720" w:footer="720" w:gutter="0"/><w:cols w:space="720"/><w:docGrid w:linePitch="360"/></w:sectPr></w:body></w:document>`;

  // 段落：置中 / 靠左，含單一 run（jc 在 spacing 前 — 對應 add_run(align=...) 的呼叫順序）
  function para(runsXml, jc) {
    const jcXml = jc ? `<w:jc w:val="${jc}"/>` : "";
    return `<w:p><w:pPr>${jcXml}<w:spacing w:before="0" w:after="0"/></w:pPr>${runsXml}</w:p>`;
  }
  // 標題/日期段落：python 版先 no_space 再設 alignment，故 spacing 在 jc 前
  function paraSpacingFirst(runsXml, jc) {
    return `<w:p><w:pPr><w:spacing w:before="0" w:after="0"/><w:jc w:val="${jc}"/></w:pPr>${runsXml}</w:p>`;
  }
  function run(text, opts) {
    const o = opts || {};
    let rPr = "";
    if (o.b) rPr += "<w:b/>";
    if (o.i) rPr += "<w:i/>";
    if (o.color) rPr += `<w:color w:val="${o.color}"/>`;
    if (o.sz) rPr += `<w:sz w:val="${o.sz}"/>`;
    return `<w:r><w:rPr>${rPr}</w:rPr>${runText(text)}${o.brEnd ? "<w:br/>" : ""}</w:r>`;
  }

  // 表格外框（python-docx 產出：tblPr ＋ 兩組 tblGrid）
  // jcOrder: 0=無置中；1=jc 在 tblLook 前（先設 alignment 再 set_table_fixed，故障表）；
  //          2=jc 在 tblLook 後（先 set_table_fixed 再設 alignment，摘要表）
  function tbl(inner, widths, defaultW, jcOrder) {
    const jcXml = jcOrder ? `<w:jc w:val="center"/>` : "";
    const look = `<w:tblLook w:firstColumn="1" w:firstRow="1" w:lastColumn="0" w:lastRow="0" w:noHBand="0" w:noVBand="1" w:val="04A0"/>`;
    const gridReal = widths.map(w => `<w:gridCol w:w="${w}"/>`).join("");
    const gridDef  = widths.map(() => `<w:gridCol w:w="${defaultW}"/>`).join("");
    const total = widths.reduce((a, b) => a + b, 0);
    const mid = jcOrder === 1 ? jcXml + look : look + jcXml;
    return `<w:tbl><w:tblPr><w:tblW w:type="auto" w:w="0"/>${mid}` +
      `<w:tblLayout w:type="fixed"/><w:tblW w:w="${total}" w:type="dxa"/></w:tblPr>` +
      `<w:tblGrid>${gridReal}</w:tblGrid><w:tblGrid>${gridDef}</w:tblGrid>${inner}</w:tbl>`;
  }
  // 儲存格：tcPr = 預設 tcW ＋ shd(可選) ＋ 實際 tcW ＋ vAlign(可選) ＋ 額外
  function tc(pXml, defaultW, fill, realW, vCenter, extra) {
    let tcPr = `<w:tcW w:type="dxa" w:w="${defaultW}"/>`;
    if (fill) tcPr += `<w:shd w:val="clear" w:color="auto" w:fill="${fill}"/>`;
    tcPr += `<w:tcW w:w="${realW}" w:type="dxa"/>`;
    if (extra) tcPr += extra;
    if (vCenter) tcPr += `<w:vAlign w:val="center"/>`;
    return `<w:tc><w:tcPr>${tcPr}</w:tcPr>${pXml}</w:tc>`;
  }

  function translate(zh, zhEn) {
    const clean = String(zh).trim();
    return Object.prototype.hasOwnProperty.call(zhEn, clean) ? zhEn[clean] : clean;
  }

  // ── document.xml 組裝（對應 build_doc(active_only=False)）──
  const UNIT_TITLES = { "73G": "CN301-370", "74G": "CN501-546", "75G": "CN401-446" };

  function buildDocumentXml(rotations, faultData, zhEn, today, unitId) {
    const parts = [PREFIX];

    // 標題與日期
    parts.push(paraSpacingFirst(run("DT&E 故障日報 Daily Fault Report", { b: 1, color: NAVY, sz: 36 }), "center"));
    const unitTitle = UNIT_TITLES[unitId] || unitId;
    parts.push(paraSpacingFirst(run(`日期 Date：${today}　｜　作業單位 Unit：${unitId}（${unitTitle}）`, { color: "445566", sz: 20 }), "center"));

    // 摘要
    const scopeCars = rotations.flatMap(r => r[1]);
    const count = st => scopeCars.reduce((n, car) =>
      n + (faultData[car] || []).filter(f => f.status === st).length, 0);
    const totalCars = scopeCars.filter(car => faultData[car] && faultData[car].length).length;
    const TOTAL_CARS = scopeCars.length;

    parts.push(para(run("摘要 Summary", { b: 1, color: NAVY, sz: 22 })));

    const SUM_COLS = [
      ["總車數\nTotal Cars",          String(TOTAL_CARS),       "2C3E50"],
      ["有紀錄車廂\nCars w/ Records", String(totalCars),        "1A2332"],
      ["故障\nFault",                 String(count("故障")),     "C00000"],
      ["已修復完成\nFixed",            String(count("已修復完成")), "0E7490"],
      ["維修中\nUnder Repair",        String(count("維修中")),   "7B3F00"],
      ["待確認\nPending",             String(count("待確認")),   "1F497D"],
    ];
    const hdrRow = "<w:tr>" + SUM_COLS.map(([label, , bg]) =>
      tc(para(run(label, { b: 1, color: "FFFFFF", sz: 15 }), "center"), 1701, bg, SUM_CW, true)
    ).join("") + "</w:tr>";
    const valRow = "<w:tr>" + SUM_COLS.map(([, val]) =>
      tc(para(run(val, { b: 1, color: NAVY, sz: 36 }), "center"), 1701, null, SUM_CW, true)
    ).join("") + "</w:tr>";
    parts.push(tbl(hdrRow + valRow, Array(6).fill(SUM_CW), 1701, 2));
    parts.push("<w:p/>");

    // 輪次與車廂
    for (const [rotLabel, cars] of rotations) {
      const rp = para(run(`DT&E ${rotLabel} ｜ 車廂數 Cars：${cars.length}`, { b: 1, color: "FFFFFF", sz: 22 }), "left");
      parts.push(tbl("<w:tr>" + tc(rp, 10206, "1A2332", PAGE_W) + "</w:tr>", [PAGE_W], 10206, 0));

      for (const car of cars) {
        const items = faultData[car] || [];

        // 車廂標題（左側色條 + 車號；右格移除框線）
        const noBorders = '<w:tcBorders>' +
          ["top","left","bottom","right"].map(s => `<w:${s} w:val="nil" w:sz="0" w:space="0" w:color="auto"/>`).join("") +
          "</w:tcBorders>";
        const barCell  = tc(para(""), 5103, "2D4A8A", 80);
        const nameCell = tc(para(run(` ${car}`, { b: 1, color: NAVY, sz: 22 })), 5103, null, PAGE_W - 80, false, noBorders);
        parts.push(tbl("<w:tr>" + barCell + nameCell + "</w:tr>", [80, PAGE_W - 80], 5103, 0));

        if (!items.length) {
          parts.push(para(run("  無故障紀錄 No fault records", { i: 1, color: "AAAAAA", sz: 16 })));
          continue;
        }

        // 故障表
        const hdrs = ["#", "狀態\nStatus", "故障描述 (中文)", "Fault Description (English)", "修復人員\nRepaired by", "見證人\nWitness"];
        let rows = "<w:tr>" + hdrs.map((h, j) =>
          tc(para(run(h, { b: 1, color: "FFFFFF", sz: 15 }), "center"), 1701, "2D4A8A", COL_WIDTHS[j], true)
        ).join("") + "</w:tr>";

        items.forEach((f, idx) => {
          const bg = RG_STATUS_BG[f.status] || "FFFFFF";
          const [zhSt, enSt] = RG_STATUS_ZH_EN[f.status] || [f.status, ""];
          const sc = RG_STATUS_COLOR[f.status] || NAVY;
          const statusRuns = run(zhSt, { b: 1, color: sc, sz: 16, brEnd: 1 }) + run(enSt, { color: "666666", sz: 14 });
          const person = String(f.person || "").trim();
          const witness = String(f.witness || "").trim();
          rows += "<w:tr>" +
            tc(para(run(String(idx + 1), { color: "555555", sz: 16 }), "center"), 1701, bg, COL_WIDTHS[0], true) +
            tc(para(statusRuns, "center"), 1701, bg, COL_WIDTHS[1], true) +
            tc(para(run(f.desc || "", { color: NAVY, sz: 16 })), 1701, bg, COL_WIDTHS[2], true) +
            tc(para(run(f.desc_en || translate(f.desc || "", zhEn), { color: NAVY, sz: 16 })), 1701, bg, COL_WIDTHS[3], true) +
            tc(para(person ? run(person, { b: 1, color: "0E7490", sz: 16 }) : run("—", { color: "AAAAAA", sz: 16 }), "center"), 1701, bg, COL_WIDTHS[4], true) +
            tc(para(witness ? run(witness, { b: 1, color: "92400E", sz: 16 }) : run("—", { color: "AAAAAA", sz: 16 }), "center"), 1701, bg, COL_WIDTHS[5], true) +
            "</w:tr>";
        });
        parts.push(tbl(rows, COL_WIDTHS, 1701, 1));
      }
      parts.push("<w:p/>");
    }

    // 頁尾
    parts.push(para(run(`本報告由系統自動產生 / Auto-generated on ${today}`, { i: 1, color: "AAAAAA", sz: 15 }), "center"));
    parts.push(SUFFIX);
    return parts.join("");
  }

  // ── 對外主函式 ──
  let _tmplBuf = null, _zhEn = null;
  async function fetchOnce() {
    if (!_tmplBuf) {
      const r = await fetch("report_template.docx");
      if (!r.ok) throw new Error("無法載入報告模板");
      _tmplBuf = await r.arrayBuffer();
    }
    if (!_zhEn) {
      const r = await fetch("zh_en.json");
      if (!r.ok) throw new Error("無法載入翻譯詞庫");
      _zhEn = await r.json();
    }
  }

  // savedCloud → 報告資料（依報告排序：均完成→已修復→故障→維修中→待確認）
  function toFaultData(cars, savedCloud) {
    const out = {};
    cars.forEach(car => {
      const items = (savedCloud[car] || []).map(f => ({
        status: f.status || "待確認", desc: f.desc || "", desc_en: f.desc_en || "",
        person: f.person || "", witness: f.witness || "",
      }));
      if (items.length) {
        items.sort((a, b) => (RG_STATUS_ORDER[a.status] ?? 9) - (RG_STATUS_ORDER[b.status] ?? 9));
        out[car] = items;
      }
    });
    return out;
  }

  window.generateUnitReport = async function (unitId, cars, savedCloud) {
    await fetchOnce();
    const pad = n => String(n).padStart(2, "0");
    const now = new Date();
    const today = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;

    const rotations = unitId === "73G" ? ROTATIONS_73G : [["全部車輛 All Cars", cars]];
    const faultData = toFaultData(rotations.flatMap(r => r[1]), savedCloud);
    const xml = buildDocumentXml(rotations, faultData, _zhEn, today, unitId);

    const zip = await JSZip.loadAsync(_tmplBuf.slice(0));
    zip.file("word/document.xml", xml);
    const blob = await zip.generateAsync({
      type: "blob",
      compression: "DEFLATE",
      mimeType: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `故障日報_${unitId}_${today}.docx`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    // 延後釋放，避免下載尚未開始 URL 就失效
    setTimeout(() => URL.revokeObjectURL(a.href), 10000);

    // 未收錄翻譯提醒（與 Python 腳本的 WARNING 對應）；已有即時翻譯結果的不算未翻譯
    const missing = new Set();
    Object.values(faultData).forEach(items => items.forEach(f => {
      const d = (f.desc || "").trim();
      if (d && !f.desc_en && !Object.prototype.hasOwnProperty.call(_zhEn, d)) missing.add(d);
    }));
    return { missing: [...missing] };
  };

  // 驗證用掛鉤（位元組比對測試使用，網站不會呼叫）
  window.__rg = { buildDocumentXml, toFaultData, ROTATIONS_73G };
})();
