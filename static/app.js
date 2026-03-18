const state = {
  config: null,
  runs: {
    mongo: null,
    cache: null,
  },
};

const LANE_META = {
  mongo: {
    source: "mongo",
    laneId: "mongo-lane",
    stateId: "mongo-state",
    clientLatencyId: "mongo-client-latency",
    serverLatencyId: "mongo-server-latency",
    resultCountId: "mongo-result-count",
    cacheStatusId: "mongo-cache-status",
    traceId: "mongo-trace",
    resultsId: "mongo-results",
    progressId: "mongo-progress",
    label: "MongoDB Direct",
  },
  cache: {
    source: "cache",
    laneId: "cache-lane",
    stateId: "cache-state",
    clientLatencyId: "cache-client-latency",
    serverLatencyId: "cache-server-latency",
    resultCountId: "cache-result-count",
    cacheStatusId: "cache-cache-status",
    traceId: "cache-trace",
    resultsId: "cache-results",
    progressId: "cache-progress",
    label: "Mini Redis Cache",
  },
};

async function requestJson(url, options = {}) {
  const response = await fetch(url, options);
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || "Request failed");
  }
  return payload;
}

function setText(id, value) {
  document.getElementById(id).textContent = value;
}

function setStatus(message) {
  document.getElementById("duel-status").textContent = message;
}

function renderMetrics(payload) {
  const cards = [
    ["request", payload.request_count],
    ["error", payload.error_count],
    ["hit ratio", payload.cache_hit_ratio],
    ["req/sec", payload.requests_per_sec],
    ["avg latency", `${payload.avg_latency_ms} ms`],
    ["cpu", `${payload.cpu_percent}%`],
    ["tx", `${payload.network_tx_bytes} B`],
    ["rx", `${payload.network_rx_bytes} B`],
  ];
  document.getElementById("metrics-grid").innerHTML = cards
    .map(
      ([label, value]) => `
        <div class="metric-card">
          <span>${label}</span>
          <strong>${value}</strong>
        </div>
      `,
    )
    .join("");
}

function renderTrace(trace) {
  return `
    <div class="trace-grid">
      <div><span>request</span><strong>${trace.request_type ?? "-"}</strong></div>
      <div><span>key</span><strong>${trace.key ?? "-"}</strong></div>
      <div><span>source</span><strong>${trace.source ?? "-"}</strong></div>
      <div><span>cache</span><strong>${trace.cache_status ?? "-"}</strong></div>
      <div><span>server</span><strong>${trace.latency_ms ?? "-"} ms</strong></div>
      <div><span>count</span><strong>${trace.result_count ?? 0}</strong></div>
    </div>
  `;
}

function renderItems(items) {
  if (!items.length) {
    return '<div class="empty-state">조건에 맞는 결과가 없습니다.</div>';
  }
  return items
    .slice(0, 6)
    .map(
      (item, index) => `
        <article class="result-card">
          <div class="result-rank">#${index + 1}</div>
          <div class="result-copy">
            <h3>${item.title}</h3>
            <p>${item.location} · ${item.category}</p>
          </div>
          <strong>${Number(item.price).toLocaleString()}원</strong>
        </article>
      `,
    )
    .join("");
}

function resetLane(lane) {
  const meta = LANE_META[lane];
  const laneEl = document.getElementById(meta.laneId);
  laneEl.classList.remove("is-winner", "is-loser", "is-error");
  setText(meta.stateId, "READY");
  setText(meta.clientLatencyId, "-");
  setText(meta.serverLatencyId, "-");
  setText(meta.resultCountId, "-");
  setText(meta.cacheStatusId, lane === "mongo" ? "bypass" : "-");
  document.getElementById(meta.traceId).innerHTML = "요청 준비 중입니다.";
  document.getElementById(meta.resultsId).innerHTML = '<div class="empty-state">동시 실행 대기 중...</div>';
  document.getElementById(meta.progressId).style.width = "0%";
}

function markLanePending(lane) {
  const meta = LANE_META[lane];
  setText(meta.stateId, "RUNNING");
  document.getElementById(meta.progressId).style.width = "18%";
}

