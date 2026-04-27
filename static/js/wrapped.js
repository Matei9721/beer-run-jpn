const app = document.getElementById('wrapped-app');
const startScreen = document.getElementById('start-screen');
const startBtn = document.getElementById('start-btn');
const stage = document.getElementById('slide-stage');
const progressTrack = document.getElementById('progress-track');
const counter = document.getElementById('slide-counter');
const prevBtn = document.getElementById('prev-btn');
const nextBtn = document.getElementById('next-btn');
const prevZone = document.getElementById('prev-zone');
const nextZone = document.getElementById('next-zone');
const pauseBtn = document.getElementById('pause-btn');
const audioBtn = document.getElementById('audio-btn');
const volumeControl = document.getElementById('volume-control');
const volumeSlider = document.getElementById('volume-slider');

let wrapped = null;
let slides = [];
let currentIndex = 0;
let started = false;
let paused = false;
let timer = null;
let audio = null;
let audioReady = false;
let audioMuted = false;
let audioVolume = Number(volumeSlider?.value || 5) / 100;

const ICONS = {
    pause: `
        <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M8 5v14"></path>
            <path d="M16 5v14"></path>
        </svg>
    `,
    play: `
        <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="m8 5 11 7-11 7V5Z"></path>
        </svg>
    `,
    volume: `
        <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M11 5 6 9H3v6h3l5 4V5Z"></path>
            <path d="M15.5 8.5a5 5 0 0 1 0 7"></path>
            <path d="M18.5 5.5a9 9 0 0 1 0 13"></path>
        </svg>
    `,
    muted: `
        <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M11 5 6 9H3v6h3l5 4V5Z"></path>
            <path d="m16 9 5 5"></path>
            <path d="m21 9-5 5"></path>
        </svg>
    `,
};

