
# Instagram Auto Reply

Instagram comment automation for a Professional Instagram account using the official Instagram Graph API, with Reel catalog discovery, Reel Insights history, keyword-based comment discovery, a durable SQLite pending-comment queue, DM/public-reply processing, SQLite-backed Reel configuration, and a lightweight FastAPI dashboard.

The project is intentionally a lightweight, single-process Python service. It uses module-level functions and plain dictionaries instead of an ORM or class-heavy domain model.

---

## 1. What the system does

### Reel Insights

1. Discover Reels from Instagram.
2. Store Reel metadata in insights.json.
3. Fetch the canonical Reel Insights metrics.
4. Store timestamped normalized snapshots in insights.json.
5. Expose the catalog and snapshots through the dashboard.

### Comment automation

1. Enable replyable Reels in Config.
2. Store Reel name, enabled state, and location in SQLite.
3. Explicitly refresh comments from the Comments tab or CLI.
4. Filter eligible top-level comments.
5. Queue only uncompleted work in SQLite.
6. Process queued work by sending the DM first and the public reply second.
7. Delete the queue row only after both operations succeed.

If the DM succeeds but the public reply fails, the row stays in the queue with status DM_SENT. A retry therefore skips the DM and attempts only the public reply.

Replied-comment history is not stored locally.

---

## 2. Project structure

~~~text
instagram-auto-reply/
├── .env
├── README.md
├── ARCHITECTURE_REFERENCE.md
├── main.py
├── requirements.txt
├── media.json
├── insights.json
├── instagram.db
├── logs/
│   └── instagram.log
├── app/
│   ├── api.py
│   ├── config.py
│   ├── database.py
│   ├── instagram.py
│   ├── logger.py
│   ├── analytics/
│   │   ├── metrics.py
│   │   ├── baseline.py
│   │   ├── posting_time.py
│   │   └── analyzer.py
│   ├── comments/
│   │   ├── service.py
│   │   ├── discovery.py
│   │   └── processor.py
│   ├── insights/
│   │   ├── collector.py
│   │   └── catalog.py
│   └── web/
│       ├── server.py
│       ├── service.py
│       ├── templates/index.html
│       └── static/
│           ├── app.js
│           └── style.css
└── .github/
    └── workflows/
        └── instagram.yml
~~~

Runtime artifacts:

- instagram.db: pending queue + reply configuration
- insights.json: Reel catalog + Insight history
- media.json: output from the media CLI command
- logs/instagram.log: rotating application log

---

## 3. Requirements and setup

Install dependencies:

~~~bash
pip install -r requirements.txt
~~~

Pinned runtime packages:

| Package | Version | Purpose |
|---|---:|---|
| requests | 2.34.2 | Meta/Instagram Graph API HTTP client |
| urllib3 | 2.7.0 | HTTP transport dependency |
| charset-normalizer | 3.5.1 | Response encoding |
| certifi | 2026.7.22 | TLS CA bundle |
| idna | 3.19 | URL/domain support |
| python-dotenv | 1.2.3 | Load .env configuration |
| fastapi | 0.142.2 | Web/API server |
| uvicorn | 0.54.0 | ASGI server |

There is no formal pytest, ruff, black, mypy, Poetry, or uv configuration in the repository.

---

## 4. Environment configuration

Create .env:

~~~dotenv
ACCESS_TOKEN=<instagram-graph-api-access-token>
~~~

app/config.py loads the token with python-dotenv.

Static integration settings currently include:

| Setting | Purpose |
|---|---|
| ACCESS_TOKEN | Instagram Graph API access token |
| BASE_URL | https://graph.instagram.com/v25.0 |
| MY_USERNAME | Username used to identify the bot's own replies |
| IG_USER_ID | Instagram account ID used for media and messaging calls |
| DM_MESSAGES | Ten location-DM templates containing {location} |

The public reply text is application behavior, not a configuration field:

~~~text
Please check DM
~~~

There is no static MEDIA dictionary in the current design.

---

# 5. CLI

## Start the dashboard

~~~bash
python main.py web
~~~

Defaults:

- host 127.0.0.1
- port 8000

Network binding:

~~~bash
python main.py web --host 0.0.0.0 --port 8000
~~~

Dashboard:

~~~text
http://127.0.0.1:8000
~~~

FastAPI docs:

~~~text
http://127.0.0.1:8000/docs
~~~

