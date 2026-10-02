const summaryEl = document.getElementById("summary");
const reelsBody = document.getElementById("reels-body");
const statusEl = document.getElementById("status");
const refreshReelsBtn = document.getElementById("refresh-reels-btn");

const reelModal = document.getElementById("reel-modal");
const reelModalTitle = document.getElementById("reel-modal-title");
const reelModalMeta = document.getElementById("reel-modal-meta");
const reelCurrentMetrics = document.getElementById("reel-current-metrics");
const snapshotsBody = document.getElementById("snapshots-body");
const closeReelModal = document.getElementById("close-reel-modal");

const commentsModal = document.getElementById("comments-modal");
const commentsModalTitle = document.getElementById("comments-modal-title");
const commentsModalMeta = document.getElementById("comments-modal-meta");
const commentsList = document.getElementById("comments-list");
const closeCommentsModal = document.getElementById("close-comments-modal");

function formatNumber(value) {
    if (value === null || value === undefined) return "—";
    return new Intl.NumberFormat("en-IN").format(value);
}

function formatPercent(value) {
    return value === null || value === undefined ? "—" : Number(value).toFixed(2) + "%";
}

function formatSeconds(value) {
    return value === null || value === undefined ? "—" : Number(value).toFixed(2) + "s";
}

function formatTime(value) {
    if (!value) return "—";

    const date = new Date(value);

    if (Number.isNaN(date.getTime())) return value;

    const formatted = new Intl.DateTimeFormat("en-IN", {
        timeZone: "Asia/Kolkata",
        hour: "2-digit",
        minute: "2-digit",
        hour12: true,
    }).format(date);

    return formatted.replace(/am/i, "AM").replace(/pm/i, "PM");
}

function shortText(value, limit) {
    const text = String(value || "").replace(/\s+/g, " ").trim();

    if (text.length <= limit) return text;

    return text.slice(0, limit - 1) + "…";
}

