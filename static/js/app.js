const AUTH_TOKEN_KEY = "healthlog_token";
const AUTH_USERNAME_KEY = "healthlog_username";

const BADGE_CLASS = {
  "정상": "badge-success",
  "적정": "badge-success",
  "우수": "badge-success",
  "주의": "badge-warning",
  "과체중": "badge-warning",
  "공복혈당장애": "badge-warning",
  "저체중": "badge-warning",
  "부족": "badge-warning",
  "과다": "badge-warning",
  "고혈압": "badge-danger",
  "비만": "badge-danger",
  "당뇨 의심": "badge-danger",
};

let editingId = null;
let weightChart = null;
let bpChart = null;
let stepsChart = null;
const tabLoaded = { dashboard: false, records: false, goal: false, report: false };

/* ---------- auth helpers ---------- */

function getToken() {
  return localStorage.getItem(AUTH_TOKEN_KEY);
}

function getAuthHeaders() {
  return { "Authorization": `Bearer ${getToken()}` };
}

function saveAuth(token, username) {
  localStorage.setItem(AUTH_TOKEN_KEY, token);
  localStorage.setItem(AUTH_USERNAME_KEY, username);
}

function clearAuth() {
  localStorage.removeItem(AUTH_TOKEN_KEY);
  localStorage.removeItem(AUTH_USERNAME_KEY);
}

function showAuth() {
  clearAuth();
  document.getElementById("app-section").style.display = "none";
  document.getElementById("auth-section").style.display = "block";
  document.getElementById("login-view").style.display = "block";
  document.getElementById("signup-view").style.display = "none";
}

function showApp() {
  document.getElementById("auth-section").style.display = "none";
  document.getElementById("app-section").style.display = "block";
  document.getElementById("current-username").textContent = localStorage.getItem(AUTH_USERNAME_KEY) || "";
  Object.keys(tabLoaded).forEach((key) => { tabLoaded[key] = false; });
  switchTab("dashboard");
}

function isUnauthorized(res) {
  if (res.status === 401) {
    showAuth();
    return true;
  }
  return false;
}

function showError(status, body) {
  const banner = document.getElementById("error-banner");
  banner.textContent = `${status}: ${JSON.stringify(body.detail)}`;
  banner.style.display = "block";
}

function clearError() {
  const banner = document.getElementById("error-banner");
  banner.style.display = "none";
  banner.textContent = "";
}

/* ---------- login / signup / logout / delete account ---------- */

async function handleLogin(event) {
  event.preventDefault();
  clearError();
  const form = event.target;
  const params = new URLSearchParams();
  params.set("username", form.username.value);
  params.set("password", form.password.value);

  const res = await fetch("/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: params.toString(),
  });

  if (!res.ok) {
    showError(res.status, await res.json());
    return;
  }

  const data = await res.json();
  saveAuth(data.access_token, form.username.value);
  form.reset();
  showApp();
}

async function handleSignup(event) {
  event.preventDefault();
  clearError();
  const form = event.target;
  const username = form.username.value;
  const password = form.password.value;

  const res = await fetch("/auth/signup", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });

  if (!res.ok) {
    showError(res.status, await res.json());
    return;
  }

  const params = new URLSearchParams();
  params.set("username", username);
  params.set("password", password);
  const loginRes = await fetch("/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: params.toString(),
  });

  if (!loginRes.ok) {
    showError(loginRes.status, await loginRes.json());
    return;
  }

  const loginData = await loginRes.json();
  saveAuth(loginData.access_token, username);
  form.reset();
  showApp();
}

function handleLogout() {
  showAuth();
}

async function handleDeleteAccount() {
  if (!confirm("정말 회원탈퇴 하시겠어요? 로그인은 더 이상 할 수 없습니다.")) return;

  const res = await fetch("/auth/me", {
    method: "DELETE",
    headers: getAuthHeaders(),
  });

  if (isUnauthorized(res)) return;
  if (!res.ok) {
    showError(res.status, await res.json());
    return;
  }

  showAuth();
}

/* ---------- tabs ---------- */

