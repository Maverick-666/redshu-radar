const state = { products: [], filter: "all", query: "", currentItemId: null };

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || `请求失败：${response.status}`);
  }
  return response.json();
}

function formatMoney(cents) {
  return cents == null ? "—" : `¥${(Number(cents) / 100).toFixed(2)}`;
}

function formatValue(value, prefix = "") {
  return value == null ? "—" : `${prefix}${value}`;
}

function formatDailyDelta(product) {
  return product.data_status === "complete_daily"
    ? formatValue(product.sales_delta, "+")
    : "—";
}

function formatBytes(bytes) {
  if (!bytes) return "0 KB";
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

const statusLabels = {
  complete_daily: ["完整 24h", ""],
  awaiting_baseline: ["待基线", "waiting"],
  partial: ["时段数据", "waiting"],
  cross_period: ["跨期 · 不入榜", "waiting"],
  rollback_suspected: ["销量回退", "attention"],
  collection_error: ["采集失败", "attention"],
};

const decisionLabels = {
  watching: "观察",
  reviewing: "复核",
  testing: "测试",
  dropped: "放弃",
  scaling: "放大",
};

function statusBadge(status) {
  const [label, style] = statusLabels[status] || [status || "未知", "attention"];
  return `<span class="status-badge ${style}">${escapeHtml(label)}</span>`;
}

function filteredProducts() {
  const query = state.query.toLowerCase();
  return state.products.filter((product) => {
    const matchesQuery = [product.title, product.shop_name, product.item_id]
      .some((value) => String(value || "").toLowerCase().includes(query));
    const matchesFilter = state.filter === "all"
      || product.data_status === state.filter
      || (state.filter === "attention" && ["rollback_suspected", "collection_error"].includes(product.data_status));
    return matchesQuery && matchesFilter;
  });
}

function renderProducts() {
  const products = filteredProducts();
  const rows = $("#product-rows");
  if (!products.length) {
    rows.innerHTML = '<tr class="empty-row"><td colspan="10">暂无商品，先添加第一批候选。</td></tr>';
  } else {
    rows.innerHTML = products.map((product) => `
      <tr data-item-id="${escapeHtml(product.item_id)}">
        <td class="product-name">${escapeHtml(product.title || "等待首次采集")}<span class="product-id">${escapeHtml(product.item_id)}</span></td>
        <td>${escapeHtml(product.shop_name || "—")}</td>
        <td>${formatMoney(product.price_cents)}</td>
        <td class="number-strong">${formatDailyDelta(product)}</td>
        <td>${formatValue(product.hourly_delta, "+")}</td>
        <td>${formatValue(product.trusted_high_water)}</td>
        <td>${formatValue(product.hotness)}</td>
        <td>${product.product_value == null ? "—" : `¥${escapeHtml(product.product_value)}`}</td>
        <td>${statusBadge(product.data_status)}</td>
        <td>${escapeHtml(decisionLabels[product.decision_status] || product.decision_status)}</td>
      </tr>`).join("");
  }
  $("#visible-count").textContent = `${products.length} 个商品`;
  $("#product-count").textContent = state.products.length;
  $("#complete-count").textContent = state.products.filter((p) => p.data_status === "complete_daily").length;
  $("#awaiting-count").textContent = state.products.filter((p) => p.data_status === "awaiting_baseline").length;
  $("#attention-count").textContent = state.products.filter((p) => ["rollback_suspected", "collection_error"].includes(p.data_status)).length;
  $$("#product-rows tr[data-item-id]").forEach((row) => {
    row.addEventListener("click", () => openDetail(row.dataset.itemId));
  });
}

async function loadStatus() {
  const status = await api("/api/status");
  $("#database-size").textContent = formatBytes(status.database_bytes);
  $("#snapshot-count").textContent = status.snapshot_count;
  const last = status.last_collection;
  $("#run-state").textContent = last ? ({ succeeded: "正常", partial: "部分失败", failed: "失败", running: "运行中" }[last.status] || last.status) : "待命";
  $("#run-dot").classList.toggle("attention", Boolean(last && ["partial", "failed"].includes(last.status)));
}

async function loadProducts() {
  state.products = await api("/api/products");
  renderProducts();
}

function openDrawer(selector) {
  $("#drawer-backdrop").hidden = false;
  $(selector).hidden = false;
}

function closeDrawers() {
  $("#drawer-backdrop").hidden = true;
  $$(".drawer").forEach((drawer) => { drawer.hidden = true; });
}

function toast(message) {
  const element = $("#toast");
  element.textContent = message;
  element.hidden = false;
  window.setTimeout(() => { element.hidden = true; }, 2800);
}

async function importProducts() {
  const input = $("#product-input").value.trim();
  if (!input) return toast("请先粘贴商品信息");
  const button = $("#import-button");
  button.disabled = true;
  button.textContent = "解析中…";
  try {
    const results = await api("/api/products/import", {
      method: "POST",
      body: JSON.stringify({ input_text: input }),
    });
    const resultList = $("#import-results");
    resultList.hidden = false;
    resultList.innerHTML = results.map((result) => `
      <div class="result-item ${result.status === "error" ? "error" : ""}">
        第 ${result.line_number} 行 · ${escapeHtml(result.item_id || result.original_input)} · ${escapeHtml(result.status === "ready" ? "已加入" : result.message)}
      </div>`).join("");
    const readyItemIds = results
      .filter((result) => result.status === "ready")
      .map((result) => result.item_id);
    if (readyItemIds.length) {
      button.textContent = "建立首次基线…";
      await api("/api/collections", {
        method: "POST",
        body: JSON.stringify({ trigger: "manual", item_ids: readyItemIds }),
      });
    }
    await Promise.all([loadProducts(), loadStatus()]);
    toast("导入处理完成");
  } catch (error) {
    toast(error.message);
  } finally {
    button.disabled = false;
    button.textContent = "解析并建立基线";
  }
}

async function collectNow() {
  const button = $("#collect-button");
  button.disabled = true;
  button.textContent = "采集中…";
  try {
    const summary = await api("/api/collections", { method: "POST", body: JSON.stringify({ trigger: "manual" }) });
    await Promise.all([loadProducts(), loadStatus()]);
    toast(`采集完成：${summary.success_count} 成功，${summary.failure_count} 失败`);
  } catch (error) {
    toast(error.message);
  } finally {
    button.disabled = false;
    button.textContent = "立即采集";
  }
}

async function openDetail(itemId) {
  try {
    const product = await api(`/api/products/${itemId}`);
    state.currentItemId = itemId;
    $("#detail-title").textContent = product.title || "等待首次采集";
    $("#detail-shop").textContent = `${product.shop_name || "未知店铺"} · ${itemId}`;
    $("#detail-metrics").innerHTML = [
      ["当前价格", formatMoney(product.price_cents)],
      ["24h 增量", formatDailyDelta(product)],
      ["累计已售", formatValue(product.trusted_high_water)],
      ["爆品值", formatValue(product.hotness)],
      ["商品价值", product.product_value == null ? "—" : `¥${product.product_value}`],
      ["实际间隔", product.interval_hours == null ? "—" : `${product.interval_hours} 小时`],
      ["数据状态", (statusLabels[product.data_status] || [product.data_status])[0]],
    ].map(([label, value]) => `<div class="metric"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`).join("");
    $("#decision-status").value = product.decision_status;
    ["audience", "scenario", "problem", "delivery", "notes"].forEach((field) => { $(`#${field}`).value = product[field] || ""; });
    $("#next-action").value = product.next_action || "";
    $("#snapshot-list").innerHTML = product.snapshots.length
      ? [...product.snapshots].reverse().map((snapshot) => {
        const roles = [];
        if (snapshot.id === product.current_snapshot_id) roles.push("当前");
        if (snapshot.id === product.baseline_snapshot_id) roles.push("指标基线");
        const role = roles.length ? roles.join(" / ") : "历史";
        return `<div class="snapshot-item"><span>${new Date(snapshot.captured_at).toLocaleString("zh-CN")} · ${role}</span><span>已售 ${snapshot.sold_reported}</span><span>${formatMoney(snapshot.price_cents)}</span></div>`;
      }).join("")
      : '<p class="field-help">暂无可信快照。</p>';
    $("#failure-list").innerHTML = product.failures.length
      ? product.failures.map((failure) => `<div class="snapshot-item"><span>${new Date(failure.attempted_at).toLocaleString("zh-CN")}</span><span>${escapeHtml(failure.error_type)}</span><span>${escapeHtml(failure.error_message)}</span></div>`).join("")
      : '<p class="field-help">暂无采集失败。</p>';
    openDrawer("#detail-drawer");
  } catch (error) {
    toast(error.message);
  }
}

async function saveDecision() {
  if (!state.currentItemId) return;
  const payload = {
    decision_status: $("#decision-status").value,
    audience: $("#audience").value || null,
    scenario: $("#scenario").value || null,
    problem: $("#problem").value || null,
    delivery: $("#delivery").value || null,
    notes: $("#notes").value || null,
    next_action: $("#next-action").value || null,
  };
  try {
    await api(`/api/products/${state.currentItemId}/decision`, { method: "PATCH", body: JSON.stringify(payload) });
    await loadProducts();
    toast("人工判断已保存");
  } catch (error) {
    toast(error.message);
  }
}

$("#add-button").addEventListener("click", () => openDrawer("#add-drawer"));
$("#collect-button").addEventListener("click", collectNow);
$("#import-button").addEventListener("click", importProducts);
$("#save-decision-button").addEventListener("click", saveDecision);
$("#drawer-backdrop").addEventListener("click", closeDrawers);
$$('[data-close-drawer]').forEach((button) => button.addEventListener("click", closeDrawers));
$("#search-input").addEventListener("input", (event) => { state.query = event.target.value; renderProducts(); });
$$('.filter').forEach((button) => button.addEventListener("click", () => {
  $$('.filter').forEach((item) => item.classList.remove("active"));
  button.classList.add("active");
  state.filter = button.dataset.filter;
  renderProducts();
}));

Promise.all([loadStatus(), loadProducts()]).catch((error) => toast(error.message));
