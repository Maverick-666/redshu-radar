const state = {
  products: [],
  filter: "all",
  query: "",
  currentItemId: null,
  currentProduct: null,
  sortKey: null,
  sortDirection: null,
  taxonomy: { categories: [], tags: [] },
  trackFilter: "all",
  subcategoryFilter: "all",
  selectedTagIds: [],
  monitorFilter: "all",
  taxonomyCreateMode: null,
};

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

function sortableValue(product, key) {
  if (key === "sales_delta" && product.data_status !== "complete_daily") {
    return null;
  }
  if (product[key] == null || (typeof product[key] === "string" && !product[key].trim())) return null;
  const value = Number(product[key]);
  return Number.isFinite(value) ? value : null;
}

function sortedProducts(products) {
  if (!state.sortKey) return products;
  return products
    .map((product, index) => ({ product, index }))
    .sort((left, right) => {
      const leftValue = sortableValue(left.product, state.sortKey);
      const rightValue = sortableValue(right.product, state.sortKey);
      if (leftValue == null && rightValue == null) return left.index - right.index;
      if (leftValue == null) return 1;
      if (rightValue == null) return -1;
      if (leftValue === rightValue) return left.index - right.index;
      const difference = leftValue - rightValue;
      return state.sortDirection === "descending" ? -difference : difference;
    })
    .map(({ product }) => product);
}

function updateSortHeaders() {
  $$(".sort-button").forEach((button) => {
    const active = button.dataset.sortKey === state.sortKey;
    button.closest("th").setAttribute(
      "aria-sort",
      active ? state.sortDirection : "none",
    );
    button.querySelector(".sort-indicator").textContent = active
      ? (state.sortDirection === "descending" ? "↓" : "↑")
      : "";
  });
}

function filteredProducts() {
  const query = state.query.toLowerCase();
  const products = state.products.filter((product) => {
    const matchesQuery = [
      product.title,
      product.shop_name,
      product.item_id,
      product.track?.name,
      product.subcategory?.name,
      ...product.tags.map((tag) => tag.name),
    ]
      .some((value) => String(value || "").toLowerCase().includes(query));
    const matchesFilter = state.filter === "all"
      || product.data_status === state.filter
      || (state.filter === "attention" && ["rollback_suspected", "collection_error"].includes(product.data_status));
    const matchesTrack = state.trackFilter === "all"
      || (state.trackFilter === "uncategorized" && product.track == null)
      || String(product.track?.id) === state.trackFilter;
    const matchesSubcategory = state.subcategoryFilter === "all"
      || (state.subcategoryFilter === "uncategorized" && product.subcategory == null)
      || String(product.subcategory?.id) === state.subcategoryFilter;
    const matchesTags = state.selectedTagIds.every((tagId) =>
      product.tags.some((tag) => tag.id === tagId));
    const matchesMonitoring = state.monitorFilter === "all"
      || (state.monitorFilter === "enabled" && product.enabled)
      || (state.monitorFilter === "disabled" && !product.enabled);
    return matchesQuery && matchesFilter && matchesTrack
      && matchesSubcategory && matchesTags && matchesMonitoring;
  });
  return sortedProducts(products);
}

function productTaxonomyMarkup(product) {
  const category = product.subcategory
    ? `${product.track?.name || "—"} / ${product.subcategory.name}`
    : "未分类";
  const tags = product.tags.slice(0, 2)
    .map((tag) => `<span class="tag-chip">${escapeHtml(tag.name)}</span>`)
    .join("");
  const remaining = product.tags.length > 2
    ? `<span class="tag-chip">+${product.tags.length - 2}</span>`
    : "";
  const monitorClass = product.enabled ? "" : " disabled";
  const monitorLabel = product.enabled ? "监控中" : "候选";
  return `<span class="product-taxonomy"><span>${escapeHtml(category)}</span>${tags}${remaining}<span class="monitor-chip${monitorClass}">${monitorLabel}</span></span>`;
}