function switchTab(tabName) {
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.tab === tabName);
  });
  document.querySelectorAll(".view").forEach((view) => {
    view.classList.toggle("active", view.id === `view-${tabName}`);
  });
  loadTab(tabName);
}

function loadTab(tabName) {
  if (tabLoaded[tabName]) return;
  tabLoaded[tabName] = true;
  if (tabName === "dashboard") loadDashboard();
  else if (tabName === "records") loadRecordsList();
  else if (tabName === "goal") loadGoalView();
  else if (tabName === "report") loadReportView();
}

function invalidateAndReload() {
  tabLoaded.dashboard = false;
  tabLoaded.report = false;
  tabLoaded.goal = false;
  loadRecordsList();
}

/* ---------- shared helpers ---------- */

async function fetchAllRecords() {
  const res = await fetch("/records", { headers: getAuthHeaders() });
  if (isUnauthorized(res)) return null;
  const data = await res.json();
  return data.records;
}

async function fetchRecordsSince(days) {
  const start = new Date();
  start.setDate(start.getDate() - (days - 1));
  const startStr = start.toISOString().slice(0, 10);
  const res = await fetch(`/search?start=${startStr}`, { headers: getAuthHeaders() });
  if (isUnauthorized(res)) return null;
  const data = await res.json();
  return data.records;
}

function badgeHtml(category) {
  const cls = BADGE_CLASS[category] || "badge-success";
  return `<span class="badge ${cls}">${category}</span>`;
}

/* ---------- dashboard ---------- */

async function loadDashboard() {
  const records = await fetchRecordsSince(14);
  if (records === null) return;
  const sorted = [...records].sort((a, b) => a.date.localeCompare(b.date));
  renderKpiCards(sorted);
  renderWeightChart(sorted);
  renderBpChart(sorted);
}

function renderKpiCards(sorted) {
  const weightValueEl = document.getElementById("kpi-weight-value");
  const weightDeltaEl = document.getElementById("kpi-weight-delta");
  const bmiValueEl = document.getElementById("kpi-bmi-value");
  const bmiBadgeEl = document.getElementById("kpi-bmi-badge");
  const bpValueEl = document.getElementById("kpi-bp-value");
  const bpBadgeEl = document.getElementById("kpi-bp-badge");
  const sugarValueEl = document.getElementById("kpi-sugar-value");
  const sugarBadgeEl = document.getElementById("kpi-sugar-badge");

  if (sorted.length === 0) {
    weightValueEl.textContent = "-";
    weightDeltaEl.textContent = "기록 없음";
    bmiValueEl.textContent = "-";
    bmiBadgeEl.innerHTML = "";
    bpValueEl.textContent = "-";
    bpBadgeEl.innerHTML = "";
    sugarValueEl.textContent = "-";
    sugarBadgeEl.innerHTML = "";
    return;
  }

  const latest = sorted[sorted.length - 1];
  const prev = sorted.length > 1 ? sorted[sorted.length - 2] : null;

  weightValueEl.textContent = `${latest.weight}kg`;
  if (prev) {
    const diff = Math.round((latest.weight - prev.weight) * 10) / 10;
    const arrow = diff > 0 ? "▲" : diff < 0 ? "▼" : "–";
    weightDeltaEl.textContent = `전일 대비 ${arrow} ${Math.abs(diff)}kg`;
  } else {
    weightDeltaEl.textContent = "전일 기록 없음";
  }

  bmiValueEl.textContent = latest.bmi;
  bmiBadgeEl.innerHTML = badgeHtml(latest.bmi_category);

  bpValueEl.textContent = `${latest.systolic}/${latest.diastolic}`;
  bpBadgeEl.innerHTML = badgeHtml(latest.bp_category);

  sugarValueEl.textContent = `${latest.blood_sugar}`;
  sugarBadgeEl.innerHTML = badgeHtml(latest.sugar_category);
}