function escapeHtml(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

function slideDuration() {
    return Number(wrapped?.meta?.slide_duration_ms || 10500);
}

function statMarkup(stats = []) {
    if (!stats.length) return '';
    return `
        <div class="stat-grid">
            ${stats.map(stat => `
                <div class="stat-pill">
                    <div class="stat-value">${escapeHtml(stat.value)}</div>
                    <div class="stat-label">${escapeHtml(stat.label)}</div>
                </div>
            `).join('')}
        </div>
    `;
}

function imageMarkup(image) {
    if (!image?.src) return '';
    return `
        <figure class="slide-media">
            <img src="${escapeHtml(image.src)}" alt="${escapeHtml(image.alt || '')}">
            ${image.caption ? `<figcaption class="image-caption">${escapeHtml(image.caption)}</figcaption>` : ''}
        </figure>
    `;
}

function leaderboardMarkup(rows = []) {
    if (!rows.length) return '';
    return `
        <div class="leaderboard-list">
            ${rows.map((row, index) => `
                <div class="leaderboard-row">
                    <div class="rank-number">${index + 1}</div>
                    <div>
                        <div class="leader-name">${escapeHtml(row.username)}</div>
                        <div class="leader-meta">${escapeHtml(row.entries)} entries - ${escapeHtml(row.liters)}L total</div>
                    </div>
                    <div class="leader-score">${escapeHtml(row.pure_alcohol)} Alc L</div>
                </div>
            `).join('')}
        </div>
    `;
}

function locationMarkup(rows = []) {
    if (!rows.length) return '';
    return `
        <div class="location-list">
            ${rows.map(row => `
                <div class="location-row">
                    <div class="rank-number">${escapeHtml(String(row.name).charAt(0))}</div>
                    <div>
                        <div class="location-name">${escapeHtml(row.name)}</div>
                        <div class="location-meta">${escapeHtml(row.entries)} entries</div>
                    </div>
                    <div class="location-score">${escapeHtml(row.pure_alcohol)} Alc L</div>
                </div>
            `).join('')}
        </div>
    `;
}

function dateRangeMarkup(dateRange) {
    if (!dateRange?.start || !dateRange?.end) return '';
    return `
        <div class="date-range-panel">
            <div class="date-node">
                <span class="date-label">Start</span>
                <strong>${escapeHtml(dateRange.start_short || dateRange.start)}</strong>
            </div>
            <div class="date-line" aria-hidden="true"></div>
            <div class="date-node">
                <span class="date-label">Finish</span>
                <strong>${escapeHtml(dateRange.end_short || dateRange.end)}</strong>
            </div>
        </div>
    `;
}

function badgeMarkup(label) {
    if (!label) return '';
    return `<div class="story-badge">${escapeHtml(label)}</div>`;
}

function timelineMarkup(timeline) {
    const checkpoints = Array.isArray(timeline?.checkpoints) ? timeline.checkpoints : [];
    const series = Array.isArray(timeline?.series) ? timeline.series : [];
    if (checkpoints.length < 2 || !series.length) return '';

    const width = 720;
    const height = 420;
    const padding = { top: 34, right: 34, bottom: 58, left: 54 };
    const plotWidth = width - padding.left - padding.right;
    const plotHeight = height - padding.top - padding.bottom;
    const maxValue = Math.max(...series.flatMap(row => row.values || [0]), 0.1);
    const colors = ['#ffd166', '#57e5a7', '#4dd6ff', '#ff4d8d'];

    const xFor = (index) => padding.left + (plotWidth * index / Math.max(checkpoints.length - 1, 1));
    const yFor = (value) => padding.top + plotHeight - ((Number(value) || 0) / maxValue * plotHeight);

    const midpoint = Math.floor((checkpoints.length - 1) / 2);
    const axisLabels = checkpoints.map((checkpoint, index) => `
        <text class="timeline-checkpoint-label ${index === 0 || index === checkpoints.length - 1 ? 'is-edge' : ''} ${index === midpoint ? 'is-midpoint' : ''}" x="${xFor(index)}" y="${height - 24}" text-anchor="${index === 0 ? 'start' : index === checkpoints.length - 1 ? 'end' : 'middle'}">${escapeHtml(checkpoint.label || checkpoint.date || '')}</text>
    `).join('');

    const lineMarkup = series.map((row, seriesIndex) => {
        const values = Array.isArray(row.values) ? row.values : [];
        const points = values.map((value, index) => `${xFor(index).toFixed(1)},${yFor(value).toFixed(1)}`).join(' ');
        const finalValue = values.length ? values[values.length - 1] : 0;
        const color = colors[seriesIndex % colors.length];
        return `
            <g class="timeline-series" style="--series-color: ${color}; --series-delay: ${seriesIndex * 120}ms">
                <polyline pathLength="1" points="${points}"></polyline>
                ${values.map((value, index) => `<circle cx="${xFor(index).toFixed(1)}" cy="${yFor(value).toFixed(1)}" r="4"></circle>`).join('')}
            </g>
        `;
    }).join('');

    const legend = series.map((row, index) => `
        <div class="timeline-legend-item" style="--series-color: ${colors[index % colors.length]}">
            <span></span>${escapeHtml(row.username)}
        </div>
    `).join('');

    const finalRows = series
        .map(row => ({
            username: row.username,
            value: Number(row.values?.[row.values.length - 1] || 0),
        }))
        .sort((a, b) => b.value - a.value)
        .map((row, index) => `
            <div class="timeline-result-row">
                <span>${index + 1}</span>
                <strong>${escapeHtml(row.username)}</strong>
                <em>${escapeHtml(row.value.toFixed(3))}L</em>
            </div>
        `).join('');

    return `
        <div class="timeline-panel">
            <svg class="timeline-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="Leaderboard timeline">
                <g class="timeline-grid" aria-hidden="true">
                    <line x1="${padding.left}" y1="${padding.top}" x2="${padding.left}" y2="${height - padding.bottom}"></line>
                    <line x1="${padding.left}" y1="${height - padding.bottom}" x2="${width - padding.right}" y2="${height - padding.bottom}"></line>
                    <text x="${padding.left}" y="22">${escapeHtml(timeline.unit || 'Pure alcohol')}</text>
                    ${axisLabels}
                </g>
                ${lineMarkup}
            </svg>
            <div class="timeline-legend">${legend}</div>
            <div class="timeline-results" aria-label="Final logged ranking">${finalRows}</div>
        </div>
    `;
}

function calendarMarkup(calendar) {
    const weeks = Array.isArray(calendar?.weeks) ? calendar.weeks : [];
    if (!weeks.length) return '';

    const weekdays = Array.isArray(calendar.weekdays) && calendar.weekdays.length
        ? calendar.weekdays
        : ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
    const highlights = Array.isArray(calendar.highlights) ? calendar.highlights : [];
    const dayCells = weeks.flatMap(week => week).map((day, index) => {
        const entries = Number(day.entries || 0);
        const liters = Number(day.liters || 0);
        const level = Math.max(0, Math.min(1, Number(day.intensity || 0)));
        const classes = [
            'calendar-day',
            day.in_range ? '' : 'is-outside',
            entries ? 'is-active-day' : 'is-quiet-day',
            day.is_peak_entries ? 'is-peak-entries' : '',
            day.is_peak_liters ? 'is-peak-liters' : '',
        ].filter(Boolean).join(' ');
        const title = `${day.label || day.date}: ${entries} drinks, ${liters.toFixed(2)}L`;

        return `
            <div class="${classes}" style="--day-level: ${level.toFixed(3)}; --day-order: ${index}" title="${escapeHtml(title)}">
                <div class="calendar-day-top">
                    <span class="calendar-day-number">${escapeHtml(day.day)}</span>
                    <span class="calendar-day-month">${escapeHtml(day.month || '')}</span>
                </div>
                <div class="calendar-day-metric">
                    <strong>${escapeHtml(entries)}</strong>
                    <span>drinks</span>
                </div>
                <div class="calendar-day-liters">${escapeHtml(liters.toFixed(2))}L</div>
            </div>
        `;
    }).join('');

    const highlightMarkup = highlights.map(item => `
        <div class="calendar-highlight">
            <span>${escapeHtml(item.label)}</span>
            <strong>${escapeHtml(item.value)}</strong>
            <em>${escapeHtml(item.date)}</em>
        </div>
    `).join('');

    return `
        <div class="calendar-panel">
            <div class="calendar-panel-head">
                <div>
                    <span>Trip calendar</span>
                    <strong>${escapeHtml(calendar.month_label || '')}</strong>
                </div>
                <div class="calendar-legend" aria-label="Daily intensity">
                    <i></i><i></i><i></i><i></i>
                </div>
            </div>
            <div class="calendar-weekdays" aria-hidden="true">
                ${weekdays.map(day => `<span>${escapeHtml(day)}</span>`).join('')}
            </div>
            <div class="calendar-grid" aria-label="Drinks and liters by day">
                ${dayCells}
            </div>
            <div class="calendar-highlights">
                ${highlightMarkup}
            </div>
        </div>
    `;
}

function galleryMarkup(images = []) {
    if (!images.length) return '';
    return `
        <div class="gallery-window">
            <div class="gallery-grid">
                ${images.map(image => `<img src="${escapeHtml(image.src)}" alt="${escapeHtml(image.alt || '')}">`).join('')}
            </div>
        </div>
    `;
}

function multiImageMarkup(images = []) {
    if (!images.length) return '';
    return `
        <div class="multi-image-grid">
            ${images.map(image => `<img src="${escapeHtml(image.src)}" alt="${escapeHtml(image.alt || '')}">`).join('')}
        </div>
    `;
}

function contentMarkup(slide) {
    const extras = [
        dateRangeMarkup(slide.date_range),
        badgeMarkup(slide.badge),
        statMarkup(slide.stats),
        leaderboardMarkup(slide.leaderboard),
        locationMarkup(slide.locations),
    ].join('');

    const finale = slide.layout === 'finale'
        ? `<div class="finale-actions">
                <a id="go-app-btn" class="finale-btn" href="/">GO TO APP</a>
                <button id="share-btn" class="finale-btn secondary" type="button">SHARE</button>
           </div>`
        : '';

    return `
        <div class="slide-content">
            ${slide.kicker ? `<p class="slide-kicker">${escapeHtml(slide.kicker)}</p>` : ''}
            <h2 class="slide-title">${escapeHtml(slide.title || '')}</h2>
            ${slide.body ? `<p class="slide-body">${escapeHtml(slide.body)}</p>` : ''}
            ${extras}
            ${finale}
        </div>
    `;
}

function slideClass(slide) {
    const layout = slide.layout || 'stat';
    const layoutClass = `${layout}-slide`;
    return `slide ${layoutClass}`;
}

function renderSlide(slide, index) {
    const article = document.createElement('article');
    article.className = slideClass(slide);
    article.dataset.index = String(index);

    if (slide.layout === 'gallery') {
        article.innerHTML = contentMarkup(slide) + galleryMarkup(slide.images);
        return article;
    }

    if (slide.layout === 'timeline') {
        article.innerHTML = contentMarkup(slide) + timelineMarkup(slide.timeline);
        return article;
    }

    if (slide.layout === 'calendar') {
        article.innerHTML = contentMarkup(slide) + calendarMarkup(slide.calendar);
        return article;
    }

    if (slide.layout === 'multi-image') {
        article.innerHTML = contentMarkup(slide) + multiImageMarkup(slide.images);
        return article;
    }

    article.innerHTML = contentMarkup(slide) + imageMarkup(slide.image);
    return article;
}

function renderProgress() {
    progressTrack.style.setProperty('--slide-duration', `${slideDuration()}ms`);
    progressTrack.innerHTML = slides.map((_, index) => `
        <div class="progress-segment ${index < currentIndex ? 'complete' : ''} ${index === currentIndex ? 'active' : ''} ${index === currentIndex && !slideAutoAdvances(slides[index]) ? 'hold' : ''}">
            <div class="progress-fill"></div>
        </div>
    `).join('');
}

function slideAutoAdvances(slide) {
    return slide?.layout !== 'gallery';
}

function scheduleNext() {
    clearTimeout(timer);
    if (!started || paused || slides.length <= 1) return;
    if (currentIndex >= slides.length - 1) return;
    if (!slideAutoAdvances(slides[currentIndex])) return;
    timer = setTimeout(() => {
        goTo(currentIndex + 1);
    }, slideDuration());
}

function updateControls() {
    counter.textContent = `${currentIndex + 1} / ${slides.length}`;
    pauseBtn.innerHTML = paused ? ICONS.play : ICONS.pause;
    pauseBtn.setAttribute('aria-label', paused ? 'Resume reel' : 'Pause reel');
    audioBtn.innerHTML = audioReady && !audioMuted ? ICONS.volume : ICONS.muted;
    audioBtn.setAttribute('aria-label', audioMuted ? 'Unmute music' : 'Mute music');
    if (volumeControl) {
        volumeControl.hidden = !audioReady;
    }
}

function bindFinaleActions() {
    const shareBtn = document.getElementById('share-btn');

    if (!shareBtn) return;

    shareBtn.onclick = async () => {
        const shareData = {
            title: wrapped?.meta?.title || 'BeerRunJPN Wrapped',
            text: wrapped?.meta?.subtitle || 'The final trip recap',
            url: window.location.href,
        };

        try {
            if (navigator.share) {
                await navigator.share(shareData);
                return;
            }

            await navigator.clipboard?.writeText(window.location.href);
            shareBtn.textContent = 'COPIED';
        } catch (error) {
            shareBtn.textContent = 'LINK READY';
        } finally {
            setTimeout(() => { shareBtn.textContent = 'SHARE'; }, 1400);
        }
    };
}

function resetSlideScroll() {
    [...stage.querySelectorAll('.slide')].forEach((node) => {
        node.scrollTop = 0;
        node.scrollLeft = 0;
    });
    stage.scrollLeft = 0;
    app.scrollLeft = 0;
    document.documentElement.scrollLeft = 0;
    document.body.scrollLeft = 0;
}

function fitTextElement(element) {
    element.style.removeProperty('--fit-scale');
    element.style.removeProperty('--fit-width');

    const maxIterations = 18;
    const minScale = Number(element.dataset.minScale || 0.42);
    let low = minScale;
    let high = 1;
    let best = 1;

    const slide = element.closest('.slide');
    const content = element.closest('.slide-content');
    const parent = element.parentElement;
    const parentStyle = parent ? window.getComputedStyle(parent) : null;
    const parentInnerWidth = parent
        ? parent.clientWidth
            - Number.parseFloat(parentStyle?.paddingLeft || 0)
            - Number.parseFloat(parentStyle?.paddingRight || 0)
        : element.clientWidth;

    let availableWidth = Math.max(1, parentInnerWidth);
    if (slide && content) {
        const slideRect = slide.getBoundingClientRect();
        const contentRect = content.getBoundingClientRect();
        const slideStyle = window.getComputedStyle(slide);
        const visibleRight = slideRect.right - Number.parseFloat(slideStyle.paddingRight || 0);
        const remainingVisibleWidth = visibleRight - contentRect.left;
        availableWidth = Math.max(1, Math.min(availableWidth, remainingVisibleWidth));
    }

    if (element.classList.contains('image-caption')) {
        const figure = element.closest('.slide-media');
        availableWidth = Math.max(1, (figure?.clientWidth || availableWidth) - 28);
    }

    element.style.setProperty('--fit-width', `${Math.floor(availableWidth)}px`);

    const overflows = () => element.scrollWidth > element.clientWidth + 1;

    if (!overflows()) return;

    for (let index = 0; index < maxIterations; index += 1) {
        const scale = (low + high) / 2;
        element.style.setProperty('--fit-scale', scale.toFixed(3));
        if (overflows()) {
            high = scale;
        } else {
            best = scale;
            low = scale;
        }
    }

    element.style.setProperty('--fit-scale', best.toFixed(3));
}

function fitSlideText() {
    stage.querySelectorAll('.slide-title, .slide-kicker, .slide-body, .story-badge, .stat-value, .stat-label, .leader-name, .location-name, .image-caption, .date-label, .date-node strong').forEach(fitTextElement);
}

function updateGalleryMotion() {
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    stage.querySelectorAll('.gallery-window').forEach((windowNode) => {
        const grid = windowNode.querySelector('.gallery-grid');
        if (!grid) return;

        const scrollDistance = Math.max(0, grid.scrollHeight - windowNode.clientHeight);
        const canScroll = scrollDistance > 8 && !reduceMotion;
        grid.style.setProperty('--gallery-scroll-distance', `${Math.ceil(scrollDistance)}px`);
        grid.style.setProperty('--gallery-scroll-duration', `${Math.max(20000, slideDuration())}ms`);
        grid.classList.toggle('is-scrollable', canScroll);
    });
}

function queueGalleryMotionUpdate() {
    window.requestAnimationFrame(() => {
        updateGalleryMotion();
        fitSlideText();
        window.setTimeout(updateGalleryMotion, 250);
        window.setTimeout(fitSlideText, 250);
    });
}

function blurNavigationButton() {
    if (document.activeElement instanceof HTMLElement) {
        document.activeElement.blur();
    }
}

function goTo(nextIndex) {
    if (!slides.length) return;
    blurNavigationButton();

    const previousIndex = currentIndex;
    if (nextIndex < 0) nextIndex = slides.length - 1;
    if (nextIndex >= slides.length) nextIndex = 0;
    currentIndex = nextIndex;

    const direction = currentIndex < previousIndex ? 'reverse' : '';
    [...stage.querySelectorAll('.slide')].forEach((node, index) => {
        node.scrollTop = 0;
        node.scrollLeft = 0;
        node.classList.toggle('active', index === currentIndex);
        node.classList.toggle('reverse', direction === 'reverse' && index === currentIndex);
    });
    resetSlideScroll();

    renderProgress();
    updateControls();
    bindFinaleActions();
    queueGalleryMotionUpdate();
    fitSlideText();
    scheduleNext();
}

async function setupAudio() {
    const audioPath = wrapped?.meta?.audio_path;
    if (!audioPath) {
        audioBtn.style.display = 'none';
        return;
    }

    try {
        const probe = await fetch(audioPath, { method: 'HEAD' });
        if (!probe.ok) throw new Error('Audio file not found');
        audio = new Audio(audioPath);
        audio.loop = true;
        audio.volume = audioVolume;
        await audio.play();
        audioReady = true;
    } catch (error) {
        audio = null;
        audioReady = false;
        audioBtn.style.display = 'none';
        if (volumeControl) volumeControl.hidden = true;
    }
}

async function startReel() {
    if (!slides.length) return;
    started = true;
    paused = false;
    startScreen.classList.add('hidden');
    await setupAudio();
    updateControls();
    goTo(0);
}

function togglePause() {
    if (!started) return;
    paused = !paused;
    app.classList.toggle('paused', paused);
    if (paused) {
        clearTimeout(timer);
    } else {
        scheduleNext();
    }
    updateControls();
}

function toggleAudio() {
    if (!audioReady || !audio) return;
    audioMuted = !audioMuted;
    audio.muted = audioMuted;
    updateControls();
}

function setAudioVolume(value) {
    audioVolume = Math.max(0, Math.min(1, Number(value) / 100));
    if (audio) {
        audio.volume = audioVolume;
        if (audioVolume > 0 && audioMuted) {
            audioMuted = false;
            audio.muted = false;
        }
    }
    updateControls();
}

function renderEmptyState(message) {
    stage.innerHTML = `<div class="empty-state">${escapeHtml(message)}</div>`;
}

async function loadWrapped() {
    startBtn.disabled = true;
    startBtn.textContent = 'LOADING';

    try {
        const response = await fetch('/api/wrapped');
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        wrapped = await response.json();
        slides = Array.isArray(wrapped.slides) ? wrapped.slides : [];

        if (!slides.length) {
            renderEmptyState('Wrapped has no slides yet.');
            return;
        }

        stage.innerHTML = '';
        slides.forEach((slide, index) => stage.appendChild(renderSlide(slide, index)));
        stage.querySelectorAll('.gallery-grid img').forEach((image) => {
            image.addEventListener('load', queueGalleryMotionUpdate, { once: true });
        });
        stage.querySelector('.slide')?.classList.add('active');
        renderProgress();
        updateControls();
        queueGalleryMotionUpdate();
        fitSlideText();
        startBtn.disabled = false;
        startBtn.textContent = 'START REEL';
    } catch (error) {
        renderEmptyState('Wrapped data could not be loaded. Run the generator and try again.');
        startBtn.textContent = 'UNAVAILABLE';
    }
}

startBtn.addEventListener('click', startReel);
prevBtn.addEventListener('click', (event) => {
    event.stopPropagation();
    goTo(currentIndex - 1);
});
nextBtn.addEventListener('click', (event) => {
    event.stopPropagation();
    goTo(currentIndex + 1);
});
prevZone.addEventListener('click', () => goTo(currentIndex - 1));
nextZone.addEventListener('click', () => goTo(currentIndex + 1));
pauseBtn.addEventListener('click', togglePause);
audioBtn.addEventListener('click', toggleAudio);
volumeSlider?.addEventListener('input', (event) => setAudioVolume(event.target.value));
window.addEventListener('resize', () => {
    queueGalleryMotionUpdate();
    fitSlideText();
});
stage.addEventListener('click', (event) => {
    if (!started) return;
    if (currentIndex >= slides.length - 1) return;
    if (event.target.closest('button, a, input, label, .wrapped-controls, .wrapped-topbar')) return;
    goTo(currentIndex + 1);
});

document.addEventListener('keydown', (event) => {
    if (event.key === 'ArrowLeft') goTo(currentIndex - 1);
    if (event.key === 'ArrowRight') goTo(currentIndex + 1);
    if (event.key === ' ') {
        event.preventDefault();
        togglePause();
    }
});

let touchStartX = 0;
document.addEventListener('touchstart', (event) => {
    touchStartX = event.changedTouches[0]?.clientX || 0;
}, { passive: true });

document.addEventListener('touchend', (event) => {
    const touchEndX = event.changedTouches[0]?.clientX || 0;
    const delta = touchEndX - touchStartX;
    if (Math.abs(delta) < 48) return;
    goTo(delta > 0 ? currentIndex - 1 : currentIndex + 1);
}, { passive: true });

loadWrapped();
