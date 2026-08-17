/**
 * translate-worker.js
 * ────────────────────────────────────────────────────────────────
 * CN301-370 故障追蹤系統 — 即時翻譯代理 (Cloudflare Worker)
 *
 * 用途：網站存檔後，對「詞庫（zh_en.json）沒收錄」的新故障描述呼叫本 Worker，
 * 由本 Worker 代為呼叫 Google Cloud Translation API 並回傳英文。
 * Google API 金鑰只存在 Worker 的加密環境變數（Secret）裡，絕不暴露給瀏覽器。
 *
 * 部署方式：Cloudflare Dashboard → Workers & Pages → Create → 貼上本檔內容 → Deploy
 * 需要設定的 Secret（Settings → Variables and Secrets → Add）：
 *   GOOGLE_TRANSLATE_API_KEY = <你在 Google Cloud 建立、限制為 Cloud Translation API 的金鑰>
 *   SITE_SHARED_SECRET       = <任意一串你自訂的亂數字串，例如用密碼產生器產生>
 *                               （前端 index.html 呼叫時要帶同一組值，作為基本防護，
 *                                避免這個公開網址被隨意濫用；非銀行等級安全機制，
 *                                但足以擋掉自動掃描與隨手亂打）
 *
 * 部署後請把 Worker 網址（形如 https://xxx.<你的帳號>.workers.dev）
 * 和你設定的 SITE_SHARED_SECRET 告訴接手的 AI，用於串接 index.html。
 *
 * ── 每日翻譯字元上限（防濫用，2026-08-17 新增）───────────────────────
 * SITE_SHARED_SECRET 會被前端公開程式碼帶出去，不是真正保密的機制
 * （CORS 只擋瀏覽器跨網域請求，擋不住有人直接用程式呼叫這個網址）。
 * 為了防止有人抓到網址+密鑰後拿去大量翻譯（例如整篇論文），加一道
 * 「不管誰呼叫、一天翻譯總字元數超過上限就全部拒絕」的硬性防線，
 * 需要額外綁定一個 Cloudflare KV 命名空間：
 *   Cloudflare Dashboard → Workers & Pages → 左側「Storage & Databases」
 *   → KV → Create namespace（取名如 fics-translate-usage）
 *   → 回到這個 Worker → Settings → Bindings → Add → KV Namespace
 *   → Variable name 填 USAGE_KV，選剛建立的命名空間 → Deploy
 * 未綁定 KV 時此限制不生效（向下相容，但強烈建議設定）。
 */

// 只允許從故障追蹤網站呼叫（依你的 GitHub Pages 網址調整）
const ALLOWED_ORIGIN = "https://gabrielliou026-max.github.io";

const MAX_TEXTS = 30;         // 單次請求最多幾筆，避免異常請求拉爆用量
const MAX_CHARS = 500;        // 單筆文字最多字元數
const DAILY_CHAR_CAP = 20000; // 每日翻譯字元總量上限（遠高於正常用量，但足以擋住整篇文件翻譯）

export default {
  async fetch(request, env) {
    if (request.method === "OPTIONS") {
      return new Response(null, { headers: corsHeaders() });
    }
    if (request.method !== "POST") {
      return json({ error: "method not allowed" }, 405);
    }

    // 基本防護：需帶正確的共用密鑰（見檔頭說明）
    const secret = request.headers.get("X-Site-Key") || "";
    if (!env.SITE_SHARED_SECRET || secret !== env.SITE_SHARED_SECRET) {
      return json({ error: "unauthorized" }, 401);
    }

    let body;
    try {
      body = await request.json();
    } catch {
      return json({ error: "invalid json" }, 400);
    }

    const texts = Array.isArray(body.texts)
      ? body.texts.filter(t => typeof t === "string" && t.trim().length > 0)
      : [];
    if (texts.length === 0) return json({ error: "no texts" }, 400);
    if (texts.length > MAX_TEXTS) return json({ error: `too many texts (max ${MAX_TEXTS})` }, 400);
    if (texts.some(t => t.length > MAX_CHARS)) return json({ error: `text too long (max ${MAX_CHARS} chars)` }, 400);

    if (!env.GOOGLE_TRANSLATE_API_KEY) {
      return json({ error: "server not configured" }, 500);
    }

    const totalChars = texts.reduce((sum, t) => sum + t.length, 0);
    const withinQuota = await checkAndConsumeQuota(env, totalChars);
    if (!withinQuota) {
      return json({ error: "daily quota exceeded" }, 429);
    }

    const gUrl = `https://translation.googleapis.com/language/translate/v2?key=${env.GOOGLE_TRANSLATE_API_KEY}`;
    let gRes;
    try {
      gRes = await fetch(gUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ q: texts, source: "zh-TW", target: "en", format: "text" }),
      });
    } catch (e) {
      return json({ error: "upstream request failed" }, 502);
    }

    if (!gRes.ok) {
      const detail = await gRes.text();
      return json({ error: "translation failed", detail: detail.slice(0, 300) }, 502);
    }

    const gData = await gRes.json();
    const translations = ((gData.data && gData.data.translations) || []).map(t => t.translatedText);
    if (translations.length !== texts.length) {
      return json({ error: "translation count mismatch" }, 502);
    }

    return json({ translations }, 200);
  },
};

// 每日字元配額檢查＋扣除（用 KV 儲存當天累計字元數，key 依日期自然輪替）
// 未綁定 USAGE_KV 時直接放行（向下相容）；KV 為最終一致性，短時間內
// 高併發可能有些微誤差，但作為防濫用防線已足夠，不追求絕對精確。
async function checkAndConsumeQuota(env, chars) {
  if (!env.USAGE_KV) return true;
  const key = "usage:" + new Date().toISOString().slice(0, 10); // usage:YYYY-MM-DD
  const current = parseInt(await env.USAGE_KV.get(key)) || 0;
  if (current + chars > DAILY_CHAR_CAP) return false;
  // 2 天後自動過期，key 不會無限累積
  await env.USAGE_KV.put(key, String(current + chars), { expirationTtl: 172800 });
  return true;
}

function corsHeaders() {
  return {
    "Access-Control-Allow-Origin": ALLOWED_ORIGIN,
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, X-Site-Key",
  };
}

function json(obj, status) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { "Content-Type": "application/json", ...corsHeaders() },
  });
}
