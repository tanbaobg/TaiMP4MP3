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

  // Multi-Segment Trimmer State
  let trimMode = 'keep'; // 'keep' (lấy các đoạn) or 'remove' (bỏ các đoạn)
  let segments = [
    { id: 1, start: 0, end: 30 }
  ];
  let segmentCounter = 1;
  let currentDirectStreamUrl = '';
  let activeTrimTimer = null;

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

  // In-Page Player & Multi-Segment Trimmer Elements
  const inlineVideoPlayer = document.getElementById('inline-video-player');
  const playerTimeDisplay = document.getElementById('player-time-display');
  const btnModeKeep = document.getElementById('btn-mode-keep');
  const btnModeRemove = document.getElementById('btn-mode-remove');
  const segmentsContainer = document.getElementById('segments-container');
  const btnAddSegment = document.getElementById('btn-add-segment');
  const btnPreviewAllTrim = document.getElementById('btn-preview-all-trim');
  const trimDurationBadge = document.getElementById('trim-duration-badge');
  const trimModeDesc = document.getElementById('trim-mode-desc');
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

  // --- Multi-Segment UI Rendering ---
  function renderSegments() {
    segmentsContainer.innerHTML = '';

    segments.forEach((seg, idx) => {
      const segEl = document.createElement('div');
      segEl.className = 'p-3.5 rounded-xl bg-slate-950/70 border border-slate-800 space-y-2.5 transition-all';
      segEl.innerHTML = `
        <div class="flex items-center justify-between pb-1.5 border-b border-slate-800/60">
          <div class="flex items-center gap-2">
            <span class="w-6 h-6 rounded-md bg-blue-500/20 text-blue-400 text-xs font-bold flex items-center justify-center">
              ${idx + 1}
            </span>
            <span class="text-xs font-bold text-white">Đoạn ${idx + 1}</span>
          </div>

          <div class="flex items-center gap-2">
            <!-- Preview single segment -->
            <button type="button" data-seg-id="${seg.id}" class="btn-preview-seg px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-[11px] font-semibold flex items-center gap-1 transition-colors">
              <i data-lucide="play" class="w-3 h-3 text-emerald-400"></i>
              <span>Xem đoạn này</span>
            </button>

            <!-- Delete button -->
            ${segments.length > 1 ? `
              <button type="button" data-seg-id="${seg.id}" class="btn-delete-seg p-1 rounded hover:bg-rose-500/10 text-rose-400 transition-colors" title="Xóa đoạn này">
                <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
              </button>
            ` : ''}
          </div>
        </div>

        <div class="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
          <!-- Start -->
          <div class="space-y-1">
            <div class="flex items-center justify-between">
              <label class="text-[11px] font-semibold text-slate-400 flex items-center gap-1">
                <span class="w-1.5 h-1.5 rounded-full bg-emerald-400"></span> Bắt đầu:
              </label>
              <button type="button" data-seg-id="${seg.id}" class="btn-set-start-curr text-[11px] text-blue-400 hover:text-blue-300 font-semibold flex items-center gap-0.5">
                <i data-lucide="map-pin" class="w-2.5 h-2.5"></i> Vị trí đang xem
              </button>
            </div>
            <input type="text" data-seg-id="${seg.id}" data-type="start" value="${secondsToTimeCode(seg.start)}" class="input-seg-time w-full px-3 py-1.5 bg-slate-900 text-xs font-mono font-bold text-white rounded-lg border border-slate-700 text-center focus:outline-none focus:border-blue-500">
          </div>

          <!-- End -->
          <div class="space-y-1">
            <div class="flex items-center justify-between">
              <label class="text-[11px] font-semibold text-slate-400 flex items-center gap-1">
                <span class="w-1.5 h-1.5 rounded-full bg-rose-400"></span> Kết thúc:
              </label>
              <button type="button" data-seg-id="${seg.id}" class="btn-set-end-curr text-[11px] text-blue-400 hover:text-blue-300 font-semibold flex items-center gap-0.5">
                <i data-lucide="map-pin" class="w-2.5 h-2.5"></i> Vị trí đang xem
              </button>
            </div>
            <input type="text" data-seg-id="${seg.id}" data-type="end" value="${secondsToTimeCode(seg.end)}" class="input-seg-time w-full px-3 py-1.5 bg-slate-900 text-xs font-mono font-bold text-white rounded-lg border border-slate-700 text-center focus:outline-none focus:border-blue-500">
          </div>
        </div>
      `;
      segmentsContainer.appendChild(segEl);
    });

    if (window.lucide) {
      window.lucide.createIcons();
    }

    attachSegmentEvents();
    updateTrimSummary();
  }

  function attachSegmentEvents() {
    // Delete buttons
    document.querySelectorAll('.btn-delete-seg').forEach(btn => {
      btn.addEventListener('click', () => {
        const id = parseInt(btn.getAttribute('data-seg-id'), 10);
        segments = segments.filter(s => s.id !== id);
        renderSegments();
      });
    });

    // Set current time for start
    document.querySelectorAll('.btn-set-start-curr').forEach(btn => {
      btn.addEventListener('click', () => {
        const id = parseInt(btn.getAttribute('data-seg-id'), 10);
        const seg = segments.find(s => s.id === id);
        if (seg) {
          seg.start = inlineVideoPlayer.currentTime || 0;
          renderSegments();
          showNotification(`Đoạn ${segments.indexOf(seg) + 1} - Bắt đầu: ${secondsToTimeCode(seg.start)}`);
        }
      });
    });

    // Set current time for end
    document.querySelectorAll('.btn-set-end-curr').forEach(btn => {
      btn.addEventListener('click', () => {
        const id = parseInt(btn.getAttribute('data-seg-id'), 10);
        const seg = segments.find(s => s.id === id);
        if (seg) {
          seg.end = inlineVideoPlayer.currentTime || 0;
          renderSegments();
          showNotification(`Đoạn ${segments.indexOf(seg) + 1} - Kết thúc: ${secondsToTimeCode(seg.end)}`);
        }
      });
    });

    // Time input edits
    document.querySelectorAll('.input-seg-time').forEach(input => {
      input.addEventListener('change', () => {
        const id = parseInt(input.getAttribute('data-seg-id'), 10);
        const type = input.getAttribute('data-type');
        const seg = segments.find(s => s.id === id);
        if (seg) {
          const valSec = timeCodeToSeconds(input.value);
          if (type === 'start') seg.start = valSec;
          else seg.end = valSec;
          updateTrimSummary();
        }
      });
    });

    // Preview single segment
    document.querySelectorAll('.btn-preview-seg').forEach(btn => {
      btn.addEventListener('click', () => {
        const id = parseInt(btn.getAttribute('data-seg-id'), 10);
        const seg = segments.find(s => s.id === id);
        if (seg) {
          playSegment(seg.start, seg.end, `Đang phát thử Đoạn ${segments.indexOf(seg) + 1}`);
        }
      });
    });
  }

  // --- Add Segment Button ---
  btnAddSegment.addEventListener('click', () => {
    const totalDur = currentMediaData?.duration_seconds || inlineVideoPlayer.duration || 60;
    const lastSeg = segments[segments.length - 1];
    const newStart = lastSeg ? Math.min(lastSeg.end + 5, totalDur) : 0;
    const newEnd = Math.min(newStart + 30, totalDur);

    segmentCounter++;
    segments.push({
      id: segmentCounter,
      start: newStart,
      end: newEnd
    });
    renderSegments();
    showNotification(`Đã thêm Đoạn ${segments.length}`);
  });

  // --- Trim Summary Calculations ---
  function updateTrimSummary() {
    const totalDur = currentMediaData?.duration_seconds || inlineVideoPlayer.duration || 60;

    // Calculate kept duration
    let totalProcessedSec = 0;
    if (trimMode === 'keep') {
      segments.forEach(s => {
        totalProcessedSec += Math.max(0, s.end - s.start);
      });
      trimDurationBadge.textContent = `Số đoạn chọn: ${segments.length} • Thời lượng ghép: ~${secondsToTimeCode(totalProcessedSec)}`;
      trimModeDesc.textContent = `(Sẽ trích xuất ${segments.length} đoạn đã chọn và ghép nối lại thành 1 file duy nhất)`;
    } else {
      let totalRemovedSec = 0;
      segments.forEach(s => {
        totalRemovedSec += Math.max(0, s.end - s.start);
      });
      totalProcessedSec = Math.max(0, totalDur - totalRemovedSec);
      trimDurationBadge.textContent = `Số đoạn cắt bỏ: ${segments.length} • Thời lượng còn lại: ~${secondsToTimeCode(totalProcessedSec)}`;
      trimModeDesc.textContent = `(Sẽ loại bỏ ${segments.length} đoạn không mong muốn, giữ lại và ghép các phần còn lại)`;
    }
  }

  // --- Mode Toggle: Keep (Lấy ghép) vs Remove (Cắt bỏ) ---
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

  // --- Preview Segment Player Helper ---
  function playSegment(startSec, endSec, msg) {
    if (!inlineVideoPlayer.src) {
      showNotification('Chưa tải được video để phát thử');
      return;
    }
    if (activeTrimTimer) {
      clearInterval(activeTrimTimer);
      activeTrimTimer = null;
    }

    inlineVideoPlayer.currentTime = startSec;
    inlineVideoPlayer.play().catch(() => {});
    showNotification(`${msg}: ${secondsToTimeCode(startSec)} ➔ ${secondsToTimeCode(endSec)}`);

    activeTrimTimer = setInterval(() => {
      if (inlineVideoPlayer.currentTime >= endSec) {
        inlineVideoPlayer.pause();
        clearInterval(activeTrimTimer);
        activeTrimTimer = null;
        showNotification('Đã phát xong đoạn đã chọn!');
      }
    }, 250);
  }

  // --- Preview All Segments (Sequential Simulation) ---
  btnPreviewAllTrim.addEventListener('click', () => {
    if (!inlineVideoPlayer.src || segments.length === 0) return;

    if (activeTrimTimer) {
      clearInterval(activeTrimTimer);
      activeTrimTimer = null;
    }

    if (trimMode === 'keep') {
      // Sort segments chronologically for preview
      const sorted = [...segments].sort((a, b) => a.start - b.start);
      let curIndex = 0;

      function playNext() {
        if (curIndex >= sorted.length) {
          inlineVideoPlayer.pause();
          showNotification('Đã phát thử xong toàn bộ các đoạn ghép!');
          return;
        }

        const currentSeg = sorted[curIndex];
        inlineVideoPlayer.currentTime = currentSeg.start;
        inlineVideoPlayer.play().catch(() => {});
        showNotification(`Đang phát thử: Đoạn ${curIndex + 1}/${sorted.length} (${secondsToTimeCode(currentSeg.start)} ➔ ${secondsToTimeCode(currentSeg.end)})`);

        activeTrimTimer = setInterval(() => {
          if (inlineVideoPlayer.currentTime >= currentSeg.end) {
            clearInterval(activeTrimTimer);
            activeTrimTimer = null;
            curIndex++;
            playNext();
          }
        }, 200);
      }

      playNext();

    } else {
      // Remove mode: start from 0, jump across every removed segment
      const sorted = [...segments].sort((a, b) => a.start - b.start);
      inlineVideoPlayer.currentTime = 0;
      inlineVideoPlayer.play().catch(() => {});
      showNotification(`Đang phát thử video sau khi cắt bỏ ${sorted.length} đoạn...`);

      activeTrimTimer = setInterval(() => {
        const cur = inlineVideoPlayer.currentTime;
        for (const r of sorted) {
          if (cur >= r.start && cur < r.end) {
            inlineVideoPlayer.currentTime = r.end;
            showNotification(`Đã nhảy qua đoạn cắt bỏ đến ${secondsToTimeCode(r.end)}`);
            break;
          }
        }
        if (inlineVideoPlayer.ended) {
          clearInterval(activeTrimTimer);
          activeTrimTimer = null;
        }
      }, 200);
    }
  });

  // --- Trigger Multi-Segment Download (MP4 / MP3) ---
  async function triggerTrimDownload(mediaType) {
    if (!currentMediaData || !currentDirectStreamUrl) {
      showError('Không tìm thấy nguồn video hợp lệ để cắt');
      return;
    }

    trimLoading.classList.remove('hidden');
    const safeTitle = currentMediaData.title || 'video';
    const totalDuration = currentMediaData.duration_seconds || inlineVideoPlayer.duration || 60;

    // Clean segments array
    const cleanSegments = segments.map(s => ({
      start: Math.round(s.start * 100) / 100,
      end: Math.round(s.end * 100) / 100
    }));

    const segmentsJson = encodeURIComponent(JSON.stringify(cleanSegments));
    const trimApiUrl = `${currentApiBase.replace(/\/$/, '')}/api/trim?url=${encodeURIComponent(currentDirectStreamUrl)}&segments=${segmentsJson}&mode=${trimMode}&type=${mediaType}&duration=${totalDuration}&title=${encodeURIComponent(safeTitle)}`;

    showNotification(`Đang gửi yêu cầu cắt ghép ${segments.length} đoạn (${mediaType.toUpperCase()})...`);

    const dlLink = document.createElement('a');
    dlLink.href = trimApiUrl;
    dlLink.setAttribute('download', '');
    document.body.appendChild(dlLink);
    dlLink.click();
    dlLink.remove();

    setTimeout(() => {
      trimLoading.classList.add('hidden');
      showNotification(`File ${mediaType.toUpperCase()} đã cắt ghép đang được tải về!`);
    }, 4500);
  }

  btnDownloadTrimMp4.addEventListener('click', () => triggerTrimDownload('video'));
  btnDownloadTrimMp3.addEventListener('click', () => triggerTrimDownload('audio'));

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

  // --- Render Result Card ---
  function renderResult(data) {
    resThumbnail.src = data.thumbnail || 'https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=500&auto=format&fit=crop&q=60';
    resDuration.textContent = data.duration_str || 'Video';
    resTitle.textContent = data.title;
    resAuthor.querySelector('span').textContent = data.author || 'Tác giả';

    const platform = detectPlatform(data.url) || { name: data.platform.toUpperCase(), color: 'blue' };
    resPlatformBadge.textContent = platform.name;

    const firstVideoFormat = data.formats.find((f) => f.type === 'video' && (f.direct_url || f.proxy_url));
    const firstAudioFormat = data.formats.find((f) => f.type === 'audio' && (f.direct_url || f.proxy_url));
    const streamTarget = firstVideoFormat || firstAudioFormat;

    if (streamTarget) {
      currentDirectStreamUrl = streamTarget.direct_url || streamTarget.proxy_url;
      inlineVideoPlayer.src = currentDirectStreamUrl;
      inlineVideoPlayer.load();

      const dur = data.duration_seconds || 30;
      segmentCounter = 1;
      segments = [
        { id: 1, start: 0, end: Math.min(dur, 30) }
      ];
      renderSegments();
    }

    renderFormats();
    resultContainer.classList.remove('hidden');

    if (window.lucide) {
      window.lucide.createIcons();
    }

    resultContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  // Time display on player
  inlineVideoPlayer.addEventListener('timeupdate', () => {
    const cur = secondsToTimeCode(inlineVideoPlayer.currentTime);
    const dur = secondsToTimeCode(inlineVideoPlayer.duration || currentMediaData?.duration_seconds || 0);
    playerTimeDisplay.textContent = `${cur} / ${dur}`;
  });

  // --- Real-time Input Validation ---
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

  // --- Installation & PWA Management ---
  const btnOpenInstall = document.getElementById('btn-open-install');
  const btnBannerInstallPc = document.getElementById('btn-banner-install-pc');
  const btnBannerInstallPhone = document.getElementById('btn-banner-install-phone');
  const btnBannerGuide = document.getElementById('btn-banner-guide');
  const modalInstallGuide = document.getElementById('modal-install-guide');
  const btnCloseInstallModal = document.getElementById('btn-close-install-modal');
  const headerInstallText = document.getElementById('header-install-text');

  const tabBtnPc = document.getElementById('tab-btn-pc');
  const tabBtnAndroid = document.getElementById('tab-btn-android');
  const tabBtnIos = document.getElementById('tab-btn-ios');
  const tabContentPc = document.getElementById('tab-content-pc');
  const tabContentAndroid = document.getElementById('tab-content-android');
  const tabContentIos = document.getElementById('tab-content-ios');
  const btnModalTriggerInstall = document.getElementById('btn-modal-trigger-install');

  // Detect Device
  const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;
  const isAndroid = /Android/.test(navigator.userAgent);
  const isStandalone = window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true;

  if (isStandalone) {
    if (headerInstallText) {
      headerInstallText.textContent = 'Đã Cài Đặt';
      btnOpenInstall.classList.replace('text-emerald-400', 'text-blue-400');
      btnOpenInstall.classList.replace('bg-emerald-600/20', 'bg-blue-600/20');
      btnOpenInstall.classList.replace('border-emerald-500/30', 'border-blue-500/30');
    }
  }

  function switchInstallTab(tab) {
    [tabBtnPc, tabBtnAndroid, tabBtnIos].forEach(b => {
      b.classList.remove('bg-blue-600', 'text-white');
      b.classList.add('text-slate-400');
    });
    [tabContentPc, tabContentAndroid, tabContentIos].forEach(c => c.classList.add('hidden'));

    if (tab === 'android') {
      tabBtnAndroid.classList.add('bg-blue-600', 'text-white');
      tabBtnAndroid.classList.remove('text-slate-400');
      tabContentAndroid.classList.remove('hidden');
    } else if (tab === 'ios') {
      tabBtnIos.classList.add('bg-blue-600', 'text-white');
      tabBtnIos.classList.remove('text-slate-400');
      tabContentIos.classList.remove('hidden');
    } else {
      tabBtnPc.classList.add('bg-blue-600', 'text-white');
      tabBtnPc.classList.remove('text-slate-400');
      tabContentPc.classList.remove('hidden');
    }
    if (window.lucide) window.lucide.createIcons();
  }

  function openInstallModal(preferredTab) {
    let target = preferredTab;
    if (!target) {
      if (isIOS) target = 'ios';
      else if (isAndroid) target = 'android';
      else target = 'pc';
    }
    switchInstallTab(target);
    modalInstallGuide.classList.remove('hidden');
    if (window.lucide) window.lucide.createIcons();
  }

  if (tabBtnPc) tabBtnPc.addEventListener('click', () => switchInstallTab('pc'));
  if (tabBtnAndroid) tabBtnAndroid.addEventListener('click', () => switchInstallTab('android'));
  if (tabBtnIos) tabBtnIos.addEventListener('click', () => switchInstallTab('ios'));

  if (btnOpenInstall) {
    btnOpenInstall.addEventListener('click', () => {
      if (deferredInstallPrompt) {
        triggerBrowserInstall();
      } else {
        openInstallModal();
      }
    });
  }

  if (btnBannerInstallPc) {
    btnBannerInstallPc.addEventListener('click', () => {
      if (deferredInstallPrompt && !isAndroid && !isIOS) {
        triggerBrowserInstall();
      } else {
        openInstallModal('pc');
      }
    });
  }

  if (btnBannerInstallPhone) {
    btnBannerInstallPhone.addEventListener('click', () => {
      if (isIOS) {
        openInstallModal('ios');
      } else {
        openInstallModal('android');
      }
    });
  }

  if (btnBannerGuide) {
    btnBannerGuide.addEventListener('click', () => openInstallModal());
  }

  if (btnCloseInstallModal) {
    btnCloseInstallModal.addEventListener('click', () => {
      modalInstallGuide.classList.add('hidden');
    });
  }

  modalInstallGuide?.addEventListener('click', (e) => {
    if (e.target === modalInstallGuide) {
      modalInstallGuide.classList.add('hidden');
    }
  });

  async function triggerBrowserInstall() {
    if (!deferredInstallPrompt) {
      showToast('Trình duyệt chưa sẵn sàng hoặc đã cài đặt. Vui lòng xem hướng dẫn!');
      openInstallModal('pc');
      return;
    }
    deferredInstallPrompt.prompt();
    const { outcome } = await deferredInstallPrompt.userChoice;
    if (outcome === 'accepted') {
      showToast('🎉 Đã cài đặt TaiMP4MP3 thành công!');
      modalInstallGuide?.classList.add('hidden');
      if (headerInstallText) headerInstallText.textContent = 'Đã Cài Đặt';
    }
    deferredInstallPrompt = null;
  }

  if (btnModalTriggerInstall) {
    btnModalTriggerInstall.addEventListener('click', triggerBrowserInstall);
  }

  // PWA beforeinstallprompt event
  window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    deferredInstallPrompt = e;
    if (btnModalTriggerInstall) {
      btnModalTriggerInstall.classList.remove('opacity-75');
    }
  });

  window.addEventListener('appinstalled', () => {
    deferredInstallPrompt = null;
    showToast('🎉 TaiMP4MP3 đã được cài đặt vào thiết bị của bạn!');
    if (headerInstallText) headerInstallText.textContent = 'Đã Cài Đặt';
    dismissCallout();
  });

  // --- 15-Second Installation Callout Pointer ---
  const installCallout = document.getElementById('install-callout-toast');
  const btnCloseCallout = document.getElementById('btn-close-callout');
  const btnCalloutInstall = document.getElementById('btn-callout-install');
  const installCountdownBadge = document.getElementById('install-countdown-badge');
  const installTimerProgress = document.getElementById('install-timer-progress');

  let calloutTimer = null;
  let remainingSeconds = 15;

  function dismissCallout() {
    if (calloutTimer) {
      clearInterval(calloutTimer);
      calloutTimer = null;
    }
    if (installCallout) {
      installCallout.classList.add('opacity-0', '-translate-y-4');
      setTimeout(() => {
        installCallout.classList.add('hidden');
      }, 500);
    }
  }

  function startCalloutCountdown() {
    if (!installCallout || isStandalone) return;
    if (sessionStorage.getItem('dismiss_install_callout')) return;

    setTimeout(() => {
      if (isStandalone) return;
      installCallout.classList.remove('hidden');
      void installCallout.offsetWidth;
      installCallout.classList.remove('opacity-0', '-translate-y-4');
      if (window.lucide) window.lucide.createIcons();

      remainingSeconds = 15;
      if (installCountdownBadge) installCountdownBadge.textContent = '15s';
      if (installTimerProgress) installTimerProgress.style.width = '100%';

      calloutTimer = setInterval(() => {
        remainingSeconds -= 1;
        if (installCountdownBadge) {
          installCountdownBadge.textContent = `${remainingSeconds}s`;
        }
        if (installTimerProgress) {
          const pct = Math.max(0, (remainingSeconds / 15) * 100);
          installTimerProgress.style.width = `${pct}%`;
        }

        if (remainingSeconds <= 0) {
          dismissCallout();
        }
      }, 1000);
    }, 1000);
  }

  if (btnCloseCallout) {
    btnCloseCallout.addEventListener('click', () => {
      sessionStorage.setItem('dismiss_install_callout', 'true');
      dismissCallout();
    });
  }

  if (btnCalloutInstall) {
    btnCalloutInstall.addEventListener('click', () => {
      dismissCallout();
      if (deferredInstallPrompt) {
        triggerBrowserInstall();
      } else {
        openInstallModal();
      }
    });
  }

  if (!isStandalone) {
    startCalloutCountdown();
  }

  if ('serviceWorker' in navigator && window.location.protocol.startsWith('http')) {
    navigator.serviceWorker.register('/sw.js').catch((err) => {
      console.warn('Service worker registration:', err);
    });
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
