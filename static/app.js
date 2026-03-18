const state = {
  mongoItems: [],
  cacheItems: [],
  mongoSelectedId: null,
  cacheSelectedId: null,
  config: null,
};

const formatJson = (value) => JSON.stringify(value, null, 2);
const FALLBACK_TRACE = {
  request_type: "search",
  key: "-",
  source: "unavailable",
  cache_status: "error",
  latency_ms: 0,
  result_count: 0,
};

// 카테고리별 이모지 매핑
const CATEGORY_EMOJI = {
  digital: "📱",
  game: "🎮",
  furniture: "🛋️",
  outdoor: "⛺",
  home: "🏠",
  fashion: "👗",
  book: "📚",
  sports: "⚽",
  car: "🚗",
  beauty: "💄",
};

const DEFAULT_EMOJI = "🛍️";

function getCategoryEmoji(category) {
  if (!category) return DEFAULT_EMOJI;
  const lower = category.toLowerCase();
  for (const [key, emoji] of Object.entries(CATEGORY_EMOJI)) {
    if (lower.includes(key)) return emoji;
  }
  return DEFAULT_EMOJI;
}

function getStatusLabel(status) {
  if (!status) return null;
  const s = status.toLowerCase();
  if (s === "sold" || s === "판매완료") return { label: "판매완료", cls: "sold" };
  if (s === "reserved" || s === "예약중") return { label: "예약중", cls: "reserved" };
  return null;
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, options);
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || "Request failed");
  }
  return payload;
}

function listingCard(item, selectedId, lane) {
  const isSelected = item.listing_id === selectedId ? "selected" : "";
  const emoji = getCategoryEmoji(item.category);
  const statusInfo = getStatusLabel(item.status);
  const statusBadge = statusInfo
    ? `<span class="jn-card-status-badge ${statusInfo.cls}">${statusInfo.label}</span>`
    : "";

  return `
    <button class="jn-card ${isSelected}" data-lane="${lane}" data-id="${item.listing_id}">
      <div class="jn-card-img">
        <span>${emoji}</span>
        ${statusBadge}
      </div>
      <div class="jn-card-body">
        <p class="jn-card-title">${item.title}</p>
        <p class="jn-card-price">${Number(item.price).toLocaleString()}원</p>
        <div class="jn-card-footer">
          <span class="jn-card-location">📍 ${item.location}</span>
          <span class="jn-card-likes">❤️ ${item.likes}</span>
        </div>
      </div>
    </button>
  `;
}

function renderListings(targetId, items, selectedId, lane) {
  const root = document.getElementById(targetId);
  if (!items.length) {
    root.innerHTML = `<div class="jn-empty">조건에 맞는 매물이 없습니다.</div>`;
    return;
  }
  root.innerHTML = items.map((item) => listingCard(item, selectedId, lane)).join("");
}

function renderLaneError(lane, message) {
  const ids = getLaneIds(lane);
  document.getElementById(ids.listings).innerHTML = `<div class="jn-error-state">${message}</div>`;
  document.getElementById(ids.detail).className = "jn-detail-panel";
  document.getElementById(ids.detail).innerHTML = `<div style="color:#c62828;font-weight:600;">${message}</div>`;
  document.getElementById(ids.trace).innerHTML = `<div style="color:#c62828;font-weight:600;">${message}</div>`;
  document.getElementById(ids.metrics).innerHTML = "";
  document.getElementById(ids.count).textContent = "오류";
  document.getElementById(ids.latency).textContent = "-";
}

function getLaneIds(lane) {
  const prefix = lane === "mongo" ? "mongo" : "cache";
  return {
    listings: `${prefix}-listings`,
    detail: `${prefix}-detail`,
    trace: `${prefix}-trace`,
    metrics: `${prefix}-metrics`,
    count: `${prefix}-result-count`,
    latency: `${prefix}-headline-latency`,
    cacheStatus: `${prefix}-cache-status`,
  };
}

