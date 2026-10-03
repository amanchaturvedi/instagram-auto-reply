const aiChatMessages = document.getElementById("ai-chat-messages");
const aiChatInput = document.getElementById("ai-chat-input");
const aiChatSendBtn = document.getElementById("ai-chat-send-btn");
const aiChatClearBtn = document.getElementById("ai-chat-clear-btn");
const aiChatStatus = document.getElementById("ai-chat-status");
let aiChatHistory = [];

function renderChatMessage(role, content, structured) {
    if (aiChatMessages.querySelector(".chat-empty")) {
        aiChatMessages.innerHTML = "";
    }
    const message = document.createElement("div");
    message.className = "chat-message " + (role === "user" ? "user" : "assistant");

    let body = '<div class="chat-role">' + (role === "user" ? "You" : "AI") + '</div>';

    if (role === "assistant" && structured) {
        body += renderStructuredAi(structured, true);
    } else {
        body += '<div class="chat-content">' + escapeHtml(content) + '</div>';
    }

    message.innerHTML = body;
    aiChatMessages.appendChild(message);
    aiChatMessages.scrollTop = aiChatMessages.scrollHeight;
}

function renderAiList(items, fields) {
    if (!Array.isArray(items) || !items.length) return '<div class="ai-muted">No supported items.</div>';

    return '<div class="ai-list">' + items.map(function(item) {
        if (typeof item === "string") {
            return '<div class="ai-list-item">' + escapeHtml(item) + '</div>';
        }

        const title = item.title || item.test || "Item";
        let html = '<div class="ai-list-item"><div class="ai-item-title">' + escapeHtml(title) + '</div>';

        fields.forEach(function(field) {
            if (item[field] !== undefined && item[field] !== null && item[field] !== "") {
                html += '<div class="ai-item-detail"><span>' +
                    escapeHtml(field.replaceAll("_", " ")) + '</span>' +
                    escapeHtml(String(item[field])) +
                '</div>';
            }
        });

        html += '</div>';
        return html;
    }).join("") + '</div>';
}

function renderStructuredAi(data, compact) {
    if (!data || typeof data !== "object") {
        return '<div class="ai-content">No structured analysis returned.</div>';
    }

    let html = '<div class="' + (compact ? 'ai-chat-structured' : 'ai-structured') + '">';

    if (data.summary) {
        html += '<div class="ai-summary">' + escapeHtml(data.summary) + '</div>';
    }

    if (Array.isArray(data.what_changed)) {
        html += '<section class="ai-section"><h3>What changed</h3>' +
            renderAiList(data.what_changed, ["detail", "sample_size"]) + '</section>';
    }

    if (Array.isArray(data.patterns)) {
        html += '<section class="ai-section"><h3>Patterns worth testing</h3>' +
            renderAiList(data.patterns, ["detail", "sample_size"]) + '</section>';
    }

    if (Array.isArray(data.observations)) {
        html += '<section class="ai-section"><h3>Observations</h3>' +
            renderAiList(data.observations, ["detail"]) + '</section>';
    }

    if (Array.isArray(data.working)) {
        html += '<section class="ai-section"><h3>What’s working</h3>' +
            renderAiList(data.working, ["detail"]) + '</section>';
    }

    if (Array.isArray(data.possible_weaknesses)) {
        html += '<section class="ai-section"><h3>Possible weaknesses</h3>' +
            renderAiList(data.possible_weaknesses, ["detail"]) + '</section>';
    }

    if (Array.isArray(data.possible_causes)) {
        html += '<section class="ai-section"><h3>Possible causes</h3>' +
            renderAiList(data.possible_causes, ["detail"]) + '</section>';
    }

    if (Array.isArray(data.hypotheses)) {
        html += '<section class="ai-section"><h3>Hypotheses</h3>' +
            renderAiList(data.hypotheses, ["detail"]) + '</section>';
    }

    if (Array.isArray(data.experiments)) {
        html += '<section class="ai-section"><h3>Experiments</h3>' +
            renderAiList(data.experiments, ["why", "metric"]) + '</section>';
    }

    if (Array.isArray(data.metrics_to_monitor)) {
        html += '<section class="ai-section"><h3>Metrics to monitor</h3>' +
            renderAiList(data.metrics_to_monitor, []) + '</section>';
    }

    html += '</div>';
    return html;
}

