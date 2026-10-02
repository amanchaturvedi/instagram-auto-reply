const summaryEl = document.getElementById("summary");
const reelsBody = document.getElementById("reels-body");
const statusEl = document.getElementById("status");
const collectBtn = document.getElementById("collect-btn");
const refreshBtn = document.getElementById("refresh-btn");
const detailPanel = document.getElementById("detail-panel");
const detailTitle = document.getElementById("detail-title");
const detailMeta = document.getElementById("detail-meta");
const detailJson = document.getElementById("detail-json");
const closeDetail = document.getElementById("close-detail");

function formatNumber(value) {
    if (value === null || value === undefined) return "—";
    return new Intl.NumberFormat("en-IN").format(value);
}

function formatPercent(value) {
    return value === null || value === undefined ? "—" : value.toFixed(2) + "%";
}

function formatSeconds(value) {
    return value === null || value === undefined ? "—" : value.toFixed(2) + "s";
}

function formatDate(value) {
    if (!value) return "—";
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

function renderSummary(data) {
    summaryEl.innerHTML =
        '<div class="card">' +
            '<div class="card-label">Reels tracked</div>' +
            '<div class="card-value">' + formatNumber(data.reels_tracked) + '</div>' +
        '</div>' +
        '<div class="card">' +
            '<div class="card-label">Latest collected</div>' +
            '<div class="card-value">' + formatDate(data.last_updated) + '</div>' +
        '</div>' +
        '<div class="card">' +
            '<div class="card-label">Total current views</div>' +
            '<div class="card-value">' + formatNumber(data.total_views) + '</div>' +
        '</div>';
}

function renderReels(reels) {
    if (!reels.length) {
        reelsBody.innerHTML = '<tr><td colspan="10" class="empty">No Reel insights collected yet.</td></tr>';
        return;
    }

    reelsBody.innerHTML = reels.map(function(reel) {
        const metrics = reel.metrics || {};

        return '<tr data-media-id="' + escapeHtml(reel.media_id) + '">' +
            '<td>' +
                '<div class="reel-title">' + escapeHtml(reel.caption || reel.media_id) + '</div>' +
                '<div class="reel-date">' + formatDate(reel.timestamp) + '</div>' +
            '</td>' +
            '<td>' + formatNumber(metrics.views) + '</td>' +
            '<td>' + formatNumber(metrics.reach) + '</td>' +
            '<td>' + formatNumber(metrics.likes) + '</td>' +
            '<td>' + formatNumber(metrics.comments) + '</td>' +
            '<td>' + formatNumber(metrics.shares) + '</td>' +
            '<td>' + formatNumber(metrics.saved) + '</td>' +
            '<td>' + formatSeconds(metrics.avg_watch_time_seconds) + '</td>' +
            '<td>' + formatPercent(metrics.skip_rate) + '</td>' +
            '<td>' + formatPercent(metrics.engagement_rate) + '</td>' +
        '</tr>';
    }).join("");

    reelsBody.querySelectorAll("tr[data-media-id]").forEach(function(row) {
        row.addEventListener("click", function() {
            openDetail(row.dataset.mediaId);
        });
    });
}

async function loadDashboard() {
    statusEl.textContent = "Loading…";

    try {
        const responses = await Promise.all([
            fetch("/api/dashboard"),
            fetch("/api/reels"),
        ]);

        if (!responses[0].ok || !responses[1].ok) {
            throw new Error("Dashboard request failed");
        }

        const summary = await responses[0].json();
        const reels = await responses[1].json();

        renderSummary(summary);
        renderReels(reels.reels);
        statusEl.textContent = "Ready";
    } catch (error) {
        statusEl.textContent = error.message;
    }
}

async function openDetail(mediaId) {
    try {
        const response = await fetch("/api/reels/" + encodeURIComponent(mediaId));

        if (!response.ok) {
            throw new Error("Could not load Reel");
        }

        const reel = await response.json();

        detailTitle.textContent = reel.caption || reel.media_id;
        detailMeta.textContent = reel.media_id + " · " + formatDate(reel.timestamp);
        detailJson.textContent = JSON.stringify(reel, null, 2);
        detailPanel.classList.remove("hidden");
        detailPanel.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (error) {
        statusEl.textContent = error.message;
    }
}

async function collectInsights() {
    collectBtn.disabled = true;
    refreshBtn.disabled = true;
    statusEl.textContent = "Collecting…";

    try {
        const response = await fetch("/api/insights/collect", { method: "POST" });

        if (!response.ok) {
            const body = await response.text();
            throw new Error(body || "Insights collection failed");
        }

        await loadDashboard();
    } catch (error) {
        statusEl.textContent = error.message;
    } finally {
        collectBtn.disabled = false;
        refreshBtn.disabled = false;
    }
}

function escapeHtml(value) {
    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

collectBtn.addEventListener("click", collectInsights);
refreshBtn.addEventListener("click", loadDashboard);
closeDetail.addEventListener("click", function() {
    detailPanel.classList.add("hidden");
});

loadDashboard();