function detailMarkup(listing, trace) {
  if (!listing) return "상품을 선택하면 상세 정보가 표시됩니다.";
  const emoji = getCategoryEmoji(listing.category);
  return `
    <div class="jn-detail-header">
      <div>
        <p class="jn-detail-eyebrow">${emoji} ${listing.category || "기타"}</p>
        <h3 class="jn-detail-title">${listing.title}</h3>
      </div>
      <span class="jn-detail-price">${Number(listing.price).toLocaleString()}원</span>
    </div>
    <p class="jn-detail-desc">${listing.description}</p>
    <div class="jn-detail-grid">
      <div class="jn-detail-item"><span>지역</span><strong>${listing.location}</strong></div>
      <div class="jn-detail-item"><span>카테고리</span><strong>${listing.category}</strong></div>
      <div class="jn-detail-item"><span>상태</span><strong>${listing.status || "-"}</strong></div>
      <div class="jn-detail-item"><span>판매자</span><strong>${listing.seller?.nickname || "-"}</strong></div>
      <div class="jn-detail-item"><span>응답률</span><strong>${listing.seller?.response_rate || "-"}</strong></div>
      <div class="jn-detail-item"><span>찜 / 조회</span><strong>❤️ ${listing.likes}  👁️ ${listing.views}</strong></div>
    </div>
    <div class="jn-detail-trace">
      <span>🔑 ${trace.key}</span>
      <span>📦 ${trace.source}</span>
      <span>${getCacheStatusLabel(trace.cache_status)}</span>
      <span>⚡ ${trace.latency_ms} ms</span>
    </div>
  `;
}

function getCacheStatusLabel(status) {
  if (!status) return "-";
  const map = {
    hit: "✅ 캐시 HIT",
    "miss-fill": "🟡 캐시 MISS → 채움",
    bypass: "🔵 캐시 우회 (Direct)",
    miss: "❌ 캐시 MISS",
    error: "⚠️ 오류",
  };
  return map[status] || status;
}

function renderTrace(targetId, trace) {
  document.getElementById(targetId).innerHTML = `
    <div class="jn-trace-grid">
      <div><span>Request Type</span><strong>${trace.request_type}</strong></div>
      <div><span>Key</span><strong style="font-size:11px;word-break:break-all;">${trace.key}</strong></div>
      <div><span>Source</span><strong>${trace.source}</strong></div>
      <div><span>Cache Status</span><strong>${getCacheStatusLabel(trace.cache_status)}</strong></div>
      <div><span>Latency</span><strong>${trace.latency_ms} ms</strong></div>
      <div><span>Result Count</span><strong>${trace.result_count}</strong></div>
    </div>
  `;
}

function renderLaneMetrics(targetId, trace, items) {
  const metrics = [
    ["응답시간", `${trace.latency_ms} ms`],
    ["결과 수", items.length],
    ["소스", trace.source.split("-")[0]],
    ["캐시", trace.cache_status],
  ];
  document.getElementById(targetId).innerHTML = metrics
    .map(
      ([label, value]) => `
      <div class="jn-mini-metric"><span>${label}</span><strong>${value}</strong></div>
    `,
    )
    .join("");
}

function renderGlobalMetrics(payload) {
  const grid = document.getElementById("metrics-grid");
  const metrics = [
    ["요청 수", payload.request_count],
    ["오류", payload.error_count],
    ["Hit 비율", payload.cache_hit_ratio],
    ["Req/sec", payload.requests_per_sec],
    ["평균 응답", `${payload.avg_latency_ms} ms`],
    ["RSS", `${payload.rss_used_memory_kb} KB`],
    ["연결 수", payload.active_connections],
    ["CPU", `${payload.cpu_percent}%`],
    ["TX", `${payload.network_tx_bytes} B`],
    ["RX", `${payload.network_rx_bytes} B`],
  ];
  grid.innerHTML = metrics
    .map(
      ([label, value]) => `
      <div class="jn-global-metric"><span>${label}</span><strong>${value}</strong></div>
    `,
    )
    .join("");
}

