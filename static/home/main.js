// index.html dosyasındaki <script>...</script> içeriği buraya taşınacak
let currentPlatform = "";
let selectedVideoIndex = -1;
let selectedAudioIndex = -1;
let currentVideoTitle = "";
let currentVideoQuality = "";

// İstatistikleri yükle
loadStatistics();

document.getElementById("convertBtn").addEventListener("click", processUrl);
document.getElementById("urlInput").addEventListener("keypress", function (e) {
  if (e.key === "Enter") {
    processUrl();
  }
});

async function processUrl() {
  const url = document.getElementById("urlInput").value.trim();
  if (!url) {
    showError("Lütfen bir link girin.");
    return;
  }
  const btn = document.getElementById("convertBtn");
  btn.disabled = true;
  btn.textContent = "İşleniyor...";
  document.getElementById("resultSection").style.display = "none";
  document.getElementById("success").style.display = "none";
  document.getElementById("progress").style.display = "none";
  try {
    const response = await fetch("/api/process", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ url }),
    });
    const data = await response.json();
    if (!response.ok) {
      if (data.error === "Desteklenmeyen platform.") {
        showError(
          "Bu platform henüz desteklenmiyor. Şu anda sadece YouTube, Instagram ve TikTok videoları indirilebilir."
        );
      } else {
        showError(data.error || "Bir hata oluştu.");
      }
      return;
    }
    if (data.success) {
      currentPlatform = data.platform;
      if (data.platform === "youtube") {
        showYouTubeInfo(data);
      } else if (data.platform === "instagram") {
        showInstagramInfo(data);
      } else if (data.platform === "tiktok") {
        showTikTokInfo(data);
      }
    } else {
      if (data.error === "Desteklenmeyen platform.") {
        showError(
          "Bu platform henüz desteklenmiyor. Şu anda sadece YouTube, Instagram ve TikTok videoları indirilebilir."
        );
      } else {
        showError(data.error);
      }
    }
  } catch (error) {
    showError("Bir hata oluştu: " + error.message);
  } finally {
    btn.disabled = false;
    btn.textContent = "Video Bilgilerini Getir";
  }
}
// --- Tüm script fonksiyonları buraya eklenecek ---
function showYouTubeInfo(data) {
  document.getElementById("error").style.display = "none";
  currentVideoTitle = data.title;
  const titleEl = document.getElementById("videoTitle");
  titleEl.textContent = data.title;
  if (data.thumbnail_url) {
    const thumbnailEl = document.getElementById("thumbnail");
    thumbnailEl.src = data.thumbnail_url;
    thumbnailEl.style.display = "block";
  }
  const qualityOptions = document.getElementById("qualityOptions");
  qualityOptions.innerHTML = "";
  data.video_streams.forEach((stream, index) => {
    const btn = document.createElement("button");
    btn.className = "quality-btn";
    const sizeStr = stream.size_mb ? `${stream.size_mb}MB` : "Bilinmiyor";
    const adaptiveStr = stream.is_progressive ? "" : " (Adaptive)";
    btn.textContent = `${stream.resolution} (${sizeStr})${adaptiveStr}`;
    btn.onclick = () =>
      selectQuality(index, stream.resolution, stream.is_progressive);
    qualityOptions.appendChild(btn);
  });
  if (data.audio_streams && data.audio_streams.length > 0) {
    const mp3Row = document.createElement("div");
    mp3Row.style.marginTop = "12px";
    mp3Row.style.display = "flex";
    mp3Row.style.gap = "10px";
    data.audio_streams.forEach((stream) => {
      if (stream.mp3_available) {
        const mp3Btn = document.createElement("button");
        mp3Btn.className = "quality-btn";
        const sizeStr = stream.size_mb ? ` (${stream.size_mb}MB)` : "";
        mp3Btn.textContent = `${stream.abr} (MP3)${sizeStr}`;
        mp3Btn.onclick = () => {
          selectedVideoIndex = null;
          selectedAudioIndex = stream.index;
          window.selectedMp3 = true;
          document
            .querySelectorAll(".quality-btn")
            .forEach((btn) => btn.classList.remove("selected"));
          mp3Btn.classList.add("selected");
          document.getElementById("audioOptions").style.display = "none";
          const downloadBtn = document.getElementById("downloadBtn");
          downloadBtn.style.display = "block";
          downloadBtn.onclick = () => downloadVideo();
        };
        mp3Row.appendChild(mp3Btn);
      }
    });
    qualityOptions.appendChild(document.createElement("br"));
    qualityOptions.appendChild(mp3Row);
  }
  window.audioStreams = data.audio_streams || [];
  document.getElementById("resultSection").style.display = "block";
}
function showInstagramInfo(data) {
  document.getElementById("error").style.display = "none";
  const titleEl = document.getElementById("videoTitle");
  titleEl.textContent = data.title || "Instagram Video";
  const thumbnailEl = document.getElementById("thumbnail");
  if (data.thumbnail_url && data.thumbnail_url.startsWith("data:")) {
    thumbnailEl.src = data.thumbnail_url;
    thumbnailEl.style.display = "block";
    thumbnailEl.onerror = function () {
      showDefaultInstagramThumbnail();
    };
    thumbnailEl.onload = function () {};
  } else {
    showDefaultInstagramThumbnail();
  }
  const videoInfo = document.getElementById("videoInfo");
  const infoDiv = document.createElement("div");
  infoDiv.style.cssText =
    "text-align: center; margin: 20px 0; padding: 15px; background: rgba(255,255,255,0.5); border-radius: 10px;";
  let infoText = "📱 Instagram Video";
  if (data.duration) {
    const minutes = Math.floor(data.duration / 60);
    const seconds = data.duration % 60;
    infoText += ` • ${minutes}:${seconds.toString().padStart(2, "0")}`;
  }
  if (data.uploader) {
    infoText += ` • @${data.uploader}`;
  }
  infoDiv.innerHTML = infoText;
  videoInfo.appendChild(infoDiv);
  document.getElementById("resultSection").style.display = "block";
  const downloadBtn = document.getElementById("downloadBtn");
  downloadBtn.style.display = "block";
  downloadBtn.onclick = () => downloadVideo();
}
function showDefaultInstagramThumbnail() {
  const thumbnailEl = document.getElementById("thumbnail");
  thumbnailEl.style.display = "block";
  thumbnailEl.style.background =
    "linear-gradient(135deg, #667eea 0%, #764ba2 100%)";
  thumbnailEl.style.border = "none";
  thumbnailEl.style.width = "300px";
  thumbnailEl.style.height = "200px";
  thumbnailEl.style.objectFit = "cover";
  thumbnailEl.style.borderRadius = "15px";
  const placeholderDiv = document.createElement("div");
  placeholderDiv.style.cssText = `width: 300px; height: 200px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 15px; display: flex; flex-direction: column; align-items: center; justify-content: center; color: white; font-size: 48px; margin: 0 auto 20px; box-shadow: 0 8px 25px rgba(0,0,0,0.15);`;
  placeholderDiv.innerHTML = `<div style="font-size: 48px; margin-bottom: 10px;">📱</div><div style="font-size: 16px; font-weight: 600;">Instagram Video</div>`;
  thumbnailEl.style.display = "none";
  const videoInfo = document.getElementById("videoInfo");
  videoInfo.insertBefore(placeholderDiv, videoInfo.firstChild);
}
function showTikTokInfo(data) {
  document.getElementById("error").style.display = "none";
  const titleEl = document.getElementById("videoTitle");
  titleEl.textContent = data.title || "TikTok Video";
  const thumbnailEl = document.getElementById("thumbnail");
  if (data.thumbnail_url && data.thumbnail_url.startsWith("data:")) {
    thumbnailEl.src = data.thumbnail_url;
    thumbnailEl.style.display = "block";
    thumbnailEl.onerror = function () {
      showDefaultTikTokThumbnail();
    };
    thumbnailEl.onload = function () {};
  } else {
    showDefaultTikTokThumbnail();
  }
  const videoInfo = document.getElementById("videoInfo");
  const infoDiv = document.createElement("div");
  infoDiv.style.cssText =
    "text-align: center; margin: 20px 0; padding: 15px; background: rgba(255,255,255,0.5); border-radius: 10px;";
  let infoText = "🎵 TikTok Video";
  if (data.duration) {
    const minutes = Math.floor(data.duration / 60);
    const seconds = data.duration % 60;
    infoText += ` • ${minutes}:${seconds.toString().padStart(2, "0")}`;
  }
  if (data.uploader) {
    infoText += ` • @${data.uploader}`;
  }
  infoDiv.innerHTML = infoText;
  videoInfo.appendChild(infoDiv);
  document.getElementById("resultSection").style.display = "block";
  const downloadBtn = document.getElementById("downloadBtn");
  downloadBtn.style.display = "block";
  downloadBtn.onclick = () => downloadVideo();
}
function showDefaultTikTokThumbnail() {
  const thumbnailEl = document.getElementById("thumbnail");
  thumbnailEl.style.display = "block";
  thumbnailEl.style.background =
    "linear-gradient(135deg, #667eea 0%, #764ba2 100%)";
  thumbnailEl.style.border = "none";
  thumbnailEl.style.width = "300px";
  thumbnailEl.style.height = "200px";
  thumbnailEl.style.objectFit = "cover";
  thumbnailEl.style.borderRadius = "15px";
  const placeholderDiv = document.createElement("div");
  placeholderDiv.style.cssText = `width: 300px; height: 200px; background: linear-gradient(135deg, #000000 0%, #333333 100%); border-radius: 15px; display: flex; flex-direction: column; align-items: center; justify-content: center; color: white; font-size: 48px; margin: 0 auto 20px; box-shadow: 0 8px 25px rgba(0,0,0,0.15);`;
  placeholderDiv.innerHTML = `<div style=\"font-size: 48px; margin-bottom: 10px;\">🎵</div><div style=\"font-size: 16px; font-weight: 600;\">TikTok Video</div>`;
  thumbnailEl.style.display = "none";
  const videoInfo = document.getElementById("videoInfo");
  videoInfo.insertBefore(placeholderDiv, videoInfo.firstChild);
}
function selectQuality(index, quality, isProgressive) {
  selectedVideoIndex = index + 1;
  currentVideoQuality = quality;
  document.querySelectorAll(".quality-btn").forEach((btn) => {
    btn.classList.remove("selected");
  });
  event.target.classList.add("selected");
  if (currentPlatform === "youtube" && !isProgressive) {
    showAudioOptions();
  }
  const downloadBtn = document.getElementById("downloadBtn");
  downloadBtn.style.display = "block";
  downloadBtn.onclick = () => downloadVideo();
}
function showAudioOptions() {
  const audioOptions = document.getElementById("audioOptions");
  audioOptions.style.display = "block";
  audioOptions.innerHTML = "<p>Ses kalitesi seçin:</p>";
  if (window.audioStreams && window.audioStreams.length > 0) {
    window.audioStreams.forEach((stream, index) => {
      const btn = document.createElement("button");
      btn.className = "quality-btn";
      const sizeStr = stream.size_mb ? `${stream.size_mb}MB` : "Bilinmiyor";
      btn.textContent = `${stream.abr} (${sizeStr})`;
      btn.onclick = () => {
        selectedAudioIndex = stream.index;
        document
          .querySelectorAll("#audioOptions .quality-btn")
          .forEach((b) => b.classList.remove("selected"));
        btn.classList.add("selected");
        window.selectedMp3 = false;
      };
      audioOptions.appendChild(btn);
    });
  } else {
    audioOptions.innerHTML +=
      '<p style="text-align: center; color: #6c757d; font-style: italic;">Ses stream\'leri bulunamadı.</p>';
  }
}
async function downloadVideo() {
  const url = document.getElementById("urlInput").value.trim();
  const downloadBtn = document.getElementById("downloadBtn");
  const progress = document.getElementById("progress");
  const videoInfo = document.getElementById("videoInfo");
  videoInfo.style.display = "none";
  progress.style.display = "block";
  downloadBtn.disabled = true;
  startFakeProgress();
  try {
    const response = await fetch("/api/convert", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        url: url,
        platform: currentPlatform,
        video_index: selectedVideoIndex,
        audio_index: selectedAudioIndex,
        video_title: currentVideoTitle,
        video_quality: currentVideoQuality,
        mp3: window.selectedMp3 === true,
      }),
    });
    const data = await response.json();
    if (data.success) {
      completeProgress();
      setTimeout(() => {
        showSuccess(
          `Video başarıyla indirildi! <a href="${data.download_url}" class="download-link">İndir</a><br><small>${data.info}</small>`,
          data.download_url,
          data.file_type
        );
        progress.style.display = "none";
        loadStatistics();
      }, 500);
    } else {
      progress.style.display = "none";
      videoInfo.style.display = "block";
      showError(data.error);
    }
  } catch (error) {
    progress.style.display = "none";
    videoInfo.style.display = "block";
    showError("İndirme sırasında hata oluştu: " + error.message);
  } finally {
    downloadBtn.disabled = false;
  }
}
function startFakeProgress() {
  const progressBar = document.getElementById("progressBar");
  let progress = 0;
  const duration = 3000 + Math.random() * 4000;
  const interval = 50;
  const steps = duration / interval;
  let currentStep = 0;
  const updateProgress = () => {
    currentStep++;
    const progressRatio = currentStep / steps;
    const slowFactor = Math.max(0.1, 1 - progressRatio * 0.7);
    const increment = (100 / steps) * slowFactor;
    progress += increment;
    if (progress < 95) {
      progressBar.style.width = progress + "%";
      document.getElementById("progressText").textContent =
        Math.round(progress) + "%";
      setTimeout(updateProgress, interval);
    }
  };
  updateProgress();
}
function completeProgress() {
  const progressBar = document.getElementById("progressBar");
  const progressText = document.getElementById("progressText");
  progressBar.style.width = "100%";
  progressBar.style.transition = "width 0.3s ease";
  progressText.textContent = "100%";
}
async function loadStatistics() {
  try {
    const response = await fetch("/api/statistics");
    const data = await response.json();
    if (data.success) {
      showStatistics(data);
    }
  } catch (error) {
    console.error("İstatistikler yüklenemedi:", error);
  }
}
function showStatistics(data) {
  const statsGrid = document.getElementById("statsGrid");
  const total = data.total_statistics;
  statsGrid.innerHTML = `
        <div class="stat-card">
            <div class="stat-number">${total.total_downloads}</div>
            <div class="stat-label">Toplam İndirme</div>
        </div>
        <div class="stat-card">
            <div class="stat-number">${total.successful_downloads}</div>
            <div class="stat-label">Başarılı</div>
        </div>
        <div class="stat-card">
            <div class="stat-number">${total.failed_downloads}</div>
            <div class="stat-label">Başarısız</div>
        </div>
        <div class="stat-card">
            <div class="stat-number">${formatFileSize(
              total.total_file_size
            )}</div>
            <div class="stat-label">Toplam Boyut</div>
        </div>
        <div class="stat-card">
            <div class="stat-number">${
              total.avg_processing_time
                ? total.avg_processing_time.toFixed(1)
                : 0
            }s</div>
            <div class="stat-label">Ortalama Süre</div>
        </div>
    `;
  if (data.platform_statistics.length > 0) {
    const platformList = document.getElementById("platformList");
    platformList.innerHTML = "";
    data.platform_statistics.forEach((platform) => {
      const item = document.createElement("div");
      item.className = "platform-item";
      item.innerHTML = `
                <div>
                    <strong>${capitalize(platform.platform)}</strong>
                    <div style="font-size: 0.8em; color: #6c757d;">
                        ${platform.successful_downloads}/${
        platform.total_downloads
      } başarılı
                    </div>
                </div>
                <div style="text-align: right;">
                    <div>${formatFileSize(platform.total_file_size)}</div>
                    <div style="font-size: 0.8em; color: #6c757d;">
                        ${
                          platform.avg_processing_time
                            ? platform.avg_processing_time.toFixed(1)
                            : 0
                        }s
                    </div>
                </div>
            `;
      platformList.appendChild(item);
    });
    document.getElementById("platformStats").style.display = "block";
  }
}
function formatFileSize(bytes) {
  if (!bytes) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
}
function capitalize(str) {
  if (!str) return "";
  return str.charAt(0).toUpperCase() + str.slice(1).toLowerCase();
}
function showError(message) {
  const errorEl = document.getElementById("error");
  errorEl.textContent = message;
  errorEl.style.display = "block";
}
function showSuccess(message, downloadUrl = null, fileType = "video/mp4") {
  const successEl = document.getElementById("success");
  if (downloadUrl) {
    // Tüm indirme linklerinde safeDownload fonksiyonunu kullan
    message = message.replace(
      /<a href=\"([^\"]+)\" class=\"download-link\">İndir<\/a>/g,
      function (_, link) {
        return `<a href="#" class="download-link" onclick="event.preventDefault(); safeDownload('${link}');">İndir</a>`;
      }
    );
  }
  successEl.innerHTML = message;
  successEl.style.display = "block";
  if (downloadUrl && (fileType === "video/mp4" || fileType === "video")) {
    const oldPreview = document.getElementById("videoPreviewPanel");
    if (oldPreview) oldPreview.remove();
    const panel = document.createElement("div");
    panel.id = "videoPreviewPanel";
    panel.style.marginTop = "24px";
    panel.style.background = "var(--bg-card)";
    panel.style.borderRadius = "12px";
    panel.style.padding = "18px";
    panel.style.boxShadow = "0 2px 8px rgba(0,0,0,0.08)";
    panel.style.textAlign = "center";
    const video = document.createElement("video");
    video.id = "previewVideo";
    video.src = downloadUrl;
    video.controls = true;
    video.style.maxWidth = "100%";
    video.style.borderRadius = "8px";
    video.style.marginBottom = "18px";
    panel.appendChild(video);
    const controlsDiv = document.createElement("div");
    controlsDiv.style.display = "flex";
    controlsDiv.style.justifyContent = "center";
    controlsDiv.style.gap = "16px";
    controlsDiv.style.margin = "18px 0 10px 0";
    const startInput = document.createElement("input");
    startInput.type = "text";
    startInput.id = "cutStart";
    startInput.value = "00:00";
    startInput.style.width = "70px";
    startInput.style.textAlign = "center";
    startInput.style.marginRight = "4px";
    const setStartBtn = document.createElement("button");
    setStartBtn.textContent = "Başlangıcı Seç";
    setStartBtn.className = "convert-btn";
    setStartBtn.onclick = () => {
      const v = document.getElementById("previewVideo");
      startInput.value = secondsToTime(v.currentTime);
    };
    const endInput = document.createElement("input");
    endInput.type = "text";
    endInput.id = "cutEnd";
    endInput.value = "00:00";
    endInput.style.width = "70px";
    endInput.style.textAlign = "center";
    endInput.style.marginRight = "4px";
    const setEndBtn = document.createElement("button");
    setEndBtn.textContent = "Bitişi Seç";
    setEndBtn.className = "convert-btn";
    setEndBtn.onclick = () => {
      const v = document.getElementById("previewVideo");
      endInput.value = secondsToTime(v.currentTime);
    };
    controlsDiv.appendChild(startInput);
    controlsDiv.appendChild(setStartBtn);
    controlsDiv.appendChild(endInput);
    controlsDiv.appendChild(setEndBtn);
    panel.appendChild(controlsDiv);
    const cutBtn = document.createElement("button");
    cutBtn.textContent = "Cut";
    cutBtn.className = "download-btn";
    cutBtn.style.marginTop = "10px";
    cutBtn.onclick = () => cutVideo(downloadUrl);
    panel.appendChild(cutBtn);
    const cutProgress = document.createElement("div");
    cutProgress.id = "cutProgress";
    cutProgress.style.marginTop = "16px";
    panel.appendChild(cutProgress);
    video.onloadedmetadata = function () {
      endInput.value = secondsToTime(video.duration);
    };
    successEl.appendChild(panel);
  }
}
function secondsToTime(sec) {
  sec = Math.floor(sec);
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
}
function timeToSeconds(str) {
  if (!str) return 0;
  if (str.includes(":")) {
    const [m, s] = str.split(":").map(Number);
    return m * 60 + s;
  }
  return Number(str);
}
async function cutVideo(downloadUrl) {
  const start = document.getElementById("cutStart").value;
  const end = document.getElementById("cutEnd").value;
  const startSec = timeToSeconds(start);
  const endSec = timeToSeconds(end);
  if (isNaN(startSec) || isNaN(endSec) || startSec >= endSec) {
    alert("Başlangıç ve bitiş zamanlarını doğru giriniz.");
    return;
  }
  const fileIdMatch = downloadUrl.match(/\/download\/(.*?)(\.|$)/);
  const fileId = fileIdMatch ? fileIdMatch[1] : null;
  if (!fileId) {
    alert("Dosya ID bulunamadı!");
    return;
  }
  const cutProgress = document.getElementById("cutProgress");
  cutProgress.innerHTML =
    '<div class="loading"><div class="spinner"></div>Video kesiliyor...</div>';
  try {
    const response = await fetch("/api/cut", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ file_id: fileId, start: startSec, end: endSec }),
    });
    const data = await response.json();
    if (data.success) {
      cutProgress.innerHTML = `<div class="success">Kesilmiş video hazır! <a href="${data.download_url}" class="download-link">İndir</a></div>`;
    } else {
      cutProgress.innerHTML = `<div class="error">${data.error}</div>`;
    }
  } catch (e) {
    cutProgress.innerHTML = `<div class="error">Bir hata oluştu: ${e.message}</div>`;
  }
}
async function safeDownload(url) {
  try {
    // HEAD isteğiyle dosya hazır mı kontrol et
    const headResp = await fetch(url, { method: "HEAD" });
    if (headResp.ok) {
      const a = document.createElement("a");
      a.href = url;
      a.download = "";
      document.body.appendChild(a);
      a.click();
      setTimeout(() => document.body.removeChild(a), 100);
    } else {
      showError(
        "Dosya henüz hazır değil. Lütfen birkaç saniye sonra tekrar deneyin."
      );
    }
  } catch (e) {
    showError("İndirme sırasında hata oluştu. Lütfen tekrar deneyin.");
  }
}
