let page = 1;
let pageSize = 25;
let sortBy = "timestamp";
let sortDir = "desc";
let total = 0;
let charts = {};

// Grafikleri yükle
function loadCharts() {
  fetch("/api/admin/charts")
    .then((res) => res.json())
    .then((data) => {
      if (!data.success) {
        showError(data.error || "Grafik verileri alınamadı.");
        return;
      }
      createPlatformChart(data.platform_distribution);
      createDailyChart(data.daily_downloads);
      createSuccessChart(data.success_rates);
      createHourlyChart(data.hourly_distribution);
      createSizeChart(data.file_size_distribution);
      updateStatsCards(data);
    })
    .catch((err) => showError("Grafik verileri alınamadı: " + err));
}

function createPlatformChart(data) {
  const ctx = document.getElementById("platformChart").getContext("2d");
  const colors = ["#FF6384", "#36A2EB", "#FFCE56", "#4BC0C0", "#9966FF"];

  charts.platform = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels: data.map((d) => capitalize(d.platform)),
      datasets: [
        {
          data: data.map((d) => d.count),
          backgroundColor: colors.slice(0, data.length),
          borderWidth: 2,
          borderColor: "#fff",
        },
      ],
    },
    options: {
      responsive: true,
      plugins: {
        legend: {
          position: "bottom",
        },
      },
    },
  });
}

function createDailyChart(data) {
  const ctx = document.getElementById("dailyChart").getContext("2d");

  charts.daily = new Chart(ctx, {
    type: "line",
    data: {
      labels: data.map((d) => new Date(d.date).toLocaleDateString("tr-TR")),
      datasets: [
        {
          label: "İndirme Sayısı",
          data: data.map((d) => d.count),
          borderColor: "#667eea",
          backgroundColor: "rgba(102, 126, 234, 0.1)",
          tension: 0.4,
          fill: true,
        },
      ],
    },
    options: {
      responsive: true,
      scales: {
        y: {
          beginAtZero: true,
        },
      },
    },
  });
}

function createSuccessChart(data) {
  const ctx = document.getElementById("successChart").getContext("2d");

  charts.success = new Chart(ctx, {
    type: "bar",
    data: {
      labels: data.map((d) => capitalize(d.platform)),
      datasets: [
        {
          label: "Başarı Oranı (%)",
          data: data.map((d) => d.success_rate),
          backgroundColor: "#00b894",
          borderColor: "#00a085",
          borderWidth: 1,
        },
      ],
    },
    options: {
      responsive: true,
      scales: {
        y: {
          beginAtZero: true,
          max: 100,
        },
      },
    },
  });
}

function createHourlyChart(data) {
  const ctx = document.getElementById("hourlyChart").getContext("2d");

  charts.hourly = new Chart(ctx, {
    type: "bar",
    data: {
      labels: data.map((d) => d.hour + ":00"),
      datasets: [
        {
          label: "İndirme Sayısı",
          data: data.map((d) => d.count),
          backgroundColor: "#764ba2",
          borderColor: "#667eea",
          borderWidth: 1,
        },
      ],
    },
    options: {
      responsive: true,
      scales: {
        y: {
          beginAtZero: true,
        },
      },
    },
  });
}

function createSizeChart(data) {
  const ctx = document.getElementById("sizeChart").getContext("2d");
  const colors = ["#FF6384", "#36A2EB", "#FFCE56", "#4BC0C0", "#9966FF"];

  charts.size = new Chart(ctx, {
    type: "pie",
    data: {
      labels: data.map((d) => d.range),
      datasets: [
        {
          data: data.map((d) => d.count),
          backgroundColor: colors.slice(0, data.length),
          borderWidth: 2,
          borderColor: "#fff",
        },
      ],
    },
    options: {
      responsive: true,
      plugins: {
        legend: {
          position: "bottom",
        },
      },
    },
  });
}