function aiResponseToHistory(data) {
    if (!data || typeof data !== "object") return "";
    const parts = [];
    if (data.summary) parts.push(data.summary);

    ["observations", "what_changed", "patterns", "working", "possible_weaknesses", "possible_causes", "hypotheses"].forEach(function(key) {
        (data[key] || []).forEach(function(item) {
            if (typeof item === "string") parts.push(item);
            else if (item.detail) parts.push((item.title ? item.title + ": " : "") + item.detail);
        });
    });

    (data.experiments || []).forEach(function(item) {
        if (typeof item === "string") parts.push(item);
        else parts.push(
            (item.test || "Experiment") +
            (item.why ? " — " + item.why : "") +
            (item.metric ? " — measure " + item.metric : "")
        );
    });

    return parts.join("\n");
}

function renderRetrievedReels(reels) {
    if (!Array.isArray(reels) || !reels.length) return "";

    return '<section class="ai-section chat-retrieved"><h3>Reels referenced</h3>' +
        '<div class="ai-retrieved-grid">' +
        reels.map(function(reel) {
            const metrics = reel.latest_metrics || reel["24h_metrics"] || {};
            return '<div class="ai-retrieved-card">' +
                '<div class="ai-retrieved-rank">Reel ' + escapeHtml(String(reel.rank || "")) + '</div>' +
                '<div class="ai-item-title">' + escapeHtml(shortText(reel.caption || reel.media_id, 100)) + '</div>' +
                '<div class="ai-retrieved-meta">' +
                    escapeHtml(reel.media_id || "") +
                    (reel.timestamp ? ' · ' + escapeHtml(formatPosted(reel.timestamp)) : '') +
                '</div>' +
                '<div class="ai-retrieved-metrics">' +
                    '<span>Views ' + formatNumber(metrics.views) + '</span>' +
                    '<span>Reach ' + formatNumber(metrics.reach) + '</span>' +
                    '<span>Likes ' + formatNumber(metrics.likes) + '</span>' +
                '</div>' +
            '</div>';
        }).join("") +
        '</div></section>';
}

function clearAiChat() {
    aiChatHistory = [];
    aiChatMessages.innerHTML =
        '<div class="chat-empty">Ask something like “Why are my recent Reels underperforming?” or “Which of my Reels had the strongest engagement?”</div>';
    aiChatStatus.textContent = "Ready";
}

async function sendAiChat() {
    const message = aiChatInput.value.trim();
    if (!message || aiChatSendBtn.disabled) return;

    renderChatMessage("user", message);
    aiChatHistory.push({ role: "user", content: message });
    aiChatInput.value = "";
    setButtonLoading(aiChatSendBtn, true, "Thinking…");
    aiChatStatus.textContent = "Retrieving relevant Reels and analyzing…";

    try {
        const response = await fetch("/api/ai/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                message: message,
                history: aiChatHistory.slice(-8),
            }),
        });
        const body = await response.json();
        if (!response.ok) throw new Error(body.detail || "AI chat failed");

        renderChatMessage("assistant", aiResponseToHistory(body.analysis), body.analysis);
        const retrievedHtml = renderRetrievedReels(body.retrieved_reels || []);\n        if (retrievedHtml) {\n            const lastMessage = aiChatMessages.lastElementChild;\n            if (lastMessage) lastMessage.insertAdjacentHTML("beforeend", retrievedHtml);\n        }\n        aiChatHistory.push({ role: "assistant", content: aiResponseToHistory(body.analysis) });

        const retrieved = body.retrieved_reels ? body.retrieved_reels.length : 0;
        aiChatStatus.textContent =
            "Answered · " + formatNumber(retrieved) + " historical Reels retrieved";
        setStatus("AI chat complete");
    } catch (error) {
        renderChatMessage("assistant", "Error: " + error.message);
        aiChatStatus.textContent = "Chat failed";
        setStatus(error.message);
    } finally {
        setButtonLoading(aiChatSendBtn, false);
    }
}