## Discover one Reel

~~~bash
python main.py discover <media_name> [count]
~~~

The Reel name must be enabled/replyable in SQLite configuration. Default count is 100.

## Discover all replyable Reels

~~~bash
python main.py discover_all [count]
~~~

The count is applied per Reel. Default is 100.

## Process pending comments

~~~bash
python main.py process
python main.py process --count 25
python main.py process <media_name>
python main.py process <media_name> --count 25
~~~

Important: process reads the existing SQLite queue. It does not discover comments first.

## Export media

~~~bash
python main.py media
~~~

This writes the recent media response to media.json. media.json is an export artifact, not configuration source-of-truth.

## Collect Insights

~~~bash
python main.py insights
python main.py insights <media_id>
~~~

With no media ID, Insight collection scans the available media and keeps only items whose media_product_type is REELS.

---

# 6. Dashboard behavior

The dashboard has three tabs.

## Insights

Shows:

- Reel caption
- Posted time
- Views
- Reach
- Likes
- Comments
- Shares
- Saves
- Average watch time
- Skip rate
- Engagement rate

Actions:

- Refresh reels: refreshes the Reel catalog only.
- Per-Reel Refresh: fetches current metadata and Insights for that Reel.
- Clicking a Reel opens its current metrics and historical snapshots.

## Comments

Opening the tab performs a read from the application state. It calls GET /api/comments and GET /api/config.

Opening Comments does not discover comments from Instagram.

Actions:

- global Refresh: discover eligible comments for all enabled Reels
- per-Reel Refresh: discover comments for one enabled Reel
- Reply All: process the existing pending queue
- per-Reel Reply: process only that Reel's queue

The table shows:

- Reel name
- Pending comments
- Actions

## Config

Configuration is stored in SQLite.

Each Reel has:

- media_id
- editable media_name
- enabled
- location

An enabled Reel must have a non-empty location.

---

# 7. Internal FastAPI API

FastAPI metadata:

~~~text
title   = Instagram Automation
version = 1.0.0
docs    = /docs
~~~

## Endpoint list

