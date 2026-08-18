// 建置腳本：把 main 分支的開發版原始碼（含中文開發註解、內部文件）
// 處理成「正式版」靜態網站，輸出到 dist/，由 GitHub Actions 部署。
//
// 開發時完全不用管這個檔案——正常改 index.html / domain.html / report_gen.js，
// push 到 main 後 GitHub Actions 會自動跑這支腳本、部署 dist/ 的內容。
//
// 這支腳本做兩件事：
//   1. 去除 index.html / domain.html / report_gen.js 裡的開發註解與多餘空白，
//      避免任何人「檢視原始碼」看到內部技術細節
//   2. 只把「網站真正需要的檔案」放進 dist/，scripts/（Python 腳本、交接文件）
//      與 worker/（Cloudflare Worker 原始碼）等內部維護用檔案完全不會被公開部署
//
// 新增檔案給網站用時，記得把檔名加進下面的 PASSTHROUGH 或 MINIFY_HTML/MINIFY_JS 清單。

import { minify as minifyHtml } from "html-minifier-terser";
import { minify as minifyJs } from "terser";
import { readFile, writeFile, mkdir, cp, rm } from "node:fs/promises";
import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const DIST = path.join(ROOT, "dist");

// 只去除註解與壓縮空白，不做變數改名（compress/mangle 關閉）——
// 保持行為完全等價，日後要在瀏覽器 devtools 除錯時也還讀得懂
const TERSER_OPTS = {
  compress: false,
  mangle: false,
  format: { comments: false },
};

// 需要去除註解、壓縮的 HTML（含內嵌 <script>）
const MINIFY_HTML = ["index.html", "domain.html"];
// 需要去除註解的獨立 JS
const MINIFY_JS = ["report_gen.js"];
// 原封不動複製的檔案／資料夾（網站執行需要，但沒有開發註解可去除）
const PASSTHROUGH = [
  "report_template.docx",
  "zh_en.json",
  "vendor",
  "rf.html",
  "fics.html",
];

async function buildHtml(name) {
  const src = await readFile(path.join(ROOT, name), "utf8");
  const out = await minifyHtml(src, {
    removeComments: true,
    collapseWhitespace: true,
    minifyJS: TERSER_OPTS,
    minifyCSS: true,
  });
  await writeFile(path.join(DIST, name), out);
  console.log(`  ${name}: ${src.length} → ${out.length} bytes`);
}

async function buildJs(name) {
  const src = await readFile(path.join(ROOT, name), "utf8");
  const result = await minifyJs(src, TERSER_OPTS);
  await writeFile(path.join(DIST, name), result.code);
  console.log(`  ${name}: ${src.length} → ${result.code.length} bytes`);
}

async function main() {
  if (existsSync(DIST)) await rm(DIST, { recursive: true });
  await mkdir(DIST, { recursive: true });

  console.log("處理 HTML（去除註解＋壓縮）：");
  for (const name of MINIFY_HTML) await buildHtml(name);

  console.log("處理 JS（去除註解）：");
  for (const name of MINIFY_JS) await buildJs(name);

  console.log("複製原始檔案：");
  for (const name of PASSTHROUGH) {
    const srcPath = path.join(ROOT, name);
    if (!existsSync(srcPath)) {
      console.log(`  ⚠️  跳過（不存在）：${name}`);
      continue;
    }
    await cp(srcPath, path.join(DIST, name), { recursive: true });
    console.log(`  ${name}`);
  }

  console.log(`\n完成，輸出於 ${DIST}`);
}

main().catch(err => {
  console.error("建置失敗：", err);
  process.exit(1);
});