const aiReelSelect = document.getElementById("ai-reel-select");
const aiReelBtn = document.getElementById("ai-reel-btn");
const aiAccountBtn = document.getElementById("ai-account-btn");
const aiOutput = document.getElementById("ai-output");
const aiStatus = document.getElementById("ai-status");

function renderAiReelOptions(reels) {
    aiReelSelect.innerHTML = '<option value="">Select a Reel</option>' +
        reels.map(function(reel) {
            return '<option value="' + escapeHtml(reel.media_id) + '">' +
                escapeHtml(shortText(reel.caption || reel.media_id, 80)) +
            '</option>';
        }).join("");
}

async function runAi(endpoint, button, loadingLabel) {
    setButtonLoading(button, true, loadingLabel);
    aiStatus.textContent = "Running local AI analysis…";
    aiOutput.classList.remove("empty");
    aiOutput.innerHTML = '<div class="loading-indicator"><span class="loader"></span><span>Analyzing your Instagram data…</span></div>';
    try {
        const response = await fetch(endpoint, { method: "POST" });
        const body = await response.json();
        if (!response.ok) throw new Error(body.detail || "AI analysis failed");
        aiOutput.innerHTML = renderStructuredAi(body.analysis, false);
        if (body.reels_analyzed !== undefined) {
            const coverage = body.reels_with_24h_snapshot !== undefined
                ? " · " + formatNumber(body.reels_with_24h_snapshot) + " with 24h snapshots"
                : "";
            const source = body.analysis_metric_source
                ? " · " + body.analysis_metric_source + " metrics"
                : "";
            aiStatus.textContent =
                "Analysis complete · " +
                formatNumber(body.reels_analyzed) +
                " Reels analyzed" +
                coverage +
                source;
        } else {
            aiStatus.textContent = "Analysis complete";
        }
        setStatus("AI analysis complete");
    } catch (error) {
        aiOutput.textContent = error.message;
        aiStatus.textContent = "Analysis failed";
        setStatus(error.message);
    } finally {
        setButtonLoading(button, false);
    }
}

async function loadAiReels() {
    try {
        const response = await fetch("/api/reels");
        if (!response.ok) throw new Error("Could not load Reels");
        const data = await response.json();
        renderAiReelOptions(data.reels || []);
    } catch (error) {
        aiStatus.textContent = error.message;
    }
}

const statusEl = document.getElementById("status");

const tabButtons = document.querySelectorAll(".tab-button");
const tabPanels = document.querySelectorAll(".tab-panel");

const summaryEl = document.getElementById("summary");
const reelsBody = document.getElementById("reels-body");
const refreshReelsBtn = document.getElementById("refresh-reels-btn");

const commentsBody = document.getElementById("comments-body");
const refreshCommentsBtn = document.getElementById("refresh-comments-btn");
const replyCommentsBtn = document.getElementById("reply-comments-btn");
const commentLimitInput = document.getElementById("comment-limit-input");
const saveConfigBtn = document.getElementById("save-config-btn");
const configReelsBody = document.getElementById("config-reels-body");
const configReelsCount = document.getElementById("config-reels-count");

const configUsernameEl = document.getElementById("config-username");
const configUserIdEl = document.getElementById("config-user-id");

const reelModal = document.getElementById("reel-modal");
const reelModalTitle = document.getElementById("reel-modal-title");
const reelModalMeta = document.getElementById("reel-modal-meta");
const reelCurrentMetrics = document.getElementById("reel-current-metrics");
const snapshotsBody = document.getElementById("snapshots-body");
const closeReelModal = document.getElementById("close-reel-modal");

let commentsLoaded = false;

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

