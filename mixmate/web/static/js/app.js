const MixMate = (() => {
    const state = {
        currentStep: 1,
        uploadedFiles: [],
        analysisData: null,
        selectedStyles: [],
        renderCount: 1,
        targetDuration: 15,
        bgMusicPath: null,
        bgMusicName: null,
        currentTaskId: null,
        pollTimer: null,
        analyzing: false,
    };

    const $ = (sel) => document.querySelector(sel);
    const $$ = (sel) => document.querySelectorAll(sel);

    const TAG_LABELS = {
        dance: '💃 舞蹈', sports: '🏅 运动', talking: '🗣 对话',
        walking: '🚶 行走', closeup: '🔍 特写', landscape: '🌄 风景',
        group: '👥 群像', solo: '👤 独角', action: '⚡ 动作',
        emotion: '😊 情感', intro: '🎬 开场', outro: '🎬 结尾',
        broll: '📹 空镜', silence: '🔇 静音', music: '🎵 音乐',
    };

    const MOTION_LABELS = {
        0: { name: '静止', cls: 'motion-still' },
        1: { name: '低', cls: 'motion-low' },
        2: { name: '中', cls: 'motion-medium' },
        3: { name: '高', cls: 'motion-high' },
        4: { name: '极高', cls: 'motion-extreme' },
    };

    function init() {
        bindUpload();
        bindNavigation();
        bindStyleGrid();
        bindConfig();
        loadStyles();
        restoreState();
        checkFFmpeg();
    }

    async function restoreState() {
        try {
            const activeResp = await fetch('/api/active-task');
            const activeData = await activeResp.json();
            if (activeData.has_active) {
                state.analyzing = true;
                state.currentTaskId = activeData.task_id;
                const btn = $('#btnAnalyze');
                btn.disabled = true;
                btn.innerHTML = '<span class="btn-icon-left">⏳</span> 分析中...';
                goToStep(2);
                const container = $('#timelineContainer');
                container.innerHTML = `
                    <div class="timeline-loading">
                        <div class="spinner"></div>
                        <span id="analyzeMsg">${activeData.message || '正在分析中...'}</span>
                    </div>`;
                loadExistingFiles();
                const analysisData = await pollTask(activeData.task_id);
                if (analysisData) {
                    state.analysisData = analysisData.analysis;
                    renderTimeline(analysisData.analysis);
                    toast('Timeline 识别完成！', 'success');
                } else {
                    resetAnalyzeState();
                    goToStep(1);
                }
                return;
            }
        } catch (e) {
            console.error('[MixMate] restoreState active check failed:', e);
        }

        try {
            const lastResp = await fetch('/api/last-analysis');
            const lastData = await lastResp.json();
            if (lastData.has_analysis) {
                state.analysisData = lastData.analysis;
                loadExistingFiles();
                goToStep(2);
                renderTimeline(lastData.analysis);
                return;
            }
        } catch (e) {
            console.error('[MixMate] restoreState last-analysis check failed:', e);
        }

        loadExistingFiles();
    }

    async function loadExistingFiles() {
        try {
            const resp = await fetch('/api/uploaded-files');
            const data = await resp.json();
            if (data.files && data.files.length > 0) {
                state.uploadedFiles = data.files;
                renderFileList();
                $('#btnAnalyze').disabled = false;
            }
        } catch (e) {
            console.error('[MixMate] loadExistingFiles failed:', e);
        }
    }

    function toast(msg, type = 'info') {
        const container = $('#toastContainer');
        const el = document.createElement('div');
        el.className = `toast toast-${type}`;
        el.textContent = msg;
        container.appendChild(el);
        setTimeout(() => el.remove(), 3000);
    }

    function goToStep(step) {
        state.currentStep = step;
        $$('.step').forEach(s => {
            const sNum = parseInt(s.dataset.step);
            s.classList.remove('active', 'completed');
            if (sNum === step) s.classList.add('active');
            else if (sNum < step) s.classList.add('completed');
        });
        $$('.panel').forEach(p => p.classList.add('hidden'));
        const panelMap = { 1: 'panelUpload', 2: 'panelTimeline', 3: 'panelStyle', 4: 'panelResult' };
        const panel = $(`#${panelMap[step]}`);
        if (panel) {
            panel.classList.remove('hidden');
            panel.style.animation = 'none';
            panel.offsetHeight;
            panel.style.animation = '';
        }
    }

    function bindUpload() {
        const zone = $('#uploadZone');
        const input = $('#fileInput');

        zone.addEventListener('click', () => input.click());
        zone.addEventListener('dragover', (e) => { e.preventDefault(); zone.classList.add('dragover'); });
        zone.addEventListener('dragleave', () => zone.classList.remove('dragover'));
        zone.addEventListener('drop', (e) => {
            e.preventDefault();
            zone.classList.remove('dragover');
            handleFiles(e.dataTransfer.files);
        });
        input.addEventListener('change', () => handleFiles(input.files));

        $('#btnAnalyze').addEventListener('click', startAnalysis);
    }

    async function handleFiles(fileList) {
        const formData = new FormData();
        let count = 0;
        for (const f of fileList) {
            if (f.type.startsWith('video/') || /\.(mp4|mov|avi|mkv|flv|webm|m4v)$/i.test(f.name)) {
                formData.append('videos', f);
                count++;
            }
        }
        if (count === 0) { toast('请选择视频文件', 'error'); return; }

        toast(`正在上传 ${count} 个文件...`, 'info');
        try {
            const resp = await fetch('/api/upload', { method: 'POST', body: formData });
            const data = await resp.json();
            if (data.error) { toast(data.error, 'error'); return; }

            state.uploadedFiles = data.files;
            renderFileList();
            $('#btnAnalyze').disabled = false;
            toast(`已上传 ${data.count} 个文件`, 'success');
        } catch (e) {
            toast('上传失败: ' + e.message, 'error');
        }
    }

    function renderFileList() {
        const list = $('#fileList');
        list.innerHTML = state.uploadedFiles.map((f, i) => `
            <div class="file-item" data-index="${i}">
                <div class="file-icon">🎬</div>
                <div class="file-info">
                    <div class="file-name">${esc(f.name)}</div>
                    <div class="file-meta">ID: ${f.id}</div>
                </div>
                <button class="file-remove" data-index="${i}">✕</button>
            </div>
        `).join('');

        list.querySelectorAll('.file-remove').forEach(btn => {
            btn.addEventListener('click', () => {
                const idx = parseInt(btn.dataset.index);
                state.uploadedFiles.splice(idx, 1);
                renderFileList();
                if (state.uploadedFiles.length === 0) $('#btnAnalyze').disabled = true;
            });
        });
    }

    async function startAnalysis() {
        console.log('[MixMate] startAnalysis called, files:', state.uploadedFiles.length, 'analyzing:', state.analyzing);

        if (state.uploadedFiles.length === 0) {
            toast('请先上传视频文件', 'error');
            return;
        }

        if (state.analyzing) {
            toast('分析正在进行中，请稍候', 'warn');
            return;
        }

        state.analyzing = true;
        const btn = $('#btnAnalyze');
        btn.disabled = true;
        btn.innerHTML = '<span class="btn-icon-left">⏳</span> 分析中...';

        console.log('[MixMate] goToStep(2) called');
        goToStep(2);
        console.log('[MixMate] panelUpload hidden?', $('#panelUpload').classList.contains('hidden'), 'panelTimeline hidden?', $('#panelTimeline').classList.contains('hidden'));
        const container = $('#timelineContainer');
        const stats = $('#timelineStats');
        stats.innerHTML = '';
        container.innerHTML = renderAnalysisProgress(state.uploadedFiles);

        const paths = state.uploadedFiles.map(f => f.path);
        try {
            const resp = await fetch('/api/analyze', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ videos: paths }),
            });
            const data = await resp.json();
            if (data.error) {
                toast(data.error, 'error');
                resetAnalyzeState();
                goToStep(1);
                return;
            }

            if (data.task_id) {
                state.currentTaskId = data.task_id;
                updateAnalysisProgress({ message: '分析任务已启动，正在处理中...', progress: 5 });
                console.log('[MixMate] task_id:', data.task_id, 'starting poll...');
                const analysisData = await pollTask(data.task_id);
                console.log('[MixMate] pollTask returned:', !!analysisData, analysisData ? ('has_analysis=' + !!analysisData.analysis) : 'null');
                if (analysisData && analysisData.analysis) {
                    state.analysisData = analysisData.analysis;
                    console.log('[MixMate] calling renderTimeline, sources:', analysisData.analysis.sources?.length);
                    renderTimeline(analysisData.analysis);
                    toast('Timeline 识别完成！', 'success');
                    console.log('[MixMate] renderTimeline done, current step:', state.currentStep);
                } else {
                    console.error('[MixMate] pollTask returned no analysis data');
                    resetAnalyzeState();
                    goToStep(1);
                }
            } else if (data.analysis) {
                state.analysisData = data.analysis;
                renderTimeline(data.analysis);
                toast('Timeline 识别完成！', 'success');
            } else {
                toast('分析返回数据异常', 'error');
                resetAnalyzeState();
                goToStep(1);
            }
        } catch (e) {
            toast('分析失败: ' + e.message, 'error');
            resetAnalyzeState();
            goToStep(1);
        }
    }

    function resetAnalyzeState() {
        state.analyzing = false;
        state.currentTaskId = null;
        const btn = $('#btnAnalyze');
        btn.disabled = false;
        btn.innerHTML = '<span class="btn-icon-left">🔍</span> 开始 Timeline 识别';
    }

    async function pollTask(taskId) {
        const maxAttempts = 600;
        for (let i = 0; i < maxAttempts; i++) {
            await new Promise(r => setTimeout(r, 2000));
            try {
                const resp = await fetch(`/api/task/${taskId}`);
                if (!resp.ok) {
                    console.error('[MixMate] pollTask HTTP error:', resp.status);
                    continue;
                }
                const data = await resp.json();
                updateAnalysisProgress(data);
                if (data.status === 'done') {
                    console.log('[MixMate] pollTask done, has_analysis:', !!data.analysis);
                    return data;
                } else if (data.status === 'error') {
                    toast(data.message || '分析失败', 'error');
                    return null;
                }
            } catch (e) {
                console.error('[MixMate] pollTask fetch error:', e);
            }
        }
        toast('分析超时', 'error');
        return null;
    }

    const ANALYSIS_STEPS = ['初始化', '镜头分割', '音频提取', '节拍检测', '运动分析 + 内容标签', '完成'];

    function renderAnalysisProgress(files) {
        let cardsHtml = '';
        for (let i = 0; i < files.length; i++) {
            const f = files[i];
            const name = f.name || f.path.split('/').pop();
            cardsHtml += `<div class="aprog-card" id="aprogCard${i}">
                <div class="aprog-card-header">
                    <div class="aprog-card-icon" id="aprogIcon${i}">
                        <div class="aprog-spinner"></div>
                    </div>
                    <div class="aprog-card-meta">
                        <div class="aprog-card-name">${esc(name)}</div>
                        <div class="aprog-card-step" id="aprogStep${i}">等待中...</div>
                    </div>
                    <div class="aprog-card-badge" id="aprogBadge${i}"></div>
                </div>
                <div class="aprog-steps">
                    ${ANALYSIS_STEPS.map((s, si) => `<div class="aprog-step" id="aprogStepDot${i}_${si}">
                        <div class="aprog-step-dot"></div>
                        <span class="aprog-step-text">${s}</span>
                    </div>`).join('')}
                </div>
                <div class="aprog-detail" id="aprogDetail${i}"></div>
            </div>`;
        }

        return `<div class="analysis-progress">
            <div class="aprog-header">
                <div class="aprog-title">
                    <div class="aprog-title-spinner"></div>
                    <span id="aprogMessage">正在提交分析任务...</span>
                </div>
                <div class="aprog-overall" id="aprogOverall">
                    <div class="aprog-overall-bar">
                        <div class="aprog-overall-fill" id="aprogOverallFill" style="width:0%"></div>
                    </div>
                    <span class="aprog-overall-pct" id="aprogOverallPct">0%</span>
                </div>
            </div>
            <div class="aprog-cards">${cardsHtml}</div>
        </div>`;
    }

    function updateAnalysisProgress(data) {
        const msgEl = $('#aprogMessage');
        if (msgEl && data.message) msgEl.textContent = data.message;

        const fillEl = $('#aprogOverallFill');
        const pctEl = $('#aprogOverallPct');
        if (fillEl && data.progress != null) {
            fillEl.style.width = data.progress + '%';
        }
        if (pctEl && data.progress != null) {
            pctEl.textContent = data.progress + '%';
        }

        if (data.video_progress) {
            for (let i = 0; i < data.video_progress.length; i++) {
                const vp = data.video_progress[i];
                const stepEl = $(`#aprogStep${i}`);
                const iconEl = $(`#aprogIcon${i}`);
                const badgeEl = $(`#aprogBadge${i}`);
                const detailEl = $(`#aprogDetail${i}`);

                if (stepEl) stepEl.textContent = vp.step || '';

                if (iconEl) {
                    if (vp.status === 'done') {
                        iconEl.innerHTML = '<span class="aprog-done-icon">✓</span>';
                    } else if (vp.status === 'error') {
                        iconEl.innerHTML = '<span class="aprog-error-icon">✗</span>';
                    } else {
                        iconEl.innerHTML = '<div class="aprog-spinner"></div>';
                    }
                }

                if (badgeEl) {
                    let badges = '';
                    if (vp.shot_count != null) badges += `<span class="aprog-badge">🔍 ${vp.shot_count} 镜头</span>`;
                    if (vp.beat_count != null) badges += `<span class="aprog-badge">🥁 ${vp.beat_count} 拍</span>`;
                    if (vp.duration != null) badges += `<span class="aprog-badge">⏱ ${vp.duration}s</span>`;
                    if (vp.resolution) badges += `<span class="aprog-badge">📐 ${vp.resolution}</span>`;
                    badgeEl.innerHTML = badges;
                }

                if (detailEl && vp.resolution) {
                    detailEl.innerHTML = `<span class="aprog-detail-text">${vp.resolution} · ${vp.fps}fps · ${vp.duration}s</span>`;
                }

                for (let si = 0; si < ANALYSIS_STEPS.length; si++) {
                    const dotEl = $(`#aprogStepDot${i}_${si}`);
                    if (!dotEl) continue;
                    dotEl.classList.remove('active', 'done');
                    if (si < vp.step_index) {
                        dotEl.classList.add('done');
                    } else if (si === vp.step_index) {
                        dotEl.classList.add('active');
                    }
                }
            }
        }
    }

    function renderTimeline(analysis) {
        const container = $('#timelineContainer');
        const stats = $('#timelineStats');

        const SHOT_TYPE_LABELS = {
            static: '固定', pan: '摇镜', tilt: '俯仰', zoom: '推拉',
            tracking: '跟踪', handheld: '手持', transition: '转场',
        };

        stats.innerHTML = `
            <div class="stat-card"><div class="stat-value">${analysis.total_segments}</div><div class="stat-label">镜头总数</div></div>
            <div class="stat-card"><div class="stat-value">${analysis.total_duration.toFixed(1)}s</div><div class="stat-label">总时长</div></div>
            <div class="stat-card"><div class="stat-value">${analysis.source_count}</div><div class="stat-label">素材数</div></div>
            <div class="stat-card"><div class="stat-value">${analysis.global_beat_count}</div><div class="stat-label">节拍点</div></div>
        `;

        let html = '';
        for (let si = 0; si < analysis.sources.length; si++) {
            const source = analysis.sources[si];
            const name = source.file_path.split('/').pop();
            const thumbUrl = `/api/thumbnail?path=${encodeURIComponent(source.file_path)}`;
            const videoUrl = `/api/video?path=${encodeURIComponent(source.file_path)}`;

            html += `<div class="source-card" data-source-index="${si}">
                <div class="source-header">
                    <div class="source-thumb" style="background-image:url('${thumbUrl}')">
                        <div class="source-play-btn" data-video="${esc(videoUrl)}">▶</div>
                    </div>
                    <div class="source-meta">
                        <div class="source-name">${esc(name)}</div>
                        <div class="source-info">
                            <span class="source-tag">${source.resolution}</span>
                            <span class="source-tag">${source.fps}fps</span>
                            <span class="source-tag">${source.duration.toFixed(1)}s</span>
                            <span class="source-tag">${source.segment_count} 镜头</span>
                        </div>
                    </div>
                </div>
                <div class="source-timeline-track">
                    <div class="track-ruler" style="--dur:${source.duration}">`;

            for (let t = 0; t <= source.duration; t += Math.max(1, Math.floor(source.duration / 10))) {
                const pct = (t / source.duration) * 100;
                html += `<span class="ruler-mark" style="left:${pct}%">${t}s</span>`;
            }

            html += `</div>
                    <div class="track-shots">`;

            for (const seg of source.segments) {
                const mInfo = MOTION_LABELS[seg.motion_intensity] || MOTION_LABELS[0];
                const leftPct = (seg.start_time / source.duration) * 100;
                const widthPct = (seg.duration / source.duration) * 100;
                const tags = (seg.content_tags || []).slice(0, 3).map(t => TAG_LABELS[t] || t).join(' ');
                const shotLabel = SHOT_TYPE_LABELS[seg.shot_type] || seg.shot_type;

                html += `<div class="track-shot ${mInfo.cls}" 
                    style="left:${leftPct}%;width:${widthPct}%"
                    data-seg-index="${seg.index}"
                    data-source-index="${si}"
                    data-start="${seg.start_time}"
                    data-end="${seg.end_time}">
                    <span class="tshot-label">#${seg.index} ${shotLabel}</span>
                    <span class="tshot-dur">${seg.duration.toFixed(1)}s</span>
                </div>`;
            }

            html += `</div>
                </div>
                <div class="source-segments">`;

            for (const seg of source.segments) {
                const mInfo = MOTION_LABELS[seg.motion_intensity] || MOTION_LABELS[0];
                const tags = (seg.content_tags || []).map(t => TAG_LABELS[t] || t);
                const shotLabel = SHOT_TYPE_LABELS[seg.shot_type] || seg.shot_type;
                const qualityClass = seg.quality_score >= 0.7 ? 'quality-good' : seg.quality_score >= 0.4 ? 'quality-ok' : 'quality-bad';
                const stabilityClass = seg.stability_score >= 0.7 ? 'stability-good' : seg.stability_score >= 0.4 ? 'stability-ok' : 'stability-bad';

                html += `<div class="seg-card" data-seg-index="${seg.index}" data-source-index="${si}">
                    <div class="seg-header">
                        <span class="seg-index">#${seg.index}</span>
                        <span class="seg-type">${shotLabel}</span>
                        <span class="seg-motion ${mInfo.cls}">${mInfo.name}</span>
                    </div>
                    <div class="seg-time">
                        <span>${seg.start_time.toFixed(1)}s → ${seg.end_time.toFixed(1)}s</span>
                        <span class="seg-duration">${seg.duration.toFixed(1)}s</span>
                    </div>
                    <div class="seg-bars">
                        <div class="seg-bar-row">
                            <span class="bar-label">运动</span>
                            <div class="bar-track"><div class="bar-fill motion" style="width:${Math.min(seg.motion_score * 100, 100)}%"></div></div>
                            <span class="bar-val">${seg.motion_score.toFixed(2)}</span>
                        </div>
                        <div class="seg-bar-row">
                            <span class="bar-label">质量</span>
                            <div class="bar-track"><div class="bar-fill quality ${qualityClass}" style="width:${Math.min(seg.quality_score * 100, 100)}%"></div></div>
                            <span class="bar-val">${seg.quality_score.toFixed(2)}</span>
                        </div>
                        <div class="seg-bar-row">
                            <span class="bar-label">稳定</span>
                            <div class="bar-track"><div class="bar-fill stability ${stabilityClass}" style="width:${Math.min(seg.stability_score * 100, 100)}%"></div></div>
                            <span class="bar-val">${seg.stability_score.toFixed(2)}</span>
                        </div>
                        <div class="seg-bar-row">
                            <span class="bar-label">亮度</span>
                            <div class="bar-track"><div class="bar-fill brightness" style="width:${Math.min(seg.brightness * 100, 100)}%"></div></div>
                            <span class="bar-val">${seg.brightness.toFixed(2)}</span>
                        </div>
                        <div class="seg-bar-row">
                            <span class="bar-label">音频</span>
                            <div class="bar-track"><div class="bar-fill audio" style="width:${Math.min(seg.audio_energy * 100, 100)}%"></div></div>
                            <span class="bar-val">${seg.audio_energy.toFixed(2)}</span>
                        </div>
                    </div>
                    ${tags.length > 0 ? `<div class="seg-tags">${tags.map(t => `<span class="seg-tag">${t}</span>`).join('')}</div>` : ''}
                    <div class="seg-audio-flags">
                        ${seg.has_music ? '<span class="audio-flag music">🎵 音乐</span>' : ''}
                        ${seg.has_speech ? '<span class="audio-flag speech">🗣 语音</span>' : ''}
                        ${seg.beat_count > 0 ? `<span class="audio-flag beat">🥁 ${seg.beat_count}拍</span>` : ''}
                    </div>
                </div>`;
            }

            html += `</div>
            </div>`;
        }

        container.innerHTML = html;
        bindTimelineEvents();
    }

    function bindTimelineEvents() {
        $$('.source-play-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const url = btn.dataset.video;
                openVideoPreview(url);
            });
        });

        $$('.track-shot').forEach(shot => {
            shot.addEventListener('click', () => {
                const si = shot.dataset.sourceIndex;
                const segIdx = shot.dataset.segIndex;
                const segCard = $(`.seg-card[data-source-index="${si}"][data-seg-index="${segIdx}"]`);
                if (segCard) {
                    segCard.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    segCard.classList.add('seg-highlight');
                    setTimeout(() => segCard.classList.remove('seg-highlight'), 1500);
                }
            });
        });

        $$('.seg-card').forEach(card => {
            card.addEventListener('click', () => {
                $$('.seg-card').forEach(c => c.classList.remove('selected'));
                card.classList.add('selected');
            });
        });
    }

    function openVideoPreview(url) {
        let overlay = $('#videoPreviewOverlay');
        if (!overlay) {
            overlay = document.createElement('div');
            overlay.id = 'videoPreviewOverlay';
            overlay.className = 'video-preview-overlay';
            overlay.innerHTML = `
                <div class="video-preview-box">
                    <div class="video-preview-header">
                        <span>视频预览</span>
                        <button class="video-preview-close" id="btnClosePreview">✕</button>
                    </div>
                    <video id="videoPreviewPlayer" controls style="width:100%;max-height:70vh;border-radius:8px;"></video>
                </div>`;
            document.body.appendChild(overlay);
            overlay.querySelector('#btnClosePreview').addEventListener('click', () => {
                const v = $('#videoPreviewPlayer');
                v.pause();
                v.src = '';
                overlay.classList.add('hidden');
            });
            overlay.addEventListener('click', (e) => {
                if (e.target === overlay) {
                    const v = $('#videoPreviewPlayer');
                    v.pause();
                    v.src = '';
                    overlay.classList.add('hidden');
                }
            });
        }
        const player = $('#videoPreviewPlayer');
        player.src = url;
        overlay.classList.remove('hidden');
        player.play().catch(() => {});
    }

    function bindNavigation() {
        $('#btnBackUpload').addEventListener('click', () => goToStep(1));
        $('#btnReAnalyze').addEventListener('click', async () => {
            if (state.analyzing) {
                toast('分析正在进行中，请稍候', 'warn');
                return;
            }
            try {
                await fetch('/api/last-analysis', { method: 'DELETE' });
            } catch (e) {}
            state.analysisData = null;
            state.analyzing = false;
            state.currentTaskId = null;
            const btn = $('#btnAnalyze');
            btn.disabled = false;
            btn.innerHTML = '<span class="btn-icon-left">🔍</span> 开始 Timeline 识别';
            goToStep(1);
            toast('已清空分析结果，可重新识别', 'info');
        });
        $('#btnToStyle').addEventListener('click', () => goToStep(3));
        $('#btnBackTimeline').addEventListener('click', () => goToStep(2));
        $('#btnBackStyle').addEventListener('click', () => goToStep(3));
        $('#btnNewTask').addEventListener('click', () => {
            state.uploadedFiles = [];
            state.analysisData = null;
            state.selectedStyles = [];
            state.currentTaskId = null;
            state.analyzing = false;
            $('#fileList').innerHTML = '';
            const btn = $('#btnAnalyze');
            btn.disabled = true;
            btn.innerHTML = '<span class="btn-icon-left">🔍</span> 开始 Timeline 识别';
            $('#resultList').innerHTML = '';
            $('#btnNewTask').classList.add('hidden');
            goToStep(1);
        });
        $('#btnStartRender').addEventListener('click', startRender);
    }

    async function loadStyles() {
        try {
            const resp = await fetch('/api/styles');
            const data = await resp.json();
            renderStyleGrid(data.styles);
        } catch (e) {
            toast('加载风格失败', 'error');
        }
    }

    function renderStyleGrid(styles) {
        const grid = $('#styleGrid');
        grid.innerHTML = styles.map(s => `
            <div class="style-card" data-style="${s.name}">
                <div class="style-card-header">
                    <div class="style-card-name">${esc(s.display_name)}</div>
                    <div class="style-card-check">✓</div>
                </div>
                <div class="style-card-desc">${esc(s.description)}</div>
                <div class="style-card-meta">
                    <span class="style-meta-item">⏱ ${s.target_duration}s</span>
                    <span class="style-meta-item">🎯 ${s.name}</span>
                </div>
            </div>
        `).join('');

        grid.querySelectorAll('.style-card').forEach(card => {
            card.addEventListener('click', () => {
                const name = card.dataset.style;
                if (card.classList.contains('selected')) {
                    card.classList.remove('selected');
                    state.selectedStyles = state.selectedStyles.filter(s => s !== name);
                } else {
                    card.classList.add('selected');
                    state.selectedStyles.push(name);
                }
            });
        });

        const firstCard = grid.querySelector('.style-card');
        if (firstCard) {
            firstCard.classList.add('selected');
            state.selectedStyles = [firstCard.dataset.style];
        }
    }

    function bindStyleGrid() {}

    function bindConfig() {
        const slider = $('#cfgDuration');
        const val = $('#cfgDurationVal');
        slider.addEventListener('input', () => {
            state.targetDuration = parseInt(slider.value);
            val.textContent = slider.value + '秒';
        });

        $$('#cfgCount .btn-toggle').forEach(btn => {
            btn.addEventListener('click', () => {
                $$('#cfgCount .btn-toggle').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                state.renderCount = parseInt(btn.dataset.val);
            });
        });

        const musicBtn = $('#btnMusic');
        const musicInput = $('#musicInput');
        const musicName = $('#musicName');
        musicBtn.addEventListener('click', () => musicInput.click());
        musicInput.addEventListener('change', () => {
            if (musicInput.files.length > 0) {
                state.bgMusicName = musicInput.files[0].name;
                musicName.textContent = state.bgMusicName;
                toast('背景音乐已选择', 'success');
            }
        });
    }

    async function startRender() {
        if (state.selectedStyles.length === 0) {
            toast('请至少选择一种风格', 'error');
            return;
        }

        goToStep(4);
        $('#progressBar').style.width = '0%';
        $('#progressPct').textContent = '0%';
        $('#progressStatus').textContent = '正在提交任务...';
        $('#resultList').innerHTML = '';
        $('#btnNewTask').classList.add('hidden');

        const paths = state.uploadedFiles.map(f => f.path);
        try {
            const resp = await fetch('/api/render', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    videos: paths,
                    styles: state.selectedStyles,
                    count: state.renderCount,
                    duration: state.targetDuration,
                    bg_music: state.bgMusicPath,
                }),
            });
            const data = await resp.json();
            if (data.error) { toast(data.error, 'error'); return; }

            state.currentTaskId = data.task_id;
            pollTask();
        } catch (e) {
            toast('提交失败: ' + e.message, 'error');
        }
    }

    function pollTask() {
        if (state.pollTimer) clearInterval(state.pollTimer);
        state.pollTimer = setInterval(async () => {
            if (!state.currentTaskId) return;
            try {
                const resp = await fetch(`/api/task/${state.currentTaskId}`);
                const data = await resp.json();

                const pct = data.progress || 0;
                $('#progressBar').style.width = pct + '%';
                $('#progressPct').textContent = pct + '%';
                $('#progressStatus').textContent = data.message || '';

                if (data.status === 'done') {
                    clearInterval(state.pollTimer);
                    $('#resultMessage').textContent = `完成！共生成 ${data.results.length} 条视频`;
                    renderResults(data.results);
                    $('#btnNewTask').classList.remove('hidden');
                    toast('视频生成完成！', 'success');
                } else if (data.status === 'error') {
                    clearInterval(state.pollTimer);
                    toast(data.message, 'error');
                    $('#btnNewTask').classList.remove('hidden');
                }
            } catch (e) {
                clearInterval(state.pollTimer);
            }
        }, 1500);
    }

    function renderResults(results) {
        const list = $('#resultList');
        list.innerHTML = results.map(r => {
            const sizeMB = (r.file_size / 1024 / 1024).toFixed(1);
            return `
                <div class="result-card">
                    <div class="result-card-header">
                        <div class="result-name">${esc(r.name)}</div>
                        <span class="result-style-badge">${esc(r.style)}</span>
                    </div>
                    <div class="result-meta">
                        <div class="result-meta-item">时长 <span>${r.duration}s</span></div>
                        <div class="result-meta-item">大小 <span>${sizeMB}MB</span></div>
                    </div>
                    <button class="btn-download" onclick="window.open('/api/download/${state.currentTaskId}/${r.filename}')">
                        ⬇ 下载视频
                    </button>
                </div>`;
        }).join('');
    }

    async function checkFFmpeg() {
        try {
            const resp = await fetch('/api/ffmpeg-check');
            const data = await resp.json();
            if (!data.available) {
                toast('FFmpeg 未安装，请先安装: brew install ffmpeg', 'error');
            }
        } catch (e) {}
    }

    function esc(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    // ===== AI Config =====
    const aiModal = $('#aiModal');
    const btnAISettings = $('#btnAISettings');
    const btnCloseAI = $('#btnCloseAI');
    const btnCancelAI = $('#btnCancelAI');
    const btnSaveAI = $('#btnSaveAI');

    btnAISettings.addEventListener('click', () => {
        aiModal.classList.remove('hidden');
        loadAIConfig();
        checkAIStatus();
    });

    btnCloseAI.addEventListener('click', () => aiModal.classList.add('hidden'));
    btnCancelAI.addEventListener('click', () => aiModal.classList.add('hidden'));

    aiModal.addEventListener('click', (e) => {
        if (e.target === aiModal) aiModal.classList.add('hidden');
    });

    $('#aiVisionProvider').addEventListener('change', (e) => {
        $('#aiVisionOpenAI').style.display = e.target.value === 'openai' ? 'flex' : 'none';
        $('#aiVisionLocal').style.display = e.target.value === 'local' ? 'flex' : 'none';
    });

    $('#aiSpeechProvider').addEventListener('change', (e) => {
        const v = e.target.value;
        $('#aiSpeechWhisper').style.display = (v === 'whisper_local' || v === 'whisper_api') ? 'flex' : 'none';
        $('#aiSpeechAPI').style.display = v === 'whisper_api' ? 'flex' : 'none';
    });

    $('#aiNarrativeProvider').addEventListener('change', (e) => {
        $('#aiNarrativeOpenAI').style.display = e.target.value === 'openai' ? 'flex' : 'none';
    });

    async function loadAIConfig() {
        try {
            const resp = await fetch('/api/ai/config');
            const data = await resp.json();
            const cfg = data.config || {};

            const v = cfg.vision || {};
            $('#aiVisionProvider').value = v.provider || 'rule_based';
            $('#aiVisionKey').value = (v.openai || {}).api_key || '';
            $('#aiVisionBaseURL').value = (v.openai || {}).base_url || 'https://api.openai.com/v1';
            $('#aiVisionModel').value = (v.openai || {}).model || 'gpt-4o';
            $('#aiVisionLocalModel').value = (v.local || {}).model || 'llava';
            $('#aiVisionOllamaURL').value = (v.local || {}).ollama_url || 'http://localhost:11434';
            $('#aiVisionProvider').dispatchEvent(new Event('change'));

            const s = cfg.speech || {};
            $('#aiSpeechProvider').value = s.provider || 'simple';
            $('#aiWhisperModelSize').value = (s.whisper || {}).model_size || 'base';
            $('#aiWhisperLang').value = (s.whisper || {}).language || 'zh';
            $('#aiSpeechKey').value = (s.openai || {}).api_key || '';
            $('#aiSpeechBaseURL').value = (s.openai || {}).base_url || 'https://api.openai.com/v1';
            $('#aiSpeechProvider').dispatchEvent(new Event('change'));

            const n = cfg.narrative || {};
            $('#aiNarrativeProvider').value = n.provider || 'rule_based';
            $('#aiNarrativeKey').value = (n.openai || {}).api_key || '';
            $('#aiNarrativeBaseURL').value = (n.openai || {}).base_url || 'https://api.openai.com/v1';
            $('#aiNarrativeModel').value = (n.openai || {}).model || 'gpt-4o';
            $('#aiNarrativeProvider').dispatchEvent(new Event('change'));
        } catch (e) {
            console.error('加载AI配置失败:', e);
        }
    }

    async function checkAIStatus() {
        try {
            const resp = await fetch('/api/ai/check');
            const data = await resp.json();

            const dotV = $('#aiDotVision');
            const dotS = $('#aiDotSpeech');
            const dotN = $('#aiDotNarrative');

            dotV.classList.toggle('active', data.vision.available);
            dotS.classList.toggle('active', data.speech.available);
            dotN.classList.toggle('active', data.narrative.available);

            $('#aiLabelVision').textContent = data.vision.provider === 'rule_based' ? '规则引擎' : data.vision.provider;
            $('#aiLabelSpeech').textContent = data.speech.provider === 'simple' ? '简单检测' : data.speech.provider;
            $('#aiLabelNarrative').textContent = data.narrative.provider === 'rule_based' ? '规则引擎' : data.narrative.provider;
        } catch (e) {}
    }

    btnSaveAI.addEventListener('click', async () => {
        const config = {
            vision: {
                provider: $('#aiVisionProvider').value,
                openai: {
                    api_key: $('#aiVisionKey').value,
                    model: $('#aiVisionModel').value,
                    base_url: $('#aiVisionBaseURL').value || 'https://api.openai.com/v1',
                },
                local: {
                    model: $('#aiVisionLocalModel').value || 'llava',
                    ollama_url: $('#aiVisionOllamaURL').value || 'http://localhost:11434',
                },
            },
            speech: {
                provider: $('#aiSpeechProvider').value,
                whisper: {
                    mode: $('#aiSpeechProvider').value === 'whisper_api' ? 'api' : 'local',
                    model_size: $('#aiWhisperModelSize').value || 'base',
                    language: $('#aiWhisperLang').value || 'zh',
                },
                openai: {
                    api_key: $('#aiSpeechKey').value,
                    base_url: $('#aiSpeechBaseURL').value || 'https://api.openai.com/v1',
                },
            },
            narrative: {
                provider: $('#aiNarrativeProvider').value,
                openai: {
                    api_key: $('#aiNarrativeKey').value,
                    model: $('#aiNarrativeModel').value || 'gpt-4o',
                    base_url: $('#aiNarrativeBaseURL').value || 'https://api.openai.com/v1',
                },
            },
            analysis: {
                vision_sample_frames: 3,
                vision_max_segments: 30,
                speech_enabled: true,
                narrative_enabled: true,
            },
        };

        try {
            const resp = await fetch('/api/ai/config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ config }),
            });
            const data = await resp.json();
            if (data.ok) {
                toast('AI 配置已保存 ✓', 'success');
                checkAIStatus();
                setTimeout(() => aiModal.classList.add('hidden'), 800);
            } else {
                toast('保存失败: ' + (data.error || '未知错误'), 'error');
            }
        } catch (e) {
            toast('保存失败: ' + e.message, 'error');
        }
    });

    document.addEventListener('DOMContentLoaded', init);

    return { state, toast, goToStep };
})();