| Method | Path | Purpose |
|---|---|---|
| GET | / | Serve dashboard HTML |
| GET | /api/health | Health check |
| GET | /api/config | Read reply configuration and Reel metadata |
| POST | /api/config | Replace reply configuration |
| GET | /api/dashboard | Read Insight summary |
| GET | /api/reels | Read all catalog Reels |
| POST | /api/reels/refresh | Refresh Reel catalog |
| GET | /api/reels/{media_id} | Read one Reel + snapshots |
| POST | /api/reels/{media_id}/refresh | Collect one Reel's Insights |
| GET | /api/analytics | Build full deterministic AI-analysis context |
| GET | /api/analytics/posting-time | Build age-normalized posting-time analysis |
| GET | /api/analytics/reels/{media_id} | Build one-Reel deterministic analysis context |
| GET | /api/comments | Read comment state from SQLite |
| POST | /api/comments/refresh | Discover comments for all replyable Reels |
| POST | /api/comments/refresh/{media_id} | Discover comments for one replyable Reel |
| POST | /api/comments/reply | Process all pending comments |
| POST | /api/comments/reply/{media_id} | Process one Reel's pending comments |
| GET | /static/* | Dashboard assets |

## GET /api/health

Example:

~~~json
{
  "status": "ok",
  "insights_file_exists": true,
  "timestamp": "2026-10-02T12:34:56"
}
~~~

## GET /api/config

Returns account information plus the merged Reel list:

~~~json
{
  "instagram_user_id": "27392931747065676",
  "username": "the_lost_aperture_",
  "timezone": "Asia/Kolkata",
  "reels": [
    {
      "media_id": "123",
      "media_name": "my reel",
      "caption": "Example",
      "timestamp": "...",
      "enabled": true,
      "location": "Example location"
    }
  ]
}
~~~

The response combines catalog metadata from insights.json with reply configuration from SQLite.

## POST /api/config

Body:

~~~json
{
  "reels": [
    {
      "media_id": "123",
      "media_name": "my reel",
      "enabled": true,
      "location": "Example location"
    }
  ]
}
~~~

Validation:

- reels must be an array
- enabled Reels require a non-empty location
- missing media_name is normalized to reel_<media_id>
- the submitted list replaces the reply_config table

Possible application errors include:

~~~text
400 reels must be an array
400 Location is required for replyable Reel media_id=<id>
~~~

## GET /api/dashboard

Returns the Insight summary:

~~~json
{
  "account": {
    "instagram_user_id": "27392931747065676",
    "username": "the_lost_aperture_"
  },
  "catalog_last_updated": "...",
  "insights_last_updated": "...",
  "reels_tracked": 10,
  "total_views": 123456
}
~~~

## GET /api/reels

Returns the normalized catalog list. Each Reel includes metadata, the latest Insight metrics, and the derived metrics produced by app/web/service.py.

## POST /api/reels/refresh

Refreshes the Reel catalog from Instagram.

It:

1. loads known Reel IDs from insights.json
2. queries Instagram media
3. uses known IDs as stop IDs for pagination
4. ignores non-Reels
5. adds new Reels
6. updates changed metadata
7. updates catalog_last_updated
8. does not fetch Insights for every Reel

Example response:

~~~json
{
  "status": "ok",
  "added": 2,
  "updated": 1,
  "total_reels": 25,
  "skipped": 4
}
~~~

## GET /api/reels/{media_id}

Returns one normalized Reel including historical snapshots.

Unknown IDs return HTTP 404:

~~~text
Reel not found
~~~

## POST /api/reels/{media_id}/refresh

Collects current Insights for one media ID.

Example:

~~~json
{
  "status": "ok",
  "media_id": "123",
  "last_updated": "..."
}
~~~

## GET /api/analytics

Reads insights.json and builds the deterministic analysis context used by the future AI layer.

It contains account baselines, per-Reel metrics, posting-time features, and age-normalized 24-hour performance.

## GET /api/analytics/posting-time

Returns posting-time analysis grouped by:

- hour
- weekday
- 1-hour slot
- 30-minute slot

Performance is normalized around a 24-hour Reel age using the nearest Insight snapshot within an 8-hour tolerance.

Each aggregate contains:

- count
- median
- p25
- p75

This avoids comparing a newly posted Reel directly with a much older Reel using raw totals.

## GET /api/analytics/reels/{media_id}

Returns deterministic analysis context for one Reel, including:

- posting features
- latest metrics
- derived engagement rates
- nearest 24-hour Insight snapshot

Unknown media IDs return HTTP 404.

## GET /api/comments

This endpoint is read-only.

It gets:

- enabled/replyable Reels from SQLite reply_config
- pending counts from SQLite queue
- Reel captions/timestamps from insights.json

It does not discover comments.

Example:

~~~json
{
  "status": "ok",
  "last_updated": null,
  "reels": {
    "my reel": {
      "media_name": "my reel",
      "media_id": "123",
      "caption": "Example",
      "timestamp": "...",
      "pending_comments": 14
    }
  }
}
~~~

## POST /api/comments/refresh

Query parameter:

~~~text
limit=100
~~~

Allowed range is 1 through 500. Default is 100.

Behavior:

1. calls discover_all(limit)
2. fetches Instagram comments for each enabled Reel
3. applies discovery filters
4. inserts eligible work into SQLite
5. returns the updated comment dashboard

## POST /api/comments/refresh/{media_id}

Same limit rules.

The media ID must be attached to an enabled replyable Reel.

Otherwise:

~~~text
400 This Reel is not enabled for replies. Enable it in Config first.
~~~

## POST /api/comments/reply

Processes all pending queue items.

It does not perform discovery.

The response contains:

- success
- failed
- total
- success_by_media
- failed_by_media
- refreshed comment dashboard state

## POST /api/comments/reply/{media_id}

Processes only the selected Reel's pending queue.

---

# 8. Instagram Graph API integration

All outbound Instagram HTTP calls are centralized in app/api.py.

Base URL:

~~~text
https://graph.instagram.com/v25.0
~~~

Timeout:

~~~text
30 seconds
~~~

## GET /{media_id}/comments

Query parameters:

~~~text
fields=id,text,username,from,parent_id,hidden,timestamp
access_token=<ACCESS_TOKEN>
limit=<1..500>
~~~

Pagination follows paging.next until the scan limit is reached.

Consumed comment fields:

| Field | Use |
|---|---|
| id | Queue key and reply target |
| text | Eligibility keyword matching |
| from.username | Self/bot detection |
| parent_id | Nested reply detection and duplicate detection |
| hidden | Hidden comment filtering |
| timestamp | Queue ordering and storage |
| username | Requested API field; compatibility |

## POST /{comment_id}/replies

Form data:

~~~text
message=Please check DM
access_token=<ACCESS_TOKEN>
~~~

This call is made only after the DM succeeds.

## POST /{IG_USER_ID}/messages

Headers:

~~~text
Authorization: Bearer <ACCESS_TOKEN>
Content-Type: application/json
~~~

Body:

~~~json
{
  "recipient": {
    "comment_id": "<COMMENT_ID>"
  },
  "message": {
    "text": "<generated DM text>"
  }
}
~~~

A HTTP 200 response is treated as DM success.

Failures are normalized into:

~~~json
{
  "status_code": 400,
  "message": "...",
  "body": {}
}
~~~

The public reply is skipped when the DM fails.

## GET /{IG_USER_ID}/media

Fields:

~~~text
id,caption,comments_count,media_type,media_product_type,timestamp
~~~

Used by media export, catalog refresh, and all-Reel Insight collection.

## GET /{media_id}

Fields:

~~~text
id,caption,comments_count,media_type,media_product_type,timestamp
~~~

Used by single-Reel discovery and single-Reel Insight refresh.

## GET /{media_id}/insights

Canonical metrics:

~~~text
views
reach
likes
comments
shares
saved
total_interactions
ig_reels_avg_watch_time
ig_reels_video_view_total_time
reels_skip_rate
~~~

All ten metrics are requested in one API call.

---

# 9. Comment eligibility

app/comments/service.py performs case-insensitive substring matching against:

~~~text
location
loc
link
map
maps
which place
where
details
📍
~~~

A comment also must be:

- not authored by MY_USERNAME
- not hidden
- not nested; parent_id must be absent

---

# 10. Duplicate detection

The project does not store replied-comment history.

During discovery, a first pass builds a set of parent IDs from comments authored by MY_USERNAME when the reply text contains one of:

~~~text
please check dm
please check your dm
shared the location in dm
i've sent you the location in dm
location sent! check your dm
sent you the location
~~~

A second pass uses that set to avoid re-enqueueing comments already answered by the bot.

This two-pass design makes detection independent of whether the bot reply appears before or after its parent comment in a returned page.

---

# 11. SQLite data model

Database file:

~~~text
instagram.db
~~~

The database creates two active tables.

## queue

| Column | Type | Meaning |
|---|---|---|
| comment_id | TEXT PRIMARY KEY | Instagram comment ID |
| username | TEXT | Comment author |
| comment | TEXT | Original comment text |
| timestamp | TEXT | Stored in IST-readable form |
| media_name | TEXT NOT NULL | Logical Reel name |
| media_id | TEXT NOT NULL | Instagram media ID |
| status | TEXT NOT NULL | Operational state |
| retries | INTEGER NOT NULL | Failed processing attempt count |
| created_at | DATETIME | Queue insertion time |

Active statuses:

~~~text
PENDING
DM_SENT
~~~

Legacy migration behavior:

- old DONE rows are deleted
- old FAILED rows are reset to PENDING

Successful work is deleted from the queue.

## reply_config

| Column | Type | Meaning |
|---|---|---|
| media_id | TEXT PRIMARY KEY | Instagram media ID |
| media_name | TEXT NOT NULL | Human-facing Reel name |
| location | TEXT NOT NULL | Location used in DM |
| enabled | INTEGER NOT NULL | Replyable flag |
| updated_at | DATETIME | Last config update time |

reply_config is the source of truth for replyable Reels.

---

# 12. Queue state model

~~~text
PENDING
   |
   | DM succeeds
   v
DM_SENT
   |
   | public reply succeeds
   v
DELETE ROW

PENDING -- DM failure --> PENDING + retries
DM_SENT -- reply failure --> DM_SENT + retries
~~~

The processor uses a 5–8 second randomized delay between queue items.

---

# 13. Insights storage

File:

~~~text
insights.json
~~~

A Reel contains:

- media_id
- caption
- media_type
- media_product_type
- timestamp
- comments_count
- snapshots

A snapshot contains:

- collected_at
- normalized metrics

The latest snapshot is selected by collected_at.

Special normalization:

| API metric | Stored key |
|---|---|
| ig_reels_avg_watch_time | avg_watch_time_ms |
| ig_reels_video_view_total_time | total_watch_time_ms |
| reels_skip_rate | skip_rate |

Derived dashboard values:

~~~text
avg_watch_time_seconds
total_watch_time_hours
engagement_rate
~~~

engagement_rate is calculated as total_interactions / reach * 100 when reach is non-zero.

Writes use a temporary file followed by os.replace().

---

# 14. Logging

app/logger.py exposes one shared logger.

Destinations:

~~~text
TimedRotatingFileHandler -> logs/instagram.log
StreamHandler            -> stdout
~~~

Logging includes:

- discovery start/completion
- queue inserts
- DM success/failure
- public reply success/failure
- processing progress
- retries
- catalog refresh
- Insights collection
- web action requests
- summary counts

---

# 15. Web UI loading behavior

Long-running dashboard actions have a visible spinner and disable the initiating button while the request is running.

Covered actions:

- Refresh reels
- per-Reel Insights Refresh
- Comments Refresh
- per-Reel Comments Refresh
- Reply All
- per-Reel Reply
- Save changes

Opening Comments only reads the current DB-backed state and is not a discovery action.

---

# 16. CLI / Web parity

| UI action | Domain function |
|---|---|
| Comments Refresh | discover_all(limit) |
| Per-Reel Comments Refresh | discover(media_name, limit) |
| Reply All | process() |
| Per-Reel Reply | process(media_name) |
| Refresh reels | refresh_reel_catalog() |
| Per-Reel Insights Refresh | collect_reel_insights(media_id) |
| Save config | save_reply_config(entries) |

The web layer therefore stays thin and does not duplicate the comment workflow.

---

# 17. GitHub Actions

Workflow:

~~~text
.github/workflows/instagram.yml
~~~

Trigger:

~~~text
workflow_dispatch
~~~

Runner:

~~~text
self-hosted ARM64
~~~

Supported actions:

- media
- discover
- discover_all
- process

Current workflow sequence:

~~~text
workflow_dispatch
    |
    v
git pull --ff-only origin main
    |
    v
activate .venv
    |
    v
python main.py <command>
    |
    v
sqlite3 instagram.db
    |
    v
print queue status
~~~

Important deployment rule:

The workflow currently pulls origin/main. Feature-branch changes are therefore not what the Action executes until merged into main.

The workflow YAML also has a manually maintained media choice list, while the application runtime reads enabled Reel names from SQLite.

---

# 18. Security and operational considerations

- ACCESS_TOKEN comes from environment configuration.
- The dashboard currently has no application-level authentication middleware.
- 127.0.0.1 is the default web binding.
- Binding to 0.0.0.0 should be protected by a trusted network boundary, reverse proxy, VPN, firewall, or equivalent access control.
- Comment scanning is capped at 500.
- Comment processing intentionally waits 5–8 seconds between items.
- SQLite and insights.json are local filesystem state.
- Instagram permissions, token validity, API restrictions, and external rate limits remain outside the application.

---

# 19. Source-of-truth map

| Data | Source of truth |
|---|---|
| Instagram access token | ACCESS_TOKEN environment variable |
| Replyable Reel selection | SQLite reply_config |
| Reel display name | SQLite reply_config.media_name |
| Reel location | SQLite reply_config.location |
| Pending/uncompleted comments | SQLite queue |
| Replied-comment history | Not stored locally |
| Reel catalog | insights.json |
| Historical Insight snapshots | insights.json |
| Media export | media.json |
| Runtime logs | logs/instagram.log |
| Dashboard API | app/web/server.py |
| Instagram API transport | app/api.py |

---

# 20. Design principles

The implementation intentionally follows these contracts:

1. Centralize Instagram HTTP transport in app/api.py.
2. Keep shared Instagram/media calls in app/instagram.py.
3. Keep comment business logic in app/comments/.
4. Keep SQLite queue/config semantics in app/database.py.
5. Keep Insight persistence in app/insights/.
6. Keep FastAPI routes in app/web/server.py.
7. Keep dashboard transformations in app/web/service.py.
8. Keep environment/static integration settings in app/config.py.
9. Prefer module-level functions and plain dictionaries over a class-heavy architecture.
10. Treat SQLite as the durable boundary between discovery and processing.
11. Do not add local reply-history persistence unless the data model is intentionally changed.
12. Keep README.md and ARCHITECTURE_REFERENCE.md synchronized with changes to API contracts, state models, and source-of-truth rules.