function formatPosted(value) {
    if (!value) return "—";

    const date = new Date(value);

    if (Number.isNaN(date.getTime())) return value;

    const parts = new Intl.DateTimeFormat("en-IN", {
        timeZone: "Asia/Kolkata",
        weekday: "short",
        hour: "2-digit",
        minute: "2-digit",
        hour12: true,
    }).formatToParts(date);

    const lookup = {};
    parts.forEach(function(part) {
        lookup[part.type] = part.value;
    });

    const period = String(lookup.dayPeriod || "").toUpperCase();

    return lookup.hour + ":" + lookup.minute + " " + period + " " + lookup.weekday;
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

function setStatus(message) {
    if (statusEl) {
        statusEl.textContent = message;
    }
}

function setButtonLoading(button, loading, label) {
    if (!button) return;

    if (loading) {
        if (!button.dataset.loadingOriginal) {
            button.dataset.loadingOriginal = button.innerHTML;
        }

        button.disabled = true;
        button.innerHTML =
            '<span class="button-loading">' +
                '<span class="button-spinner" aria-hidden="true"></span>' +
                '<span>' + escapeHtml(label) + '</span>' +
            '</span>';
        return;
    }

    if (button.dataset.loadingOriginal) {
        button.innerHTML = button.dataset.loadingOriginal;
        delete button.dataset.loadingOriginal;
    }

    button.disabled = false;
}

function metricCard(label, value) {
    return '<div class="metric-card">' +
        '<div class="metric-label">' + label + '</div>' +
        '<div class="metric-value">' + value + '</div>' +
    '</div>';
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
            '<td>' + formatPosted(reel.timestamp) + '</td>' +
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
}

async function loadDashboard() {
    setStatus("Loading insights…");

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
        setStatus("Ready");
    } catch (error) {
        setStatus(error.message);
    }
}

async function refreshReels() {
    setButtonLoading(refreshReelsBtn, true, "Refreshing…");
    setStatus("Refreshing reels…");

    try {
        const response = await fetch("/api/reels/refresh", { method: "POST" });

        if (!response.ok) {
            const body = await response.text();
            throw new Error(body || "Could not refresh reels");
        }

        const result = await response.json();

        await loadDashboard();
        await loadConfig();

        setStatus(
            result.added + " new Reel" + (result.added === 1 ? "" : "s") + " found"
        );
    } catch (error) {
        setStatus(error.message);
    } finally {
        setButtonLoading(refreshReelsBtn, false);
    }
}

async function refreshOneReel(mediaId, button) {
    setButtonLoading(button, true, "Refreshing…");
    setStatus("Refreshing Reel…");

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
        setStatus("Reel refreshed");
    } catch (error) {
        setStatus(error.message);
    } finally {
        setButtonLoading(button, false);
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
                    '<td>' + formatSeconds(m.avg_watch_time_ms === null || m.avg_watch_time_ms === undefined ? null : m.avg_watch_time_ms / 1000) + '</td>' +
                    '<td>' + formatPercent(m.skip_rate) + '</td>' +
                '</tr>';
            }).join("");
        }

        reelModal.classList.remove("hidden");
    } catch (error) {
        setStatus(error.message);
    }
}