function renderHistory(history) {
  const container = document.getElementById("history-table");
  if (!history.length) {
    container.textContent = "아직 수집된 스냅샷이 없습니다.";
    return;
  }
  const rows = history
    .slice()
    .reverse()
    .map(
      (row) => `
        <tr>
          <td>${new Date(row.timestamp * 1000).toLocaleTimeString()}</td>
          <td>${row.requests_per_sec}</td>
          <td>${row.avg_latency_ms} ms</td>
          <td>${row.cache_hit_ratio}</td>
          <td>${row.error_count}</td>
        </tr>
      `,
    )
    .join("");
  container.innerHTML = `
    <div class="jn-table-wrap">
      <table class="jn-table">
        <thead>
          <tr>
            <th>시간</th>
            <th>Req/sec</th>
            <th>평균 응답</th>
            <th>Hit 비율</th>
            <th>오류</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
  `;
}

function renderComparisonSummary(mongoTrace, cacheTrace) {
  const speedup =
    cacheTrace.latency_ms > 0 ? (mongoTrace.latency_ms / cacheTrace.latency_ms).toFixed(2) : "-";
  const fasterText = speedup !== "-" ? `${speedup}x 빠름` : "-";

  document.getElementById("comparison-summary").innerHTML = `
    <div class="jn-compare-bar">
      <div class="jn-compare-item">
        <span class="jn-compare-label">🗄️ MongoDB Direct</span>
        <strong class="jn-compare-value db">${mongoTrace.latency_ms} ms</strong>
      </div>
      <div class="jn-compare-divider"></div>
      <div class="jn-compare-item">
        <span class="jn-compare-label">⚡ Mini Redis</span>
        <strong class="jn-compare-value redis">${cacheTrace.latency_ms} ms</strong>
      </div>
      <div class="jn-compare-divider"></div>
      <div class="jn-compare-item">
        <span class="jn-compare-label">캐시 상태</span>
        <strong class="jn-compare-value">${getCacheStatusLabel(cacheTrace.cache_status)}</strong>
      </div>
      <span class="jn-speedup-badge">🚀 ${fasterText}</span>
    </div>
  `;
  document.getElementById("mongo-headline-latency").textContent = `${mongoTrace.latency_ms} ms`;
  document.getElementById("cache-headline-latency").textContent = `${cacheTrace.latency_ms} ms`;

  // 캐시 상태 배지 업데이트
  updateCacheStatusBadge("mongo-cache-status", mongoTrace.cache_status);
  updateCacheStatusBadge("cache-cache-status", cacheTrace.cache_status);
}

function updateCacheStatusBadge(elementId, status) {
  const el = document.getElementById(elementId);
  if (!el) return;
  const map = {
    hit: { text: "CACHE HIT", cls: "hit" },
    "miss-fill": { text: "CACHE MISS", cls: "miss" },
    bypass: { text: "BYPASS", cls: "bypass" },
    miss: { text: "MISS", cls: "miss" },
  };
  const info = map[status] || { text: status, cls: "" };
  el.textContent = info.text;
  el.className = `jn-toolbar-cache ${info.cls}`;
}

function renderBenchmark(payload) {
  const cards = [
    ["🗄️ MongoDB Direct", payload.direct],
    ["⚡ Mini Redis Cache", payload.cache],
  ];
  document.getElementById("benchmark-cards").innerHTML = `
    <div class="jn-benchmark-meta">
      <span>Warm-up miss ${payload.warmup_miss_ms} ms</span>
      <span>반복 ${payload.iterations}회</span>
      <span>🚀 Speedup ${payload.speedup ?? "-"}x</span>
      <span>📁 ${payload.artifact_path}</span>
    </div>
    ${cards
      .map(
        ([label, metric]) => `
          <div class="jn-benchmark-card">
            <h4>${label}</h4>
            <p>평균 <strong>${metric.avg_ms} ms</strong></p>
            <p>최소 <strong>${metric.min_ms} ms</strong></p>
            <p>최대 <strong>${metric.max_ms} ms</strong></p>
            <p>P95 <strong>${metric.p95_ms} ms</strong></p>
            <p>Req/sec <strong>${metric.requests_per_sec}</strong></p>
          </div>
        `,
      )
      .join("")}
  `;
}