function renderLaneSuccess(lane, payload, clientLatencyMs) {
  const meta = LANE_META[lane];
  const trace = payload.trace || {};
  state.runs[lane] = {
    clientLatencyMs,
    serverLatencyMs: Number(trace.latency_ms || 0),
    trace,
    items: payload.items || [],
  };
  setText(meta.stateId, "DONE");
  setText(meta.clientLatencyId, `${clientLatencyMs.toFixed(1)} ms`);
  setText(meta.serverLatencyId, `${Number(trace.latency_ms || 0).toFixed(1)} ms`);
  setText(meta.resultCountId, String((payload.items || []).length));
  setText(meta.cacheStatusId, trace.cache_status || "-");
  document.getElementById(meta.traceId).innerHTML = renderTrace(trace);
  document.getElementById(meta.resultsId).innerHTML = renderItems(payload.items || []);
  document.getElementById(meta.progressId).style.width = "100%";
}

function renderLaneError(lane, error) {
  const meta = LANE_META[lane];
  const laneEl = document.getElementById(meta.laneId);
  laneEl.classList.add("is-error");
  setText(meta.stateId, "ERROR");
  document.getElementById(meta.traceId).textContent = error.message;
  document.getElementById(meta.resultsId).innerHTML = `<div class="empty-state">${error.message}</div>`;
  document.getElementById(meta.progressId).style.width = "100%";
}

function updateWinner() {
  const mongo = state.runs.mongo;
  const cache = state.runs.cache;
  const mongoLane = document.getElementById(LANE_META.mongo.laneId);
  const cacheLane = document.getElementById(LANE_META.cache.laneId);

  mongoLane.classList.remove("is-winner", "is-loser");
  cacheLane.classList.remove("is-winner", "is-loser");

  if (!mongo || !cache) {
    return;
  }

  const mongoTime = mongo.serverLatencyMs;
  const cacheTime = cache.serverLatencyMs;
  const winner = mongoTime <= cacheTime ? "mongo" : "cache";
  const loser = winner === "mongo" ? "cache" : "mongo";
  const delta = Math.abs(mongoTime - cacheTime).toFixed(1);

  document.getElementById(LANE_META[winner].laneId).classList.add("is-winner");
  document.getElementById(LANE_META[loser].laneId).classList.add("is-loser");

  setText("winner-title", `${LANE_META[winner].label} 승리`);
  setText("winner-detail", `server latency 기준 ${delta} ms 차이로 더 빨랐습니다.`);
  setStatus(`비교 완료: server latency 기준 ${LANE_META[winner].label} 가 더 빨랐습니다.`);
}

async function runLane(lane, body) {
  markLanePending(lane);
  const startedAt = performance.now();
  const payload = await requestJson("/api/market/search", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...body, source: LANE_META[lane].source }),
  });
  const clientLatencyMs = performance.now() - startedAt;
  renderLaneSuccess(lane, payload, clientLatencyMs);
}

async function runDuel() {
  resetLane("mongo");
  resetLane("cache");
  state.runs.mongo = null;
  state.runs.cache = null;
  setText("winner-title", "Race Running");
  setText("winner-detail", "MongoDB와 Redis의 server latency를 기준으로 비교 중입니다.");
  setStatus("MongoDB와 Redis에 같은 요청을 동시에 전송했습니다.");

  const body = {
    query: document.getElementById("search-query").value.trim(),
    location: document.getElementById("search-location").value,
    category: document.getElementById("search-category").value,
    limit: 12,
  };

  await Promise.allSettled([
    runLane("mongo", body).catch((error) => renderLaneError("mongo", error)),
    runLane("cache", body).catch((error) => renderLaneError("cache", error)),
  ]);

  updateWinner();
  await refreshMetrics();
}

async function refreshMetrics() {
  const payload = await requestJson("/api/metrics/current");
  renderMetrics(payload);
}

async function bootstrap() {
  const config = await requestJson("/api/config");
  state.config = config;

  setText("redis-backend", config.redis_backend);
  setText("api-target", config.api_target || "local");

  document.getElementById("search-location").innerHTML = config.locations
    .map((item) => `<option value="${item}">${item}</option>`)
    .join("");
  document.getElementById("search-category").innerHTML = config.categories
    .map((item) => `<option value="${item}">${item}</option>`)
    .join("");

  document.getElementById("search-query").value = "아이폰";
  document.getElementById("search-location").value = config.locations.includes("성남시 분당구")
    ? "성남시 분당구"
    : config.locations[0];
  document.getElementById("search-category").value = config.categories.includes("digital")
    ? "digital"
    : config.categories[0];

  resetLane("mongo");
  resetLane("cache");
  await refreshMetrics();
}

document.getElementById("run-duel").addEventListener("click", runDuel);
document.getElementById("refresh-metrics").addEventListener("click", refreshMetrics);

bootstrap().catch((error) => {
  setStatus(`초기화 실패: ${error.message}`);
  setText("winner-title", "초기화 실패");
  setText("winner-detail", error.message);
});