function renderComments(data) {

    const reels = Object.values(data.reels || {}).sort(function(a, b) {
        return String(a.media_name).localeCompare(String(b.media_name));
    });

    const totalPending = reels.reduce(function(total, reel) {
        return total + Number(reel.pending_comments || 0);
    }, 0);

    replyCommentsBtn.disabled = totalPending === 0;

    if (!reels.length) {
        commentsBody.innerHTML =
            '<tr><td colspan="3" class="empty">No replyable Reels configured. Enable Reels in Config.</td></tr>';
        return;
    }

    commentsBody.innerHTML = reels.map(function(reel) {
        const canReply = Number(reel.pending_comments || 0) > 0;

        return '<tr>' +
            '<td class="reel-cell">' +
                '<div class="reel-title">' + escapeHtml(reel.media_name) + '</div>' +
            '</td>' +
            '<td>' + formatNumber(reel.pending_comments) + '</td>' +
            '<td class="actions-cell">' +
                '<div class="comment-row-actions">' +
                    '<label class="row-limit-control">' +
                        '<span>Limit</span>' +
                        '<input class="limit-input comment-limit-one" type="number" min="1" max="500" value="100" aria-label="Comment refresh limit">' +
                    '</label>' +
                    '<button class="table-button refresh-comments-one" data-media-id="' + escapeHtml(reel.media_id) + '">Refresh</button>' +
                    '<button class="table-button reply-one" data-media-id="' + escapeHtml(reel.media_id) + '" ' +
                        (canReply ? '' : 'disabled title="No pending comments"') +
                        '>Reply</button>' +
                '</div>' +
            '</td>' +
        '</tr>';
    }).join("");

    commentsBody.querySelectorAll(".refresh-comments-one").forEach(function(button) {
        button.addEventListener("click", function() {
            refreshCommentsForReel(button.dataset.mediaId, button);
        });
    });

    commentsBody.querySelectorAll(".reply-one").forEach(function(button) {
        button.addEventListener("click", function() {
            replyPendingCommentsForReel(button.dataset.mediaId, button);
        });
    });
}

function showCommentsLoader(message) {
    commentsBody.innerHTML =
        '<tr><td colspan="4" class="loading">' +
            '<span class="loading-indicator">' +
                '<span class="loader" aria-hidden="true"></span>' +
                '<span>' + escapeHtml(message) + '</span>' +
            '</span>' +
        '</td></tr>';
}

async function loadComments() {
    showCommentsLoader("Loading pending comments…");
    setStatus("Loading comments from database…");

    try {
        const response = await fetch("/api/comments");

        if (!response.ok) {
            throw new Error("Could not load comment stats");
        }

        const data = await response.json();
        renderComments(data);
        commentsLoaded = true;
        setStatus("Ready");
    } catch (error) {
        setStatus(error.message);
    }
}

function getCommentLimit(input) {
    const source = input || commentLimitInput;
    const value = Number(source.value);

    if (!Number.isInteger(value) || value < 1 || value > 500) {
        throw new Error("Limit must be between 1 and 500");
    }

    return value;
}

async function refreshComments() {
    setButtonLoading(refreshCommentsBtn, true, "Refreshing…");
    replyCommentsBtn.disabled = true;
    showCommentsLoader("Refreshing pending comments…");
    setStatus("Refreshing comments…");

    try {
        const limit = getCommentLimit();
        const response = await fetch(
            "/api/comments/refresh?limit=" + encodeURIComponent(limit),
            { method: "POST" }
        );

        if (!response.ok) {
            const body = await response.text();
            throw new Error(body || "Could not refresh comments");
        }

        const data = await response.json();
        renderComments(data);
        commentsLoaded = true;
        setStatus("Comments refreshed");
    } catch (error) {
        commentsBody.innerHTML =
            '<tr><td colspan="4" class="empty">' + escapeHtml(error.message) + '</td></tr>';
        setStatus(error.message);
    } finally {
        setButtonLoading(refreshCommentsBtn, false);
    }
}

async function refreshCommentsForReel(mediaId, button) {
    setButtonLoading(button, true, "Refreshing…");
    refreshCommentsBtn.disabled = true;
    setStatus("Refreshing Reel comments…");

    try {
        const row = button.closest("tr");
        const limitInput = row ? row.querySelector(".comment-limit-one") : null;
        if (!limitInput) {
            throw new Error("Comment limit input not found");
        }

        const limit = getCommentLimit(limitInput);
        const response = await fetch(
            "/api/comments/refresh/" + encodeURIComponent(mediaId) + "?limit=" + encodeURIComponent(limit),
            { method: "POST" }
        );

        if (!response.ok) {
            const body = await response.text();
            throw new Error(body || "Could not refresh Reel comments");
        }

        const data = await response.json();
        renderComments(data);
        commentsLoaded = true;

        const reel = data.reels && Object.values(data.reels).find(function(item) {
            return item.media_id === mediaId;
        });

        setStatus(
            reel
                ? "Reel refreshed: " + formatNumber(reel.discovered_comments) + " eligible comment" +
                    (Number(reel.discovered_comments) === 1 ? "" : "s") + " discovered"
                : "Reel refreshed"
        );
    } catch (error) {
        setStatus(error.message);
    } finally {
        refreshCommentsBtn.disabled = false;
        setButtonLoading(button, false);
    }
}