function renderQa(payload) {
  const total = payload.summary.total;
  const passed = payload.summary.passed;
  const failed = payload.summary.failed;
  const pct = total > 0 ? Math.round((passed / total) * 100) : 0;

  document.getElementById("qa-summary").innerHTML = `
    총 <strong>${total}</strong>건 중 <strong style="color:var(--jn-redis)">${passed}건 통과</strong>
    / <strong style="color:#c62828">${failed}건 실패</strong>
    &nbsp;(통과율 ${pct}%)
  `;
  document.getElementById("qa-results").innerHTML = payload.results
    .map(
      (result) => `
        <tr>
          <td>${result.scenario}</td>
          <td><span class="jn-qa-status ${result.status}">${result.status === "pass" ? "PASS" : "FAIL"}</span></td>
          <td>${result.latency_ms} ms</td>
          <td><code>${formatJson(result.expected)}</code></td>
          <td><code>${formatJson(result.actual)}</code></td>
          <td>${result.failure_reason || "-"}</td>
        </tr>
      `,
    )
    .join("");
}

async function refreshMetrics() {
  const [current, history] = await Promise.all([
    requestJson("/api/metrics/current"),
    requestJson("/api/metrics/history"),
  ]);
  renderGlobalMetrics(current);
  renderHistory(history.history);
}

async function loadListingDetail(lane, listingId) {
  const source = lane === "mongo" ? "mongo" : "cache";
  const payload = await requestJson("/api/market/listing", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ listing_id: listingId, source }),
  });
  const ids = getLaneIds(lane);
  document.getElementById(ids.detail).className = "jn-detail-panel";
  document.getElementById(ids.detail).innerHTML = detailMarkup(payload.listing, payload.trace);
  renderTrace(ids.trace, payload.trace);
  await refreshMetrics();
}

function buildSearchRequest(source, body) {
  return requestJson("/api/market/search", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...body, source }),
  });
}

function updateLaneFromSearch(lane, payload) {
  const selectedId = payload.items[0]?.listing_id ?? null;
  if (lane === "mongo") {
    state.mongoItems = payload.items;
    state.mongoSelectedId = selectedId;
  } else {
    state.cacheItems = payload.items;
    state.cacheSelectedId = selectedId;
  }
  const ids = getLaneIds(lane);
  renderListings(ids.listings, payload.items, selectedId, lane);
  renderTrace(ids.trace, payload.trace);
  renderLaneMetrics(ids.metrics, payload.trace, payload.items);
  document.getElementById(ids.count).textContent = `${payload.items.length}개 상품`;
  return selectedId;
}

async function runComparison() {
  const query = document.getElementById("search-query").value;
  const location = document.getElementById("search-location").value;
  const category = document.getElementById("search-category").value;
  const body = { query, location, category, limit: 12 };
  const [mongoResult, cacheResult] = await Promise.allSettled([
    buildSearchRequest("mongo", body),
    buildSearchRequest("cache", body),
  ]);

  const mongoTrace = mongoResult.status === "fulfilled" ? mongoResult.value.trace : FALLBACK_TRACE;
  const cacheTrace =
    cacheResult.status === "fulfilled"
      ? cacheResult.value.trace
      : { ...FALLBACK_TRACE, source: "cache-unavailable", key: "market:search:error" };

  if (mongoResult.status === "fulfilled") {
    const selectedId = updateLaneFromSearch("mongo", mongoResult.value);
    if (selectedId) await loadListingDetail("mongo", selectedId);
  } else {
    state.mongoItems = [];
    state.mongoSelectedId = null;
    renderLaneError("mongo", mongoResult.reason.message);
  }

  if (cacheResult.status === "fulfilled") {
    const selectedId = updateLaneFromSearch("cache", cacheResult.value);
    if (selectedId) await loadListingDetail("cache", selectedId);
  } else {
    state.cacheItems = [];
    state.cacheSelectedId = null;
    renderLaneError("cache", cacheResult.reason.message);
  }

  renderComparisonSummary(mongoTrace, cacheTrace);
  await refreshMetrics();
}