function renderProducts() {
  const products = filteredProducts();
  updateSortHeaders();
  const rows = $("#product-rows");
  if (!products.length) {
    rows.innerHTML = '<tr class="empty-row"><td colspan="10">暂无商品，先添加第一批候选。</td></tr>';
  } else {
    rows.innerHTML = products.map((product) => `
      <tr data-item-id="${escapeHtml(product.item_id)}">
        <td class="product-name">${escapeHtml(product.title || "等待首次采集")}<span class="product-id">${escapeHtml(product.item_id)}</span>${productTaxonomyMarkup(product)}</td>
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

function categoryOptions(categories, selectedValue) {
  return categories.map((category) =>
    `<option value="${category.id}"${String(category.id) === String(selectedValue) ? " selected" : ""}>${escapeHtml(category.name)}</option>`
  ).join("");
}

function renderSubcategoryFilter() {
  const selectedTrack = state.trackFilter;
  const includeUncategorized = ["all", "uncategorized"].includes(selectedTrack);
  const categories = state.taxonomy.categories.filter((category) =>
    category.parent_id != null
      && (selectedTrack === "all" || String(category.parent_id) === selectedTrack));
  const available = new Set(categories.map((category) => String(category.id)));
  if (state.subcategoryFilter === "uncategorized" && !includeUncategorized) {
    state.subcategoryFilter = "all";
  } else if (!["all", "uncategorized"].includes(state.subcategoryFilter)
      && !available.has(state.subcategoryFilter)) {
    state.subcategoryFilter = "all";
  }
  $("#subcategory-filter").innerHTML = `
    <option value="all">全部细分</option>
    ${includeUncategorized ? '<option value="uncategorized">未分类</option>' : ""}
    ${categoryOptions(categories, state.subcategoryFilter)}`;
  $("#subcategory-filter").value = state.subcategoryFilter;
}

function renderTagFilter() {
  $("#tag-filter-count").textContent = state.selectedTagIds.length
    ? `(${state.selectedTagIds.length})`
    : "";
  $("#tag-filter-options").innerHTML = state.taxonomy.tags.length
    ? state.taxonomy.tags.map((tag) => `
      <label><input type="checkbox" data-filter-tag-id="${tag.id}"${state.selectedTagIds.includes(tag.id) ? " checked" : ""}> ${escapeHtml(tag.name)} <span>${tag.product_count}</span></label>`).join("")
    : '<p class="field-help">暂无标签</p>';
  $$('[data-filter-tag-id]').forEach((checkbox) => {
    checkbox.addEventListener("change", () => {
      const tagId = Number(checkbox.dataset.filterTagId);
      state.selectedTagIds = checkbox.checked
        ? [...state.selectedTagIds, tagId]
        : state.selectedTagIds.filter((value) => value !== tagId);
      renderTagFilter();
      renderProducts();
    });
  });
}

function renderTaxonomyFilters() {
  const tracks = state.taxonomy.categories.filter((category) => category.parent_id == null);
  $("#track-filter").innerHTML = `
    <option value="all">全部赛道</option>
    <option value="uncategorized">未分类</option>
    ${categoryOptions(tracks, state.trackFilter)}`;
  $("#track-filter").value = state.trackFilter;
  renderSubcategoryFilter();
  renderTagFilter();
}

async function loadTaxonomy() {
  state.taxonomy = await api("/api/taxonomy");
  renderTaxonomyFilters();
  if (state.currentProduct) renderDetailTaxonomy(state.currentProduct);
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
    state.currentProduct = product;
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
    renderDetailTaxonomy(product);
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
    $("#detail-drawer .drawer-body").scrollTop = 0;
    openDrawer("#detail-drawer");
  } catch (error) {
    toast(error.message);
  }
}

function renderDetailSubcategories(selectedId = null) {
  const trackId = Number($("#detail-track").value);
  const categories = state.taxonomy.categories.filter((category) =>
    category.parent_id === trackId);
  $("#detail-subcategory").innerHTML = `
    <option value="">未分类</option>
    ${categoryOptions(categories, selectedId)}`;
  $("#detail-subcategory").disabled = !trackId;
}

function renderDetailTags(selectedIds = []) {
  const selected = new Set(selectedIds.map(Number));
  $("#detail-tag-options").innerHTML = state.taxonomy.tags.length
    ? state.taxonomy.tags.map((tag) => `
      <label><input type="checkbox" data-detail-tag-id="${tag.id}"${selected.has(tag.id) ? " checked" : ""}> ${escapeHtml(tag.name)}</label>`).join("")
    : '<p class="field-help">暂无标签，可用右上角“＋标签”创建。</p>';
}

function renderDetailTaxonomy(product) {
  const tracks = state.taxonomy.categories.filter((category) => category.parent_id == null);
  const trackId = product.track?.id || "";
  $("#detail-track").innerHTML = `
    <option value="">未分类</option>
    ${categoryOptions(tracks, trackId)}`;
  $("#detail-track").value = String(trackId);
  renderDetailSubcategories(product.subcategory?.id || null);
  $("#detail-subcategory").value = product.subcategory?.id || "";
  renderDetailTags(product.tags.map((tag) => tag.id));
  $("#monitor-enabled").checked = product.enabled;
}

async function saveProductSettings() {
  if (!state.currentItemId) return;
  const trackValue = $("#detail-track").value;
  const categoryValue = $("#detail-subcategory").value;
  if (trackValue && !categoryValue) {
    toast("请选择细分品类，或将赛道设为未分类");
    return;
  }
  const payload = {
    decision_status: $("#decision-status").value,
    audience: $("#audience").value || null,
    scenario: $("#scenario").value || null,
    problem: $("#problem").value || null,
    delivery: $("#delivery").value || null,
    notes: $("#notes").value || null,
    next_action: $("#next-action").value || null,
    enabled: $("#monitor-enabled").checked,
    category_id: categoryValue ? Number(categoryValue) : null,
    tag_ids: $$('[data-detail-tag-id]:checked').map((checkbox) =>
      Number(checkbox.dataset.detailTagId)),
  };
  const button = $("#save-decision-button");
  const originalLabel = button.textContent;
  button.disabled = true;
  button.textContent = "保存中…";
  try {
    state.currentProduct = await api(`/api/products/${state.currentItemId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
    await Promise.all([loadTaxonomy(), loadProducts()]);
    toast("商品设置已保存");
  } catch (error) {
    toast(error.message);
  } finally {
    button.disabled = false;
    button.textContent = originalLabel;
  }
}

function selectedDetailTagIds() {
  return $$('[data-detail-tag-id]:checked')
    .map((checkbox) => Number(checkbox.dataset.detailTagId));
}

function openTaxonomyDialog(mode) {
  if (mode === "subcategory" && !Number($("#detail-track").value)) {
    toast("请先选择或创建赛道");
    return;
  }
  const labels = {
    track: ["新建赛道", "用于组织一组细分品类"],
    subcategory: ["新建细分品类", "将创建在当前赛道下"],
    tag: ["新建标签", "标签可跨赛道复用"],
  };
  state.taxonomyCreateMode = mode;
  $("#taxonomy-dialog-title").textContent = labels[mode][0];
  $("#taxonomy-dialog-help").textContent = labels[mode][1];
  $("#taxonomy-name").value = "";
  $("#taxonomy-dialog").showModal();
  $("#taxonomy-name").focus();
}

async function createTaxonomy(event) {
  event.preventDefault();
  const name = $("#taxonomy-name").value.trim();
  if (!name) return;
  const mode = state.taxonomyCreateMode;
  const selectedTrackId = Number($("#detail-track").value) || null;
  const selectedCategoryId = Number($("#detail-subcategory").value) || null;
  const selectedTagIds = selectedDetailTagIds();
  const enabled = $("#monitor-enabled").checked;
  const confirmButton = $("#taxonomy-dialog-confirm");
  confirmButton.disabled = true;
  try {
    const created = mode === "tag"
      ? await api("/api/tags", {
        method: "POST",
        body: JSON.stringify({ name }),
      })
      : await api("/api/categories", {
        method: "POST",
        body: JSON.stringify({
          name,
          parent_id: mode === "subcategory" ? selectedTrackId : null,
        }),
      });
    await loadTaxonomy();
    const trackId = mode === "track" ? created.id : selectedTrackId;
    const categoryId = mode === "track"
      ? null
      : (mode === "subcategory" ? created.id : selectedCategoryId);
    $("#detail-track").value = trackId ? String(trackId) : "";
    renderDetailSubcategories(categoryId);
    $("#detail-subcategory").value = categoryId ? String(categoryId) : "";
    renderDetailTags(mode === "tag" ? [...selectedTagIds, created.id] : selectedTagIds);
    $("#monitor-enabled").checked = enabled;
    $("#taxonomy-dialog").close();
    toast(`${labelsForCreation(mode)}已创建`);
  } catch (error) {
    toast(error.message);
  } finally {
    confirmButton.disabled = false;
  }
}

function labelsForCreation(mode) {
  return { track: "赛道", subcategory: "细分品类", tag: "标签" }[mode];
}

$("#add-button").addEventListener("click", () => openDrawer("#add-drawer"));
$("#collect-button").addEventListener("click", collectNow);
$("#import-button").addEventListener("click", importProducts);
$("#save-decision-button").addEventListener("click", saveProductSettings);
$("#create-track-button").addEventListener("click", () => openTaxonomyDialog("track"));
$("#create-subcategory-button").addEventListener("click", () => openTaxonomyDialog("subcategory"));
$("#create-tag-button").addEventListener("click", () => openTaxonomyDialog("tag"));
$("#taxonomy-create-form").addEventListener("submit", createTaxonomy);
$("#taxonomy-dialog-cancel").addEventListener("click", () => $("#taxonomy-dialog").close());
$("#detail-track").addEventListener("change", () => renderDetailSubcategories());
$("#drawer-backdrop").addEventListener("click", closeDrawers);
$$('[data-close-drawer]').forEach((button) => button.addEventListener("click", closeDrawers));
$("#search-input").addEventListener("input", (event) => { state.query = event.target.value; renderProducts(); });
$("#track-filter").addEventListener("change", (event) => {
  state.trackFilter = event.target.value;
  renderSubcategoryFilter();
  renderProducts();
});
$("#subcategory-filter").addEventListener("change", (event) => {
  state.subcategoryFilter = event.target.value;
  renderProducts();
});
$("#monitor-filter").addEventListener("change", (event) => {
  state.monitorFilter = event.target.value;
  renderProducts();
});
$$('.filter').forEach((button) => button.addEventListener("click", () => {
  $$('.filter').forEach((item) => item.classList.remove("active"));
  button.classList.add("active");
  state.filter = button.dataset.filter;
  renderProducts();
}));
$$(".sort-button").forEach((button) => button.addEventListener("click", () => {
  const key = button.dataset.sortKey;
  if (state.sortKey === key) {
    state.sortDirection = state.sortDirection === "descending"
      ? "ascending"
      : "descending";
  } else {
    state.sortKey = key;
    state.sortDirection = "descending";
  }
  renderProducts();
}));

Promise.all([
  loadStatus(),
  (async () => {
    await loadTaxonomy();
    await loadProducts();
  })(),
]).catch((error) => toast(error.message));