async function replyPendingCommentsForReel(mediaId, button) {
    if (button.disabled) return;

    const confirmed = window.confirm(
        "This will process pending eligible comments for this Reel, sending DMs and public replies. Continue?"
    );

    if (!confirmed) return;

    setButtonLoading(button, true, "Replying…");
    refreshCommentsBtn.disabled = true;
    replyCommentsBtn.disabled = true;
    setStatus("Processing Reel comments…");

    try {
        const response = await fetch(
            "/api/comments/reply/" + encodeURIComponent(mediaId),
            { method: "POST" }
        );

        if (!response.ok) {
            const body = await response.text();
            throw new Error(body || "Could not process Reel comments");
        }

        const data = await response.json();
        renderComments(data.comments || {});
        commentsLoaded = true;
        setStatus(
            "Reel processed: " +
            formatNumber((data.processing || {}).success) +
            " succeeded, " +
            formatNumber((data.processing || {}).failed) +
            " failed"
        );
    } catch (error) {
        setStatus(error.message);
    } finally {
        refreshCommentsBtn.disabled = false;
        setButtonLoading(button, false);
        await loadConfig();
    }
}

async function replyPendingComments() {
    if (replyCommentsBtn.disabled) return;

    const confirmed = window.confirm(
        "This will discover and process pending eligible comments, sending DMs and public replies. Continue?"
    );

    if (!confirmed) return;

    setButtonLoading(replyCommentsBtn, true, "Replying…");
    refreshCommentsBtn.disabled = true;
    setStatus("Processing comments…");

    try {
        const response = await fetch("/api/comments/reply", { method: "POST" });

        if (!response.ok) {
            const body = await response.text();
            throw new Error(body || "Could not process comments");
        }

        const data = await response.json();
        renderComments(data.comments || {});
        commentsLoaded = true;
        setStatus(
            "Reply All completed: " +
            formatNumber((data.processing || {}).success) +
            " succeeded, " +
            formatNumber((data.processing || {}).failed) +
            " failed"
        );
    } catch (error) {
        setStatus(error.message);
    } finally {
        refreshCommentsBtn.disabled = false;
        setButtonLoading(replyCommentsBtn, false);
        await loadConfig();
    }
}

function renderConfig(data) {
    configUsernameEl.textContent = "@" + (data.username || "—");
    configUserIdEl.textContent = data.instagram_user_id || "—";

    renderConfigReels(data.reels || []);

}

function renderConfigReels(reels) {
    if (!reels.length) {
        configReelsBody.innerHTML =
            '<tr><td colspan="4" class="empty">No tracked Reels yet. Open Insights and click Refresh reels.</td></tr>';
        configReelsCount.textContent = "0 selected";
        return;
    }

    configReelsBody.innerHTML = reels.map(function(reel) {
        const mediaId = escapeHtml(reel.media_id);
        const mediaName = escapeHtml(reel.media_name || ("reel_" + reel.media_id));
        const caption = escapeHtml(shortText(reel.caption || reel.media_id, 90));
        const checked = reel.enabled ? "checked" : "";

        return '<tr class="config-reel-row" data-media-id="' + mediaId + '">' +
            '<td class="check-cell">' +
                '<input type="checkbox" class="config-reel-enabled" ' + checked + ' aria-label="Enable replies for Reel">' +
            '</td>' +
            '<td class="name-cell">' +
                '<input class="reel-name-input" type="text" value="' + mediaName + '" placeholder="Reel name">' +
            '</td>' +
            '<td class="reel-cell">' +
                '<div class="reel-title">' + caption + '</div>' +
            '</td>' +
            '<td>' + formatPosted(reel.timestamp) + '</td>' +
            '<td class="location-cell">' +
                '<input class="location-input" type="text" value="' + escapeHtml(reel.location || "") + '" placeholder="Enter location">' +
            '</td>' +
        '</tr>';
    }).join("");

    function updateSelectedCount() {
        const selected = configReelsBody.querySelectorAll(".config-reel-enabled:checked").length;
        configReelsCount.textContent = selected + " selected";
    }

    configReelsBody.querySelectorAll(".config-reel-enabled").forEach(function(input) {
        input.addEventListener("change", updateSelectedCount);
    });

    updateSelectedCount();
}