async function runBenchmark() {
  const payload = await requestJson("/api/market/compare", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      query: document.getElementById("search-query").value,
      location: document.getElementById("search-location").value,
      category: document.getElementById("search-category").value,
      limit: 12,
      iterations: Number(document.getElementById("iterations").value),
    }),
  });
  renderBenchmark(payload);
  await refreshMetrics();
}

async function runRedisCommand() {
  const payload = await requestJson("/api/redis/command", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      command: document.getElementById("redis-command").value,
      key: document.getElementById("redis-key").value,
      value: document.getElementById("redis-value").value || null,
      ttl_seconds: document.getElementById("redis-ttl").value || null,
    }),
  });
  document.getElementById("redis-command-result").textContent = formatJson(payload);
  await refreshMetrics();
}

function wireListingSelection() {
  document.body.addEventListener("click", async (event) => {
    const card = event.target.closest(".jn-card");
    if (!card) return;
    const lane = card.dataset.lane;
    const listingId = Number(card.dataset.id);
    if (lane === "mongo") {
      state.mongoSelectedId = listingId;
      renderListings("mongo-listings", state.mongoItems, state.mongoSelectedId, "mongo");
    } else {
      state.cacheSelectedId = listingId;
      renderListings("cache-listings", state.cacheItems, state.cacheSelectedId, "cache");
    }
    await loadListingDetail(lane, listingId);
  });
}

function wirePresetKeys() {
  document.querySelectorAll(".preset-key").forEach((button) => {
    button.addEventListener("click", () => {
      document.getElementById("redis-key").value = button.dataset.key;
    });
  });
}

async function bootstrap() {
  const config = await requestJson("/api/config");
  state.config = config;
  document.getElementById("redis-backend").textContent = config.redis_backend;
  document.getElementById("api-target").textContent = config.api_target || "local";
  document.getElementById("iterations").value = config.default_iterations;
  document.getElementById("search-query").value = "아이폰";
  document.getElementById("search-location").innerHTML = config.locations
    .map((item) => `<option value="${item}">${item}</option>`)
    .join("");
  document.getElementById("search-category").innerHTML = config.categories
    .map((item) => `<option value="${item}">${item}</option>`)
    .join("");
  document.getElementById("search-location").value = "성남시 분당구";
  document.getElementById("search-category").value = "digital";
  document.getElementById("redis-key").value = "market:listing:1001";
  wireListingSelection();
  wirePresetKeys();
  await runComparison();
  await refreshMetrics();
}

document.getElementById("run-comparison").addEventListener("click", runComparison);
document.getElementById("run-benchmark").addEventListener("click", runBenchmark);
document.getElementById("run-qa").addEventListener("click", async () => {
  const payload = await requestJson("/api/qa/run", { method: "POST" });
  renderQa(payload);
  await refreshMetrics();
});
document.getElementById("run-redis-command").addEventListener("click", runRedisCommand);
document.getElementById("refresh-metrics").addEventListener("click", refreshMetrics);

bootstrap().catch((error) => {
  document.body.insertAdjacentHTML(
    "afterbegin",
    `<div class="jn-error-banner"><div class="jn-error-banner-inner">초기화 실패: ${error.message}</div></div>`,
  );
});