function updateStatsCards(data) {
  // Toplam indirme sayısı
  const totalDownloads = data.platform_distribution.reduce(
    (sum, d) => sum + d.count,
    0
  );
  document.getElementById("totalDownloads").textContent =
    totalDownloads.toLocaleString();

  // Başarı oranı
  const totalSuccess = data.success_rates.reduce(
    (sum, d) => sum + d.successful,
    0
  );
  const totalAttempts = data.success_rates.reduce((sum, d) => sum + d.total, 0);
  const successRate =
    totalAttempts > 0 ? (totalSuccess / totalAttempts) * 100 : 0;
  document.getElementById("successRate").textContent =
    successRate.toFixed(1) + "%";

  // Ortalama dosya boyutu
  const avgFileSize = data.general_stats.avg_file_size;
  if (avgFileSize > 0) {
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(avgFileSize) / Math.log(k));
    const formattedSize =
      parseFloat((avgFileSize / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
    document.getElementById("avgFileSize").textContent = formattedSize;
  } else {
    document.getElementById("avgFileSize").textContent = "N/A";
  }

  // Ortalama işlem süresi
  const avgProcessingTime = data.general_stats.avg_processing_time;
  if (avgProcessingTime > 0) {
    document.getElementById("avgProcessingTime").textContent =
      avgProcessingTime.toFixed(1) + "s";
  } else {
    document.getElementById("avgProcessingTime").textContent = "N/A";
  }
}

function fetchData() {
  const search = document.getElementById("searchInput").value.trim();
  const platform = document.getElementById("platformFilter").value;
  const status = document.getElementById("statusFilter").value;
  const dateFrom = document.getElementById("dateFrom").value;
  const dateTo = document.getElementById("dateTo").value;

  let url = `/api/admin/downloads?page=${page}&page_size=${pageSize}`;
  if (search) url += `&search=${encodeURIComponent(search)}`;
  if (platform) url += `&platform=${platform}`;
  if (status) url += `&status=${status}`;
  if (dateFrom) url += `&date_from=${dateFrom}`;
  if (dateTo) url += `&date_to=${dateTo}`;
  if (sortBy) url += `&sort_by=${sortBy}`;
  if (sortDir) url += `&sort_dir=${sortDir}`;

  fetch(url)
    .then((res) => res.json())
    .then((data) => {
      if (!data.success) {
        showError(data.error || "Veri alınamadı.");
        return;
      }
      total = data.total;
      renderTable(data.data);
      renderPagination();
      hideError();
    })
    .catch((err) => showError("Veri alınamadı: " + err));
}

function renderTable(rows) {
  const tbody = document.getElementById("downloadsBody");
  tbody.innerHTML = "";
  if (!rows.length) {
    tbody.innerHTML =
      '<tr><td colspan="11" style="text-align:center; color:#888;">Kayıt bulunamadı.</td></tr>';
    return;
  }
  rows.forEach((row) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
            <td>${new Date(row.timestamp).toLocaleString("tr-TR")}</td>
            <td>${capitalize(row.platform)}</td>
            <td>${row.video_title || ""}</td>
            <td>${row.video_quality || ""}</td>
            <td>${formatFileSize(row.file_size)}</td>
            <td>${row.ip_address}</td>
            <td>${
              row.user_agent
                ? row.user_agent.slice(0, 30) +
                  (row.user_agent.length > 30 ? "..." : "")
                : ""
            }</td>
            <td class="status-${row.status}">${
      row.status === "success" ? "Başarılı" : "Hatalı"
    }</td>
            <td>${
              row.processing_time ? row.processing_time.toFixed(1) : ""
            }</td>
            <td style="max-width:180px; overflow-x:auto;">${
              row.error_message
                ? row.error_message.slice(0, 60) +
                  (row.error_message.length > 60 ? "..." : "")
                : ""
            }</td>
            <td><a href="${
              row.link
            }" target="_blank" style="color:#667eea;">Link</a></td>
        `;
    tbody.appendChild(tr);
  });
}

function renderPagination() {
  const pag = document.getElementById("pagination");
  pag.innerHTML = "";
  const totalPages = Math.ceil(total / pageSize);
  if (totalPages <= 1) return;
  const createBtn = (p, text, disabled, current) => {
    const btn = document.createElement("button");
    btn.textContent = text;
    if (disabled) btn.disabled = true;
    if (current) btn.classList.add("current");
    btn.onclick = () => {
      page = p;
      fetchData();
    };
    return btn;
  };
  pag.appendChild(createBtn(1, "⏮", page === 1));
  for (
    let i = Math.max(1, page - 2);
    i <= Math.min(totalPages, page + 2);
    i++
  ) {
    pag.appendChild(createBtn(i, i, false, i === page));
  }
  pag.appendChild(createBtn(totalPages, "⏭", page === totalPages));
}

function showError(msg) {
  const el = document.getElementById("errorMessage");
  el.textContent = msg;
  el.style.display = "block";
}
function hideError() {
  document.getElementById("errorMessage").style.display = "none";
}
function formatFileSize(bytes) {
  if (!bytes) return "";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
}
function capitalize(str) {
  if (!str) return "";
  return str.charAt(0).toUpperCase() + str.slice(1).toLowerCase();
}

// İlk yükleme
loadCharts();
fetchData();

// DOM yüklendiğinde event listener'ları ekle
document.addEventListener("DOMContentLoaded", function () {
  // Event listeners
  document.getElementById("searchInput").addEventListener("input", () => {
    page = 1;
    fetchData();
  });
  document.getElementById("platformFilter").addEventListener("change", () => {
    page = 1;
    fetchData();
  });
  document.getElementById("statusFilter").addEventListener("change", () => {
    page = 1;
    fetchData();
  });
  document.getElementById("dateFrom").addEventListener("change", () => {
    page = 1;
    fetchData();
  });
  document.getElementById("dateTo").addEventListener("change", () => {
    page = 1;
    fetchData();
  });

  // Sıralama
  document.querySelectorAll("th.sortable").forEach((th) => {
    th.addEventListener("click", function () {
      const sortField = this.getAttribute("data-sort");
      if (sortBy === sortField) {
        sortDir = sortDir === "asc" ? "desc" : "asc";
      } else {
        sortBy = sortField;
        sortDir = "asc";
      }
      fetchData();
    });
  });
});