async function saveConfig() {
    setButtonLoading(saveConfigBtn, true, "Saving…");
    setStatus("Saving config…");

    try {
        const reels = Array.from(configReelsBody.querySelectorAll(".config-reel-row")).map(function(row) {
            return {
                media_id: row.dataset.mediaId,
                media_name: row.querySelector(".reel-name-input").value.trim(),
                enabled: row.querySelector(".config-reel-enabled").checked,
                location: row.querySelector(".location-input").value.trim(),
            };
        });

        const response = await fetch("/api/config", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({ reels: reels }),
        });

        if (!response.ok) {
            const body = await response.text();
            throw new Error(body || "Could not save config");
        }

        const data = await response.json();
        renderConfig(data);
        commentsLoaded = false;
        setStatus("Config saved");
    } catch (error) {
        setStatus(error.message);
    } finally {
        setButtonLoading(saveConfigBtn, false);
    }
}

async function loadConfig() {
    try {
        const response = await fetch("/api/config");

        if (!response.ok) {
            throw new Error("Could not load config");
        }

        const data = await response.json();
        renderConfig(data);
    } catch (error) {
        setStatus(error.message);
    }
}

function switchTab(tabName) {
    tabButtons.forEach(function(button) {
        button.classList.toggle("active", button.dataset.tab === tabName);
    });

    tabPanels.forEach(function(panel) {
        panel.classList.toggle("active", panel.id === "tab-" + tabName);
    });

    if (tabName === "insights") {
        loadDashboard();
    } else if (tabName === "comments") {
        loadComments();
        loadConfig();
    } else if (tabName === "ai") {
        loadAiReels();
    } else if (tabName === "config") {
        loadConfig();
    }
}

function closeModal(modal) {
    modal.classList.add("hidden");
}

tabButtons.forEach(function(button) {
    button.addEventListener("click", function() {
        switchTab(button.dataset.tab);
    });
});

refreshReelsBtn.addEventListener("click", refreshReels);
refreshCommentsBtn.addEventListener("click", refreshComments);
saveConfigBtn.addEventListener("click", saveConfig);
replyCommentsBtn.addEventListener("click", replyPendingComments);
aiAccountBtn.addEventListener("click", function() {
    runAi("/api/ai/account", aiAccountBtn, "Analyzing…");
});
aiReelBtn.addEventListener("click", function() {
    const mediaId = aiReelSelect.value;
    if (!mediaId) {
        aiStatus.textContent = "Select a Reel first";
        return;
    }
    runAi("/api/ai/reels/" + encodeURIComponent(mediaId), aiReelBtn, "Analyzing…");
});

aiChatSendBtn.addEventListener("click", sendAiChat);
aiChatClearBtn.addEventListener("click", clearAiChat);
aiChatInput.addEventListener("keydown", function(event) {
    if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        sendAiChat();
    }
});

closeReelModal.addEventListener("click", function() {
    closeModal(reelModal);
});

reelModal.addEventListener("click", function(event) {
    if (event.target === reelModal) closeModal(reelModal);
});

document.addEventListener("keydown", function(event) {
    if (event.key === "Escape") {
        closeModal(reelModal);
    }
});

loadDashboard();
loadConfig();