function renderWeightChart(sorted) {
  const ctx = document.getElementById("weight-chart");
  if (weightChart) weightChart.destroy();
  weightChart = new Chart(ctx, {
    type: "line",
    data: {
      labels: sorted.map((r) => r.date.slice(5)),
      datasets: [{
        label: "체중(kg)",
        data: sorted.map((r) => r.weight),
        borderColor: "#2a78d6",
        backgroundColor: "rgba(42, 120, 214, 0.12)",
        fill: true,
        tension: 0.25,
        pointRadius: 3,
        borderWidth: 2,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: { y: { beginAtZero: false } },
    },
  });
}

function renderBpChart(sorted) {
  const ctx = document.getElementById("bp-chart");
  if (bpChart) bpChart.destroy();
  bpChart = new Chart(ctx, {
    type: "line",
    data: {
      labels: sorted.map((r) => r.date.slice(5)),
      datasets: [
        {
          label: "수축기",
          data: sorted.map((r) => r.systolic),
          borderColor: "#2a78d6",
          backgroundColor: "#2a78d6",
          tension: 0.25,
          pointRadius: 3,
          borderWidth: 2,
        },
        {
          label: "이완기",
          data: sorted.map((r) => r.diastolic),
          borderColor: "#d97706",
          backgroundColor: "#d97706",
          tension: 0.25,
          pointRadius: 3,
          borderWidth: 2,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
    },
  });

  document.getElementById("bp-chart-legend").innerHTML = `
    <span class="legend-item"><span class="legend-swatch" style="background:#2a78d6"></span>수축기</span>
    <span class="legend-item"><span class="legend-swatch" style="background:#d97706"></span>이완기</span>
  `;
}

/* ---------- records view ---------- */

async function loadRecordsList() {
  const records = await fetchAllRecords();
  if (records === null) return;
  const sorted = [...records].sort((a, b) => b.date.localeCompare(a.date));
  const container = document.getElementById("record-list");
  container.innerHTML = "";
  if (sorted.length === 0) {
    container.innerHTML = `<p class="empty-state">아직 기록이 없습니다.</p>`;
    return;
  }
  for (const record of sorted) {
    container.appendChild(renderRecordRow(record));
  }
}

function renderRecordRow(record) {
  const row = document.createElement("div");
  row.className = "record-row";
  row.innerHTML = `
    <span class="rr-date">${record.date}</span>
    <span class="rr-weight">${record.weight}kg</span>
    <span class="rr-bmi">BMI ${record.bmi}</span>
    <span class="rr-badges">
      ${badgeHtml(record.bmi_category)}
      ${badgeHtml(record.bp_category)}
      ${badgeHtml(record.sugar_category)}
    </span>
    ${record.warnings.length ? `<span class="rr-warn">${record.warnings.join(", ")}</span>` : ""}
  `;

  const actions = document.createElement("span");
  actions.className = "rr-actions";

  const editBtn = document.createElement("button");
  editBtn.type = "button";
  editBtn.className = "icon-btn";
  editBtn.textContent = "수정";
  editBtn.addEventListener("click", () => startEdit(record));

  const deleteBtn = document.createElement("button");
  deleteBtn.type = "button";
  deleteBtn.className = "icon-btn";
  deleteBtn.textContent = "삭제";
  deleteBtn.addEventListener("click", () => deleteRecord(record.id));

  actions.appendChild(editBtn);
  actions.appendChild(deleteBtn);
  row.appendChild(actions);

  return row;
}

function showRecordForm() {
  document.getElementById("record-form-wrapper").style.display = "block";
}

function hideRecordForm() {
  document.getElementById("record-form-wrapper").style.display = "none";
}

function toggleRecordForm() {
  const wrapper = document.getElementById("record-form-wrapper");
  if (wrapper.style.display === "none") {
    cancelEdit();
    showRecordForm();
  } else {
    hideRecordForm();
  }
}

function setFormMode(mode, id) {
  const heading = document.getElementById("form-heading");
  const cancelBtn = document.getElementById("cancel-btn");
  if (mode === "edit") {
    heading.textContent = `기록 수정 중 (#${id})`;
    cancelBtn.style.display = "inline-block";
  } else {
    heading.textContent = "새 기록 추가";
    cancelBtn.style.display = "none";
  }
}

function fillFormWith(record) {
  const form = document.getElementById("record-form");
  form.date.value = record.date;
  form.weight.value = record.weight;
  form.height.value = record.height;
  form.systolic.value = record.systolic;
  form.diastolic.value = record.diastolic;
  form.blood_sugar.value = record.blood_sugar;
  form.steps.value = record.steps;
  form.sleep_hours.value = record.sleep_hours;
  form.memo.value = record.memo;
}

function startEdit(record) {
  editingId = record.id;
  clearError();
  fillFormWith(record);
  setFormMode("edit", record.id);
  showRecordForm();
}

function cancelEdit() {
  editingId = null;
  document.getElementById("record-form").reset();
  setFormMode("create");
}

async function deleteRecord(id) {
  if (!confirm("이 기록을 삭제할까요?")) return;

  const res = await fetch(`/records/${id}`, {
    method: "DELETE",
    headers: getAuthHeaders(),
  });

  if (isUnauthorized(res)) return;
  if (!res.ok) {
    showError(res.status, await res.json());
    return;
  }

  clearError();
  if (editingId === id) cancelEdit();
  invalidateAndReload();
}

async function submitForm(event) {
  event.preventDefault();
  clearError();

  const form = event.target;
  const payload = {
    date: form.date.value,
    weight: parseFloat(form.weight.value),
    height: parseFloat(form.height.value),
    systolic: parseInt(form.systolic.value, 10),
    diastolic: parseInt(form.diastolic.value, 10),
    blood_sugar: parseInt(form.blood_sugar.value, 10),
    steps: parseInt(form.steps.value || "0", 10),
    sleep_hours: parseFloat(form.sleep_hours.value || "0"),
    memo: form.memo.value,
  };

  const method = editingId ? "PUT" : "POST";
  const url = editingId ? `/records/${editingId}` : "/records";

  const res = await fetch(url, {
    method,
    headers: { "Content-Type": "application/json", ...getAuthHeaders() },
    body: JSON.stringify(payload),
  });

  if (isUnauthorized(res)) return;
  if (!res.ok) {
    showError(res.status, await res.json());
    return;
  }

  cancelEdit();
  hideRecordForm();
  invalidateAndReload();
}

/* ---------- goal view ---------- */

async function loadGoalView() {
  const res = await fetch("/goal", { headers: getAuthHeaders() });
  if (isUnauthorized(res)) return;
  const data = await res.json();
  renderGoalDisplay(data);
}

function progressMetric(label, targetText, percent) {
  const pct = percent === null || percent === undefined ? 0 : percent;
  return `
    <div class="goal-metric">
      <div class="goal-metric-label">${label}</div>
      <div class="goal-metric-values">목표: ${targetText} · 달성률 ${pct}%</div>
      <div class="progress-track"><div class="progress-fill" style="width:${pct}%"></div></div>
    </div>
  `;
}

function renderGoalDisplay(data) {
  const el = document.getElementById("goal-display");
  if (!data.goal) {
    el.innerHTML = `<p class="empty-state">설정된 목표가 없습니다. 위 폼에서 목표를 등록해보세요.</p>`;
    return;
  }
  const g = data.goal;
  const a = data.achievement;

  let html = `<div class="goal-card">`;
  html += `<div class="goal-metric-label">설정일: ${g.set_date}</div>`;
  if (a) {
    html += progressMetric("체중", `${g.target_weight}kg`, a.weight_percent);
    html += progressMetric("수축기 혈압", `${g.target_systolic}`, a.systolic_percent);
    html += progressMetric("이완기 혈압", `${g.target_diastolic}`, a.diastolic_percent);
  } else {
    html += `<p class="empty-state">달성률 계산 불가 (설정일 이후 기록이 없어요)</p>`;
  }
  html += `</div>`;
  el.innerHTML = html;
}

async function submitGoal(event) {
  event.preventDefault();
  clearError();

  const form = event.target;
  const payload = {
    target_weight: parseFloat(form.target_weight.value),
    target_systolic: parseInt(form.target_systolic.value, 10),
    target_diastolic: parseInt(form.target_diastolic.value, 10),
  };

  const res = await fetch("/goal", {
    method: "PUT",
    headers: { "Content-Type": "application/json", ...getAuthHeaders() },
    body: JSON.stringify(payload),
  });

  if (isUnauthorized(res)) return;
  if (!res.ok) {
    showError(res.status, await res.json());
    return;
  }

  form.reset();
  loadGoalView();
}

/* ---------- report view ---------- */

async function loadReportView() {
  const res = await fetch("/reports/weekly", { headers: getAuthHeaders() });
  if (isUnauthorized(res)) return;
  const data = await res.json();
  renderReportStats(data);

  const stepsRecords = await fetchRecordsSince(7);
  if (stepsRecords === null) return;
  renderStepsChart(stepsRecords);
}

function deltaText(value, unit) {
  if (value === null || value === undefined) return "";
  const arrow = value > 0 ? "▲" : value < 0 ? "▼" : "–";
  return `지난주 대비 ${arrow} ${Math.abs(value)}${unit}`;
}

function renderReportStats(data) {
  const el = document.getElementById("report-stats");
  if (!data.this_week) {
    el.innerHTML = `<p class="empty-state">비교할 데이터가 부족합니다 (최근 14일 기록이 필요해요).</p>`;
    return;
  }
  const tw = data.this_week;
  const delta = data.delta || {};
  el.innerHTML = `
    <div class="stat-tile">
      <div class="stat-label">평균 체중</div>
      <div class="stat-value">${tw.avg_weight}kg</div>
      <div class="stat-delta">${deltaText(delta.weight, "kg")}</div>
    </div>
    <div class="stat-tile">
      <div class="stat-label">평균 걸음 수</div>
      <div class="stat-value">${tw.avg_steps}</div>
      <div class="stat-delta">${deltaText(delta.steps, "보")}</div>
    </div>
    <div class="stat-tile">
      <div class="stat-label">평균 수면</div>
      <div class="stat-value">${tw.avg_sleep_hours}h</div>
      <div class="stat-delta">${deltaText(delta.sleep_hours, "h")}</div>
    </div>
  `;
}

function renderStepsChart(records) {
  const sorted = [...records].sort((a, b) => a.date.localeCompare(b.date));
  const ctx = document.getElementById("steps-chart");
  if (stepsChart) stepsChart.destroy();
  stepsChart = new Chart(ctx, {
    type: "bar",
    data: {
      labels: sorted.map((r) => r.date.slice(5)),
      datasets: [{
        label: "걸음 수",
        data: sorted.map((r) => r.steps),
        backgroundColor: "#2a78d6",
        borderRadius: 4,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
    },
  });
}

/* ---------- wire up ---------- */

document.getElementById("show-signup-btn").addEventListener("click", () => {
  document.getElementById("login-view").style.display = "none";
  document.getElementById("signup-view").style.display = "block";
});
document.getElementById("show-login-btn").addEventListener("click", () => {
  document.getElementById("signup-view").style.display = "none";
  document.getElementById("login-view").style.display = "block";
});
document.getElementById("login-form").addEventListener("submit", handleLogin);
document.getElementById("signup-form").addEventListener("submit", handleSignup);
document.getElementById("logout-btn").addEventListener("click", handleLogout);
document.getElementById("delete-account-btn").addEventListener("click", handleDeleteAccount);
document.getElementById("cancel-btn").addEventListener("click", () => { cancelEdit(); hideRecordForm(); });
document.getElementById("toggle-form-btn").addEventListener("click", toggleRecordForm);
document.getElementById("record-form").addEventListener("submit", submitForm);
document.getElementById("goal-form").addEventListener("submit", submitGoal);

document.querySelectorAll(".tab-btn").forEach((btn) => {
  btn.addEventListener("click", () => switchTab(btn.dataset.tab));
});

if (getToken()) {
  showApp();
} else {
  showAuth();
}
