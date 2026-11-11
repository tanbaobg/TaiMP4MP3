// TaiMP4MP3 Client Application
document.addEventListener('DOMContentLoaded', () => {
  // Initialize Lucide icons
  if (window.lucide) {
    window.lucide.createIcons();
  }

  // --- State & Config ---
  const DEFAULT_API = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
    ? 'http://localhost:8000'
    : window.location.origin;

  let currentApiBase = localStorage.getItem('TAIMP4MP3_API') || DEFAULT_API;
  let currentMediaData = null;
  let currentFilter = 'all'; // 'all', 'video', 'audio'
  let deferredInstallPrompt = null;

  // Trimmer State
  let trimMode = 'keep'; // 'keep' (lấy đoạn) or 'remove' (bỏ đoạn)
  let trimStartSec = 0;
  let trimEndSec = 30;
  let currentDirectStreamUrl = '';
  let activeTrimPreviewTimer = null;

  // --- DOM Elements ---
  const form = document.getElementById('form-analyze');
  const inputUrl = document.getElementById('input-url');
  const btnClearUrl = document.getElementById('btn-clear-url');
  const btnPasteUrl = document.getElementById('btn-paste-url');
  const btnSubmit = document.getElementById('btn-submit');
  const platformIndicator = document.getElementById('platform-indicator');
  const platformText = document.getElementById('platform-text');
  
  const loadingSpinner = document.getElementById('loading-spinner');
  const errorBox = document.getElementById('error-box');
  const errorMessage = document.getElementById('error-message');
  const btnCloseError = document.getElementById('btn-close-error');

  const resultContainer = document.getElementById('result-container');
  const resThumbnail = document.getElementById('res-thumbnail');
  const resDuration = document.getElementById('res-duration');
  const resTitle = document.getElementById('res-title');
  const resAuthor = document.getElementById('res-author');
  const resPlatformBadge = document.getElementById('res-platform-badge');
  const formatsGrid = document.getElementById('formats-grid');
  const formatTabs = document.querySelectorAll('.format-tab');

  // In-Page Player & Trimmer Elements
  const inlineVideoPlayer = document.getElementById('inline-video-player');
  const playerTimeDisplay = document.getElementById('player-time-display');
  const btnModeKeep = document.getElementById('btn-mode-keep');
  const btnModeRemove = document.getElementById('btn-mode-remove');
  const trimStartTimeInput = document.getElementById('trim-start-time');
  const trimEndTimeInput = document.getElementById('trim-end-time');
  const btnSetStartCurr = document.getElementById('btn-set-start-curr');
  const btnSetEndCurr = document.getElementById('btn-set-end-curr');
  const trimDurationBadge = document.getElementById('trim-duration-badge');
  const trimModeDesc = document.getElementById('trim-mode-desc');
  const btnPreviewTrimSegment = document.getElementById('btn-preview-trim-segment');
  const btnDownloadTrimMp4 = document.getElementById('btn-download-trim-mp4');
  const btnDownloadTrimMp3 = document.getElementById('btn-download-trim-mp3');
  const trimLoading = document.getElementById('trim-loading');

  const btnPreviewMedia = document.getElementById('btn-preview-media');
  const modalPreview = document.getElementById('modal-preview');
  const previewPlayer = document.getElementById('preview-video-player');
  const previewTitle = document.getElementById('preview-title');
  const btnClosePreview = document.getElementById('btn-close-preview');

  const modalHistory = document.getElementById('modal-history');
  const historyList = document.getElementById('history-list');
  const btnOpenHistory = document.getElementById('btn-open-history');
  const btnCloseHistory = document.getElementById('btn-close-history');
  const btnClearHistory = document.getElementById('btn-clear-history');

  const modalSettings = document.getElementById('modal-settings');
  const inputApiUrl = document.getElementById('input-api-url');
  const btnOpenSettings = document.getElementById('btn-open-settings');
  const btnCloseSettings = document.getElementById('btn-close-settings');
  const btnSaveSettings = document.getElementById('btn-save-settings');
  const btnTestApi = document.getElementById('btn-test-api');
  const apiStatusDot = document.getElementById('api-status-dot');

  const btnPwaInstall = document.getElementById('btn-pwa-install');

  // --- Platform Detection Utility ---
  function detectPlatform(url) {
    const val = url.toLowerCase();
    if (val.includes('tiktok.com') || val.includes('douyin.com')) {
      return { name: 'TikTok', color: 'pink', badge: 'TikTok Không Logo' };
    }
    if (val.includes('youtube.com') || val.includes('youtu.be')) {
      return { name: 'YouTube', color: 'red', badge: 'YouTube MP4/MP3' };
    }
    if (val.includes('facebook.com') || val.includes('fb.watch') || val.includes('fb.com')) {
      return { name: 'Facebook', color: 'blue', badge: 'Facebook Full HD' };
    }
    if (val.includes('instagram.com')) {
      return { name: 'Instagram', color: 'purple', badge: 'Instagram Video' };
    }
    if (val.includes('twitter.com') || val.includes('x.com')) {
      return { name: 'Twitter / X', color: 'slate', badge: 'Twitter/X Media' };
    }
    return null;
  }

  // --- Time Helpers ---
  function secondsToTimeCode(sec) {
    const s = Math.max(0, Math.floor(sec || 0));
    const m = Math.floor(s / 60);
    const h = Math.floor(m / 60);
    const remM = m % 60;
    const remS = s % 60;
    return `${String(h).padStart(2, '0')}:${String(remM).padStart(2, '0')}:${String(remS).padStart(2, '0')}`;
  }

  function timeCodeToSeconds(code) {
    if (!code) return 0;
    const parts = String(code).trim().split(':').map(Number);
    if (parts.length === 3) {
      return (parts[0] || 0) * 3600 + (parts[1] || 0) * 60 + (parts[2] || 0);
    }
    if (parts.length === 2) {
      return (parts[0] || 0) * 60 + (parts[1] || 0);
    }
    return Math.max(0, parseFloat(code) || 0);
  }

  function updateTrimSummary() {
    const totalDur = currentMediaData?.duration_seconds || inlineVideoPlayer.duration || 60;
    trimStartSec = timeCodeToSeconds(trimStartTimeInput.value);
    trimEndSec = timeCodeToSeconds(trimEndTimeInput.value);

    if (trimEndSec <= trimStartSec) {
      trimEndSec = Math.min(trimStartSec + 30, totalDur);
      trimEndTimeInput.value = secondsToTimeCode(trimEndSec);
    }

    if (trimMode === 'keep') {
      const segmentDur = Math.max(0, trimEndSec - trimStartSec);
      trimDurationBadge.textContent = `Thời lượng lấy: ${secondsToTimeCode(segmentDur)}`;
      trimModeDesc.textContent = `(Sẽ trích xuất đoạn từ ${secondsToTimeCode(trimStartSec)} đến ${secondsToTimeCode(trimEndSec)})`;
    } else {
      const remainingDur = Math.max(0, totalDur - (trimEndSec - trimStartSec));
      trimDurationBadge.textContent = `Thời lượng còn lại: ~${secondsToTimeCode(remainingDur)}`;
      trimModeDesc.textContent = `(Sẽ cắt bỏ đoạn từ ${secondsToTimeCode(trimStartSec)} đến ${secondsToTimeCode(trimEndSec)}, ghép phần trước & sau)`;
    }
  }

  // --- Real-time Input Validation & UI Updates ---
  inputUrl.addEventListener('input', () => {
    const text = inputUrl.value.trim();
    btnClearUrl.classList.toggle('hidden', text.length === 0);

    const platform = detectPlatform(text);
    if (platform) {
      platformIndicator.classList.remove('hidden');
      platformText.textContent = `Phát hiện: ${platform.name} (${platform.badge})`;
    } else {
      platformIndicator.classList.add('hidden');
    }
  });

  btnClearUrl.addEventListener('click', () => {
    inputUrl.value = '';
    btnClearUrl.classList.add('hidden');
    platformIndicator.classList.add('hidden');
    inputUrl.focus();
  });

  // --- Clipboard Auto Paste ---
  btnPasteUrl.addEventListener('click', async () => {
    try {
      if (navigator.clipboard && navigator.clipboard.readText) {
        const text = await navigator.clipboard.readText();
        if (text) {
          inputUrl.value = text.trim();
          inputUrl.dispatchEvent(new Event('input'));
          showNotification('Đã dán liên kết từ bộ nhớ tạm');
        }
      } else {
        inputUrl.focus();
      }
    } catch {
      inputUrl.focus();
    }
  });

  // --- Form Submit (Analyze Media) ---
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const url = inputUrl.value.trim();
    if (!url) {
      showError('Vui lòng nhập hoặc dán đường dẫn URL cần tải');
      return;
    }
    startAnalysis(url);
  });

  async function startAnalysis(targetUrl) {
    hideError();
    resultContainer.classList.add('hidden');
    loadingSpinner.classList.remove('hidden');
    btnSubmit.disabled = true;
    btnSubmit.classList.add('opacity-70');

    try {
      const apiUrl = `${currentApiBase.replace(/\/$/, '')}/api/analyze`;
      const response = await fetch(apiUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json'
        },
        body: JSON.stringify({ url: targetUrl })
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Lỗi kết nối máy chủ' }));
        throw new Error(errorData.detail || 'Không thể bóc tách liên kết');
      }

      const data = await response.json();
      currentMediaData = data;
      renderResult(data);
      saveToHistory(data);

    } catch (err) {
      console.error('Fetch error:', err);
      showError(err.message || 'Không thể phân tích video. Vui lòng kiểm tra lại đường dẫn hoặc cấu hình API.');
    } finally {
      loadingSpinner.classList.add('hidden');
      btnSubmit.disabled = false;
      btnSubmit.classList.remove('opacity-70');
    }
  }

  // --- Render Result Card with In-Page Player & Trimmer ---
  function renderResult(data) {
    resThumbnail.src = data.thumbnail || 'https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=500&auto=format&fit=crop&q=60';
    resDuration.textContent = data.duration_str || 'Video';
    resTitle.textContent = data.title;
    resAuthor.querySelector('span').textContent = data.author || 'Tác giả';

    // Platform Badge
    const platform = detectPlatform(data.url) || { name: data.platform.toUpperCase(), color: 'blue' };
    resPlatformBadge.textContent = platform.name;

    // Find best stream for In-Page Preview & Trimmer
    const firstVideoFormat = data.formats.find((f) => f.type === 'video' && (f.direct_url || f.proxy_url));
    const firstAudioFormat = data.formats.find((f) => f.type === 'audio' && (f.direct_url || f.proxy_url));
    const streamTarget = firstVideoFormat || firstAudioFormat;

    if (streamTarget) {
      currentDirectStreamUrl = streamTarget.direct_url || streamTarget.proxy_url;
      inlineVideoPlayer.src = currentDirectStreamUrl;
      inlineVideoPlayer.load();

      // Initialize Trimmer values
      const dur = data.duration_seconds || 30;
      trimStartSec = 0;
      trimEndSec = Math.min(dur, 30);
      trimStartTimeInput.value = secondsToTimeCode(0);
      trimEndTimeInput.value = secondsToTimeCode(trimEndSec);
      updateTrimSummary();
    }

    renderFormats();
    resultContainer.classList.remove('hidden');

    if (window.lucide) {
      window.lucide.createIcons();
    }

    // Smooth scroll down to result
    resultContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  // --- In-Page Player Time Tracker ---
  inlineVideoPlayer.addEventListener('timeupdate', () => {
    const cur = secondsToTimeCode(inlineVideoPlayer.currentTime);
    const dur = secondsToTimeCode(inlineVideoPlayer.duration || currentMediaData?.duration_seconds || 0);
    playerTimeDisplay.textContent = `${cur} / ${dur}`;
  });

  // --- Trimmer Controls ---
  btnSetStartCurr.addEventListener('click', () => {
    trimStartSec = inlineVideoPlayer.currentTime || 0;
    trimStartTimeInput.value = secondsToTimeCode(trimStartSec);
    updateTrimSummary();
    showNotification(`Đã đặt Bắt đầu: ${secondsToTimeCode(trimStartSec)}`);
  });

  btnSetEndCurr.addEventListener('click', () => {
    trimEndSec = inlineVideoPlayer.currentTime || 0;
    trimEndTimeInput.value = secondsToTimeCode(trimEndSec);
    updateTrimSummary();
    showNotification(`Đã đặt Kết thúc: ${secondsToTimeCode(trimEndSec)}`);
  });

  trimStartTimeInput.addEventListener('change', updateTrimSummary);
  trimEndTimeInput.addEventListener('change', updateTrimSummary);

  // Mode Toggle: Keep (Lấy) vs Remove (Bỏ)
  btnModeKeep.addEventListener('click', () => {
    trimMode = 'keep';
    btnModeKeep.className = 'px-3 py-1.5 text-xs font-bold rounded-md bg-blue-600 text-white shadow-sm flex items-center gap-1.5 transition-all';
    btnModeRemove.className = 'px-3 py-1.5 text-xs font-semibold rounded-md text-slate-400 hover:text-white flex items-center gap-1.5 transition-all';
    updateTrimSummary();
  });

  btnModeRemove.addEventListener('click', () => {
    trimMode = 'remove';
    btnModeRemove.className = 'px-3 py-1.5 text-xs font-bold rounded-md bg-rose-600 text-white shadow-sm flex items-center gap-1.5 transition-all';
    btnModeKeep.className = 'px-3 py-1.5 text-xs font-semibold rounded-md text-slate-400 hover:text-white flex items-center gap-1.5 transition-all';
    updateTrimSummary();
  });

  // Preview Trim Segment
  btnPreviewTrimSegment.addEventListener('click', () => {
    updateTrimSummary();
    if (!inlineVideoPlayer.src) {
      showNotification('Chưa tải được nguồn video để phát thử');
      return;
    }

    if (activeTrimPreviewTimer) {
      clearInterval(activeTrimPreviewTimer);
      activeTrimPreviewTimer = null;
    }

    if (trimMode === 'keep') {
      inlineVideoPlayer.currentTime = trimStartSec;
      inlineVideoPlayer.play().catch(() => {});
      showNotification(`Đang phát thử đoạn từ ${secondsToTimeCode(trimStartSec)} đến ${secondsToTimeCode(trimEndSec)}`);

      activeTrimPreviewTimer = setInterval(() => {
        if (inlineVideoPlayer.currentTime >= trimEndSec) {
          inlineVideoPlayer.pause();
          clearInterval(activeTrimPreviewTimer);
          activeTrimPreviewTimer = null;
          showNotification('Đã phát xong đoạn đã chọn!');
        }
      }, 250);
    } else {
      // Mode remove: play from 0, jump across cut segment
      inlineVideoPlayer.currentTime = 0;
      inlineVideoPlayer.play().catch(() => {});
      showNotification(`Đang phát thử: sẽ tự động bỏ qua đoạn từ ${secondsToTimeCode(trimStartSec)} đến ${secondsToTimeCode(trimEndSec)}`);

      activeTrimPreviewTimer = setInterval(() => {
        if (inlineVideoPlayer.currentTime >= trimStartSec && inlineVideoPlayer.currentTime < trimEndSec) {
          inlineVideoPlayer.currentTime = trimEndSec;
          showNotification(`Đã nhảy qua đoạn cắt bỏ đến ${secondsToTimeCode(trimEndSec)}`);
        }
      }, 200);
    }
  });

  // Download Trimmed Media (MP4 / MP3)
  async function triggerTrimDownload(mediaType) {
    updateTrimSummary();
    if (!currentMediaData || !currentDirectStreamUrl) {
      showError('Không tìm thấy nguồn video hợp lệ để cắt');
      return;
    }

    trimLoading.classList.remove('hidden');
    const safeTitle = currentMediaData.title || 'video';
    const totalDuration = currentMediaData.duration_seconds || inlineVideoPlayer.duration || 60;

    const trimApiUrl = `${currentApiBase.replace(/\/$/, '')}/api/trim?url=${encodeURIComponent(currentDirectStreamUrl)}&start=${trimStartSec}&end=${trimEndSec}&mode=${trimMode}&type=${mediaType}&duration=${totalDuration}&title=${encodeURIComponent(safeTitle)}`;

    showNotification(`Bắt đầu xử lý cắt ${mediaType.toUpperCase()}...`);

    // Create invisible anchor to trigger file download stream
    const dlLink = document.createElement('a');
    dlLink.href = trimApiUrl;
    dlLink.setAttribute('download', '');
    document.body.appendChild(dlLink);
    dlLink.click();
    dlLink.remove();

    setTimeout(() => {
      trimLoading.classList.add('hidden');
      showNotification(`File ${mediaType.toUpperCase()} đã cắt đang được tải về!`);
    }, 3500);
  }

  btnDownloadTrimMp4.addEventListener('click', () => triggerTrimDownload('video'));
  btnDownloadTrimMp3.addEventListener('click', () => triggerTrimDownload('audio'));

  // --- Format Filter Tabs & Cards ---
  formatTabs.forEach((tab) => {
    tab.addEventListener('click', () => {
      formatTabs.forEach((t) => {
        t.classList.remove('bg-blue-600', 'text-white');
        t.classList.add('bg-slate-800', 'text-slate-400');
      });
      tab.classList.add('bg-blue-600', 'text-white');
      tab.classList.remove('bg-slate-800', 'text-slate-400');

      currentFilter = tab.getAttribute('data-filter');
      renderFormats();
    });
  });

  function renderFormats() {
    if (!currentMediaData || !currentMediaData.formats) return;

    formatsGrid.innerHTML = '';
    const formats = currentMediaData.formats.filter((f) => {
      if (currentFilter === 'video') return f.type === 'video';
      if (currentFilter === 'audio') return f.type === 'audio';
      return true;
    });

    if (formats.length === 0) {
      formatsGrid.innerHTML = `
        <div class="col-span-full py-8 text-center text-slate-500 text-xs">
          Không có định dạng nào phù hợp với bộ lọc đã chọn.
        </div>
      `;
      return;
    }

    formats.forEach((fmt) => {
      const isAudio = fmt.type === 'audio';
      const isNoWm = fmt.id.includes('nowatermark');
      const targetDownloadUrl = fmt.proxy_url || fmt.direct_url;

      const card = document.createElement('div');
      card.className = 'glass-card rounded-xl p-3.5 flex items-center justify-between gap-3 transition-all';

      card.innerHTML = `
        <div class="flex items-center gap-3 min-w-0">
          <div class="w-10 h-10 rounded-lg ${isAudio ? 'bg-amber-500/10 text-amber-400' : isNoWm ? 'bg-emerald-500/10 text-emerald-400' : 'bg-blue-500/10 text-blue-400'} flex items-center justify-center shrink-0">
            <i data-lucide="${isAudio ? 'music' : 'video'}" class="w-5 h-5"></i>
          </div>
          <div class="min-w-0">
            <div class="flex items-center gap-1.5 flex-wrap">
              <span class="text-sm font-bold text-white truncate">${fmt.quality}</span>
              ${isNoWm ? '<span class="px-1.5 py-0.2 text-[9px] font-extrabold bg-emerald-500/20 text-emerald-300 rounded border border-emerald-500/30">NO-LOGO</span>' : ''}
            </div>
            <div class="flex items-center gap-2 text-[11px] text-slate-400 mt-0.5">
              <span>Định dạng: <strong class="uppercase text-slate-300">${fmt.ext}</strong></span>
              ${fmt.filesize_str ? `<span>• ${fmt.filesize_str}</span>` : ''}
            </div>
          </div>
        </div>

        <div class="flex items-center gap-1.5 shrink-0">
          <button 
            type="button" 
            data-url="${targetDownloadUrl}" 
            class="btn-copy-format p-2 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition-colors" 
            title="Sao chép link tải"
          >
            <i data-lucide="copy" class="w-4 h-4"></i>
          </button>

          <a 
            href="${targetDownloadUrl}" 
            target="_blank" 
            rel="noopener noreferrer" 
            download="${currentMediaData.title}.${fmt.ext}"
            class="px-3 py-1.5 text-xs font-bold rounded-lg bg-blue-600 hover:bg-blue-500 text-white flex items-center gap-1.5 shadow-md shadow-blue-500/20 transition-transform active:scale-95"
          >
            <i data-lucide="download" class="w-3.5 h-3.5"></i>
            <span>Tải về</span>
          </a>
        </div>
      `;

      formatsGrid.appendChild(card);
    });

    if (window.lucide) {
      window.lucide.createIcons();
    }

    document.querySelectorAll('.btn-copy-format').forEach((btn) => {
      btn.addEventListener('click', async () => {
        const urlToCopy = btn.getAttribute('data-url');
        if (urlToCopy) {
          await navigator.clipboard.writeText(urlToCopy);
          showNotification('Đã sao chép link tải trực tiếp vào bộ nhớ tạm');
        }
      });
    });
  }

  // --- Preview Player Modal (Secondary) ---
  btnPreviewMedia.addEventListener('click', () => {
    if (!currentMediaData) return;
    const firstVideo = currentMediaData.formats.find((f) => f.type === 'video' && (f.direct_url || f.proxy_url));
    if (firstVideo) {
      previewTitle.textContent = currentMediaData.title;
      previewPlayer.src = firstVideo.direct_url || firstVideo.proxy_url;
      modalPreview.classList.remove('hidden');
      previewPlayer.play().catch(() => {});
    } else {
      showNotification('Không có nguồn video để xem trước');
    }
  });

  btnClosePreview.addEventListener('click', () => {
    previewPlayer.pause();
    previewPlayer.src = '';
    modalPreview.classList.add('hidden');
  });

  modalPreview.addEventListener('click', (e) => {
    if (e.target === modalPreview) {
      btnClosePreview.click();
    }
  });

  // --- Error Helper ---
  function showError(msg) {
    errorMessage.textContent = msg;
    errorBox.classList.remove('hidden');
    if (window.lucide) window.lucide.createIcons();
  }

  function hideError() {
    errorBox.classList.add('hidden');
  }

  btnCloseError.addEventListener('click', hideError);

  // --- History Management (localStorage) ---
  const HISTORY_KEY = 'taimp4mp3_history';

  function getHistory() {
    try {
      return JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]');
    } catch {
      return [];
    }
  }

  function saveToHistory(media) {
    let history = getHistory();
    history = history.filter((item) => item.url !== media.url);
    history.unshift({
      title: media.title,
      url: media.url,
      thumbnail: media.thumbnail,
      author: media.author,
      duration: media.duration_str,
      time: new Date().toLocaleDateString('vi-VN')
    });
    if (history.length > 30) history = history.slice(0, 30);
    localStorage.setItem(HISTORY_KEY, JSON.stringify(history));
  }

  function renderHistory() {
    const list = getHistory();
    historyList.innerHTML = '';

    if (list.length === 0) {
      historyList.innerHTML = `
        <div class="py-8 text-center text-slate-400 text-xs">
          Bạn chưa tải video nào gần đây.
        </div>
      `;
      return;
    }

    list.forEach((item) => {
      const el = document.createElement('div');
      el.className = 'glass-card p-2.5 rounded-xl flex items-center justify-between gap-3 hover:border-slate-600 transition-colors';
      el.innerHTML = `
        <div class="flex items-center gap-2.5 min-w-0">
          <img src="${item.thumbnail || ''}" class="w-12 h-8 rounded object-cover bg-slate-800 shrink-0">
          <div class="min-w-0">
            <h5 class="text-xs font-semibold text-white truncate">${item.title}</h5>
            <span class="text-[10px] text-slate-400">${item.author || ''} • ${item.time}</span>
          </div>
        </div>
        <button 
          data-url="${item.url}" 
          class="btn-reanalyze px-2.5 py-1 rounded bg-blue-600/20 text-blue-400 border border-blue-500/30 text-[11px] font-semibold hover:bg-blue-600/30 shrink-0"
        >
          Tải lại
        </button>
      `;
      historyList.appendChild(el);
    });

    document.querySelectorAll('.btn-reanalyze').forEach((btn) => {
      btn.addEventListener('click', () => {
        const u = btn.getAttribute('data-url');
        inputUrl.value = u;
        inputUrl.dispatchEvent(new Event('input'));
        modalHistory.classList.add('hidden');
        startAnalysis(u);
      });
    });
  }

  btnOpenHistory.addEventListener('click', () => {
    renderHistory();
    modalHistory.classList.remove('hidden');
    if (window.lucide) window.lucide.createIcons();
  });

  btnCloseHistory.addEventListener('click', () => {
    modalHistory.classList.add('hidden');
  });

  btnClearHistory.addEventListener('click', () => {
    if (confirm('Bạn có chắc muốn xóa toàn bộ lịch sử đã tải?')) {
      localStorage.removeItem(HISTORY_KEY);
      renderHistory();
    }
  });

  // --- Settings Modal ---
  btnOpenSettings.addEventListener('click', () => {
    inputApiUrl.value = currentApiBase;
    modalSettings.classList.remove('hidden');
  });

  btnCloseSettings.addEventListener('click', () => {
    modalSettings.classList.add('hidden');
  });

  btnSaveSettings.addEventListener('click', () => {
    const val = inputApiUrl.value.trim().replace(/\/$/, '');
    if (val) {
      currentApiBase = val;
      localStorage.setItem('TAIMP4MP3_API', val);
      showNotification('Đã lưu cấu hình API');
      modalSettings.classList.add('hidden');
    }
  });

  btnTestApi.addEventListener('click', async () => {
    apiStatusDot.className = 'w-2 h-2 rounded-full bg-amber-400 animate-ping';
    const testUrl = `${inputApiUrl.value.trim().replace(/\/$/, '')}/api/health`;
    try {
      const res = await fetch(testUrl, { method: 'GET', signal: AbortSignal.timeout(5000) });
      if (res.ok) {
        apiStatusDot.className = 'w-2 h-2 rounded-full bg-emerald-400';
        showNotification('Kết nối API thành công!');
      } else {
        throw new Error();
      }
    } catch {
      apiStatusDot.className = 'w-2 h-2 rounded-full bg-rose-500';
      showNotification('Không thể kết nối tới API!');
    }
  });

  // --- Toast Notification Helper ---
  function showNotification(text) {
    const toast = document.createElement('div');
    toast.className = 'fixed bottom-5 right-5 z-50 bg-slate-800 border border-slate-700 text-white text-xs px-4 py-2.5 rounded-xl shadow-2xl flex items-center gap-2 transform transition-all translate-y-5 opacity-0';
    toast.innerHTML = `<span class="w-2 h-2 rounded-full bg-blue-400"></span><span>${text}</span>`;
    document.body.appendChild(toast);

    setTimeout(() => {
      toast.classList.remove('translate-y-5', 'opacity-0');
    }, 10);

    setTimeout(() => {
      toast.classList.add('translate-y-5', 'opacity-0');
      setTimeout(() => toast.remove(), 300);
    }, 3000);
  }

  // --- PWA Installation Handler ---
  window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    deferredInstallPrompt = e;
    btnPwaInstall.classList.remove('hidden');
    btnPwaInstall.classList.add('inline-flex');
  });

  btnPwaInstall.addEventListener('click', async () => {
    if (!deferredInstallPrompt) return;
    deferredInstallPrompt.prompt();
    const { outcome } = await deferredInstallPrompt.userChoice;
    if (outcome === 'accepted') {
      btnPwaInstall.classList.add('hidden');
    }
    deferredInstallPrompt = null;
  });

  if ('serviceWorker' in navigator && window.location.protocol.startsWith('http')) {
    navigator.serviceWorker.register('/sw.js').catch(() => {});
  }

  // Auto-fill from URL Query Parameter
  const urlParams = new URLSearchParams(window.location.search);
  const sharedUrl = urlParams.get('url') || urlParams.get('text');
  if (sharedUrl) {
    const match = sharedUrl.match(/(https?:\/\/[^\s]+)/g);
    const finalUrl = match ? match[0] : sharedUrl;
    inputUrl.value = finalUrl;
    inputUrl.dispatchEvent(new Event('input'));
    startAnalysis(finalUrl);
  }
});