function escapeHtml(value) {
    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

function renderSummary(data) {
    summaryEl.innerHTML =
        '<div class="card">' +
            '<div class="card-label">Reels tracked</div>' +
            '<div class="card-value">' + formatNumber(data.reels_tracked) + '</div>' +
        '</div>' +
        '<div class="card">' +
            '<div class="card-label">Reels refreshed</div>' +
            '<div class="card-value">' + formatTime(data.catalog_last_updated) + '</div>' +
        '</div>' +
        '<div class="card">' +
            '<div class="card-label">Insights refreshed</div>' +
            '<div class="card-value">' + formatTime(data.insights_last_updated) + '</div>' +
        '</div>';
}

function renderReels(reels) {
    if (!reels.length) {
        reelsBody.innerHTML = '<tr><td colspan="12" class="empty">No Reels found. Click Refresh reels.</td></tr>';
        return;
    }

    reelsBody.innerHTML = reels.map(function(reel) {
        const metrics = reel.metrics || {};
        const hasInsights = metrics.views !== null && metrics.views !== undefined;

        return '<tr data-media-id="' + escapeHtml(reel.media_id) + '">' +
            '<td class="reel-cell">' +
                '<div class="reel-title">' + escapeHtml(shortText(reel.caption || reel.media_id, 90)) + '</div>' +
            '</td>' +
            '<td>' + formatTime(reel.timestamp) + '</td>' +
            '<td>' + formatNumber(metrics.views) + '</td>' +
            '<td>' + formatNumber(metrics.reach) + '</td>' +
            '<td>' + formatNumber(metrics.likes) + '</td>' +
            '<td>' + formatNumber(metrics.comments) + '</td>' +
            '<td>' + formatNumber(metrics.shares) + '</td>' +
            '<td>' + formatNumber(metrics.saved) + '</td>' +
            '<td>' + formatSeconds(metrics.avg_watch_time_seconds) + '</td>' +
            '<td>' + formatPercent(metrics.skip_rate) + '</td>' +
            '<td>' + formatPercent(metrics.engagement_rate) + '</td>' +
            '<td class="actions-cell">' +
                '<button class="table-button refresh-one" data-media-id="' + escapeHtml(reel.media_id) + '" ' + (hasInsights ? '' : 'title="Fetch insights"') + '>Refresh</button>' +
                '<button class="table-button comments-one" data-media-id="' + escapeHtml(reel.media_id) + '">Comments</button>' +
            '</td>' +
        '</tr>';
    }).join("");

    reelsBody.querySelectorAll("tr[data-media-id]").forEach(function(row) {
        row.addEventListener("click", function(event) {
            if (event.target.closest("button")) return;
            openReel(row.dataset.mediaId);
        });
    });

    reelsBody.querySelectorAll(".refresh-one").forEach(function(button) {
        button.addEventListener("click", function(event) {
            event.stopPropagation();
            refreshOneReel(button.dataset.mediaId, button);
        });
    });

    reelsBody.querySelectorAll(".comments-one").forEach(function(button) {
        button.addEventListener("click", function(event) {
            event.stopPropagation();
            openComments(button.dataset.mediaId);
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

async function refreshReels() {
    refreshReelsBtn.disabled = true;
    statusEl.textContent = "Refreshing reels…";

    try {
        const response = await fetch("/api/reels/refresh", { method: "POST" });

        if (!response.ok) {
            const body = await response.text();
            throw new Error(body || "Could not refresh reels");
        }

        const result = await response.json();

        await loadDashboard();

        statusEl.textContent =
            result.added + " new Reel" + (result.added === 1 ? "" : "s") + " found";
    } catch (error) {
        statusEl.textContent = error.message;
    } finally {
        refreshReelsBtn.disabled = false;
    }
}

async function refreshOneReel(mediaId, button) {
    const original = button.textContent;
    button.disabled = true;
    button.textContent = "…";
    statusEl.textContent = "Refreshing Reel…";

    try {
        const response = await fetch(
            "/api/reels/" + encodeURIComponent(mediaId) + "/refresh",
            { method: "POST" }
        );

        if (!response.ok) {
            const body = await response.text();
            throw new Error(body || "Could not refresh Reel");
        }

        await loadDashboard();
        statusEl.textContent = "Reel refreshed";
    } catch (error) {
        statusEl.textContent = error.message;
    } finally {
        button.disabled = false;
        button.textContent = original;
    }
}

async function openReel(mediaId) {
    try {
        const response = await fetch("/api/reels/" + encodeURIComponent(mediaId));

        if (!response.ok) {
            throw new Error("Could not load Reel");
        }

        const reel = await response.json();
        const metrics = reel.metrics || {};

        reelModalTitle.textContent = shortText(reel.caption || reel.media_id, 100);
        reelModalMeta.textContent =
            "Posted " + formatTime(reel.timestamp) +
            " · Last refresh " + formatTime(reel.last_collected_at);

        reelCurrentMetrics.innerHTML =
            metricCard("Views", formatNumber(metrics.views)) +
            metricCard("Reach", formatNumber(metrics.reach)) +
            metricCard("Likes", formatNumber(metrics.likes)) +
            metricCard("Comments", formatNumber(metrics.comments)) +
            metricCard("Shares", formatNumber(metrics.shares)) +
            metricCard("Saves", formatNumber(metrics.saved)) +
            metricCard("Avg watch", formatSeconds(metrics.avg_watch_time_seconds)) +
            metricCard("Skip rate", formatPercent(metrics.skip_rate)) +
            metricCard("Engagement", formatPercent(metrics.engagement_rate));

        const snapshots = reel.snapshots || [];

        if (!snapshots.length) {
            snapshotsBody.innerHTML =
                '<tr><td colspan="9" class="empty">No snapshots yet. Refresh this Reel to collect insights.</td></tr>';
        } else {
            snapshotsBody.innerHTML = snapshots.slice().reverse().map(function(snapshot) {
                const m = snapshot.metrics || {};

                return '<tr>' +
                    '<td>' + formatTime(snapshot.collected_at) + '</td>' +
                    '<td>' + formatNumber(m.views) + '</td>' +
                    '<td>' + formatNumber(m.reach) + '</td>' +
                    '<td>' + formatNumber(m.likes) + '</td>' +
                    '<td>' + formatNumber(m.comments) + '</td>' +
                    '<td>' + formatNumber(m.shares) + '</td>' +
                    '<td>' + formatNumber(m.saved) + '</td>' +
                    '<td>' + formatSeconds((m.avg_watch_time_ms || null) === null ? null : m.avg_watch_time_ms / 1000) + '</td>' +
                    '<td>' + formatPercent(m.skip_rate) + '</td>' +
                '</tr>';
            }).join("");
        }

        reelModal.classList.remove("hidden");
    } catch (error) {
        statusEl.textContent = error.message;
    }
}

function metricCard(label, value) {
    return '<div class="metric-card">' +
        '<div class="metric-label">' + label + '</div>' +
        '<div class="metric-value">' + value + '</div>' +
    '</div>';
}

async function openComments(mediaId) {
    commentsModalTitle.textContent = "Comments";
    commentsModalMeta.textContent = mediaId;
    commentsList.innerHTML = '<div class="loading">Loading comments…</div>';
    commentsModal.classList.remove("hidden");

    try {
        const response = await fetch(
            "/api/reels/" + encodeURIComponent(mediaId) + "/comments?limit=20"
        );

        if (!response.ok) {
            const body = await response.text();
            throw new Error(body || "Could not load comments");
        }

        const data = await response.json();

        if (!data.comments.length) {
            commentsList.innerHTML = '<div class="empty">No comments returned.</div>';
            return;
        }

        commentsList.innerHTML = data.comments.map(function(comment) {
            return '<div class="comment-item">' +
                '<div class="comment-head">' +
                    '<strong>' + escapeHtml(comment.username || "unknown") + '</strong>' +
                    '<span>' + formatTime(comment.timestamp) + '</span>' +
                '</div>' +
                '<div class="comment-text">' + escapeHtml(comment.text || "") + '</div>' +
            '</div>';
        }).join("");
    } catch (error) {
        commentsList.innerHTML = '<div class="empty">' + escapeHtml(error.message) + '</div>';
    }
}

function closeModal(modal) {
    modal.classList.add("hidden");
}

refreshReelsBtn.addEventListener("click", refreshReels);

closeReelModal.addEventListener("click", function() {
    closeModal(reelModal);
});

closeCommentsModal.addEventListener("click", function() {
    closeModal(commentsModal);
});

reelModal.addEventListener("click", function(event) {
    if (event.target === reelModal) closeModal(reelModal);
});

commentsModal.addEventListener("click", function(event) {
    if (event.target === commentsModal) closeModal(commentsModal);
});

document.addEventListener("keydown", function(event) {
    if (event.key === "Escape") {
        closeModal(reelModal);
        closeModal(commentsModal);
    }
});

loadDashboard();
