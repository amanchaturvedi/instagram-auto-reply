
# ARCHITECTURE REFERENCE
## Instagram Auto Reply

This document describes the current implementation of the repository: Instagram Graph API transport, Reel catalog and Insights storage, SQLite-backed Reel reply configuration, SQLite pending-comment queue, FastAPI dashboard, CLI orchestration, and GitHub Actions.

The project is deliberately lightweight and single-process. It uses module-level functions, plain dictionaries, SQLite, and JSON rather than an ORM or class-heavy framework.

---

# 1. SYSTEM ARCHITECTURE

~~~text
                    ┌───────────────────────┐
                    │ Presentation           │
                    │                       │
                    │ main.py CLI            │
                    │ FastAPI dashboard      │
                    └──────────┬────────────┘
                               │
                    ┌──────────▼────────────┐
                    │ Application workflows │
                    │                       │
                    │ comments/discovery     │
                    │ comments/processor     │
                    │ insights/catalog       │
                    │ insights/collector     │
                    └───────┬────────┬───────┘
                            │        │
                 ┌──────────▼───┐ ┌─▼──────────────┐
                 │ Instagram    │ │ Persistence     │
                 │ facade       │ │                │
                 │ instagram.py │ │ database.py    │
                 └──────┬───────┘ │ instagram.db   │
                        │         │ insights.json  │
                        ▼         └────────────────┘
                 ┌─────────────────────────┐
                 │ app/api.py              │
                 │ Instagram Graph API     │
                 └─────────────────────────┘

Cross-cutting:
  app/config.py
  app/logger.py
~~~

Core boundary:

~~~text
Instagram discovery
       |
       v
SQLite queue
       |
       v
queue processing
       |
       +----> DM
       |
       +----> public reply
~~~

---

# 2. DIRECTORY TREE

~~~text
instagram-auto-reply/
├── README.md
├── ARCHITECTURE_REFERENCE.md
├── main.py
├── requirements.txt
├── media.json
├── insights.json
├── instagram.db
├── logs/
├── app/
│   ├── api.py
│   ├── config.py
│   ├── database.py
│   ├── instagram.py
│   ├── logger.py
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

---

# 3. MODULE RESPONSIBILITIES

## 3.1 main.py

CLI/presentation orchestration.

Commands:

- discover
- discover_all
- process
- media
- insights
- web

The discover command validates that the supplied Reel name is currently enabled/replyable.

The CLI delegates business work to the domain modules rather than implementing the workflows itself.

## 3.2 app/analytics/

Analytics foundation used as the deterministic input to future AI interpretation.

### metrics.py
Calculates derived rates and snapshot-to-snapshot growth.

### baseline.py
Calculates account-level median/p25/p75 baselines from the latest available snapshot of each Reel.

### posting_time.py
Extracts Asia/Kolkata posting-time features and performs age-normalized 24-hour comparisons.

### analyzer.py
Combines baseline, posting-time analysis, Reel metrics, and 24-hour snapshot selection into an AI-ready structured context.

The analytics layer does not call an LLM.

## 3.3 app/api.py

Single Graph API transport layer.

Responsibilities:

- build HTTP requests
- use a 30-second timeout
- log method/path/status
- parse JSON/text response bodies
- perform comments, replies, DMs, media, media lookup, and Insights requests

All outbound Instagram HTTP should stay centralized here.

## 3.3 app/instagram.py

Shared Instagram/media facade.

Exports:

- get_media
- get_media_by_id
- get_media_insights

Also defines the canonical 10-metric REEL_INSIGHT_METRICS list.

## 3.4 app/config.py

Environment/static integration settings plus a configuration facade.

Current values:

- ACCESS_TOKEN
- BASE_URL
- MY_USERNAME
- IG_USER_ID
- DM_MESSAGES

Replyable Reel settings are read from SQLite, not from a static MEDIA dictionary.

The module exposes:

- get_reply_config_map()
- get_replyable_media()
- get_media_config()
- save_reply_config()

The public reply message is behavior in comments/service.py.

## 3.5 app/database.py

SQLite persistence boundary.

Owns:

- schema initialization
- schema migration
- thread-local SQLite connections
- reply_config CRUD used by the application
- pending queue inserts and reads
- DM_SENT state
- retry counters
- completed-row deletion

No ORM or repository class layer is used.

## 3.6 app/comments/service.py

Comment business helpers.

Owns:

- DM message generation
- keyword eligibility
- DM dispatch
- public reply dispatch

Keywords:

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

Public reply:

~~~text
Please check DM
~~~

## 3.7 app/comments/discovery.py

Comment discovery and queueing.

Flow:

1. resolve enabled Reel configuration
2. fetch media metadata
3. fetch paginated comments
4. identify existing bot replies using parent IDs and reply markers
5. skip self-authored comments
6. skip hidden comments
7. skip nested replies
8. apply keyword eligibility
9. enqueue eligible comments with INSERT OR IGNORE
10. return discovery statistics

discover_all loops over all enabled Reels and continues after per-Reel failures.

## 3.8 app/comments/processor.py

Durable queue processor.

Flow:

~~~text
PENDING
   |
   | send_dm success
   v
DM_SENT
   |
   | public reply success
   v
DELETE
~~~

Failure paths:

~~~text
PENDING -> retry counter increment
DM_SENT -> retry counter increment
~~~

The processor sleeps for a random 5–8 seconds between comments.

## 3.9 app/insights/catalog.py

Reel catalog discovery.

refresh_reel_catalog():

- reads existing insights.json
- uses existing media IDs as stop IDs
- pages through Instagram media
- ignores non-Reels
- adds new Reels
- updates changed Reel metadata
- records catalog_last_updated
- saves JSON

It does not collect Insights for every Reel.

## 3.10 app/insights/collector.py

Insight snapshot collection.

collect_reel_insights(media_id=None):

- selects all media or one media
- ignores non-Reels
- requests the canonical 10 metrics
- normalizes special metric names
- appends timestamped snapshots
- saves insights.json

Snapshot identity is collected_at.

## 3.11 app/web/service.py

Dashboard read model / formatting layer.

Owns:

- loading insights.json
- selecting the latest snapshot
- formatting Reel objects
- deriving engagement_rate
- converting watch time values
- building dashboard summary
- health response

## 3.12 app/web/server.py

FastAPI presentation/API layer.

Owns:

- dashboard HTML route
- API routes
- comment limit validation
- configuration request validation
- mapping UI actions to domain functions
- merging catalog metadata with SQLite reply configuration
- exposing pending queue counts

FastAPI metadata:

~~~text
title   = Instagram Automation
version = 1.0.0
docs    = /docs
redoc   = disabled
~~~

---

# 4. DATA OWNERSHIP

~~~text
ACCESS_TOKEN
    -> environment

Replyable Reel selection
    -> SQLite reply_config

Pending/uncompleted comments
    -> SQLite queue

Reel catalog and historical Insights
    -> insights.json

media command export
    -> media.json

runtime diagnostics
    -> logs/
~~~

The project deliberately avoids using:

- media.json as configuration
- insights.json as the comment queue
- reply_config as Reel analytics history
- queue as permanent reply history

---

# 5. SQLITE SCHEMA

## 5.1 queue

~~~sql
CREATE TABLE IF NOT EXISTS queue(
    comment_id TEXT PRIMARY KEY,
    username TEXT,
    comment TEXT,
    timestamp TEXT,
    media_name TEXT NOT NULL,
    media_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING',
    retries INTEGER NOT NULL DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
~~~

Index:

~~~sql
CREATE INDEX IF NOT EXISTS idx_queue_media_status
ON queue(media_id, status);
~~~

Active states:

- PENDING
- DM_SENT

Completed comments are deleted.

Legacy schema migration:

~~~sql
DROP TABLE IF EXISTS comment_media_stats;
DROP TABLE IF EXISTS app_state;

DELETE FROM queue
WHERE status = 'DONE';

UPDATE queue
SET status = 'PENDING'
WHERE status = 'FAILED';
~~~

The current model therefore represents unfinished operational work, not reply history.

## 5.2 reply_config

~~~sql
CREATE TABLE IF NOT EXISTS reply_config(
    media_id TEXT PRIMARY KEY,
    media_name TEXT NOT NULL,
    location TEXT NOT NULL DEFAULT '',
    enabled INTEGER NOT NULL DEFAULT 0,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
~~~

---

# 6. SQLITE CONCURRENCY

FastAPI synchronous routes may execute on worker threads.

database.py uses threading.local() so each worker thread gets its own SQLite connection/cursor.

Settings:

~~~text
SQLite timeout: 30 seconds
PRAGMA busy_timeout: 30000
~~~

This avoids unsafe cross-thread sharing of a single SQLite connection in the current single-process service.

---

# 7. COMMENT DISCOVERY ARCHITECTURE

## One Reel

~~~text
SQLite reply_config
       |
       v
media_name -> media_id/location
       |
       v
GET media metadata
       |
       v
GET comments + pagination
       |
       v
first pass:
find bot reply parent IDs
       |
       v
second pass:
self? hidden? nested? keyword?
       |
       v
already replied?
       |
       v
INSERT OR IGNORE
       |
       v
SQLite queue
~~~

The Instagram comment ID is the idempotency key.

## All replyable Reels

~~~text
get_replyable_media()
      |
      +--> discover(Reel A, limit)
      +--> discover(Reel B, limit)
      +--> discover(Reel C, limit)
      ...
~~~

A failed Reel is logged and does not stop the remaining Reels.

---

# 8. COMMENT PROCESSING ARCHITECTURE

~~~text
get_pending_comments()
        |
        v
for each row
        |
        +---- PENDING ----> send_dm()
        |                      |
        |                      +-- failure --> keep row + retries
        |                      |
        |                      +-- success -> mark DM_SENT
        |
        +---- DM_SENT -----------------------+
                                             |
                                             v
                                      reply_comment()
                                             |
                                    +--------+--------+
                                    |                 |
                                 success           failure
                                    |                 |
                                    v                 v
                               delete row       keep row + retries
~~~

The DM is never resent for a row already in DM_SENT.

---

# 9. COMMENT ELIGIBILITY / DUPLICATE DETECTION

Keywords are checked case-insensitively:

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

Filtered out:

- own comments
- hidden comments
- nested comments

Bot-reply markers:

~~~text
please check dm
please check your dm
shared the location in dm
i've sent you the location in dm
location sent! check your dm
sent you the location
~~~

The duplicate detector performs two passes over the returned API page so ordering does not matter.

No local replied-comment history is stored.

---

# 10. INSTAGRAM GRAPH API

Base URL:

~~~text
https://graph.instagram.com/v25.0
~~~

Transport timeout:

~~~text
30 seconds
~~~

## Comments

~~~http
GET /{media_id}/comments
~~~

Fields:

~~~text
id,text,username,from,parent_id,hidden,timestamp
~~~

Pagination follows paging.next.

## Public reply

~~~http
POST /{comment_id}/replies
~~~

Data:

~~~text
message=Please check DM
access_token=<ACCESS_TOKEN>
~~~

## Private reply / DM

~~~http
POST /{IG_USER_ID}/messages
~~~

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
    "text": "<generated DM>"
  }
}
~~~

A HTTP 200 response is a successful DM.

## Media list

~~~http
GET /{IG_USER_ID}/media
~~~

Fields:

~~~text
id,caption,comments_count,media_type,media_product_type,timestamp
~~~

## Media lookup

~~~http
GET /{media_id}
~~~

Fields:

~~~text
id,caption,comments_count,media_type,media_product_type,timestamp
~~~

## Insights

~~~http
GET /{media_id}/insights
~~~

Metrics:

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

---

# 12. FASTAPI API CONTRACT

| Method | Path | Domain call |
|---|---|---|
| GET | /api/health | health_check() |
| GET | /api/config | SQLite config + catalog merge |
| POST | /api/config | save_reply_config() |
| GET | /api/dashboard | get_dashboard_summary() |
| GET | /api/reels | get_reels() |
| POST | /api/reels/refresh | refresh_reel_catalog() |
| GET | /api/reels/{media_id} | get_reel() |
| POST | /api/reels/{media_id}/refresh | collect_reel_insights(media_id) |
| GET | /api/analytics | build_account_analysis_context() |
| GET | /api/analytics/posting-time | build_account_analysis_context()["posting_time"] |
| GET | /api/analytics/reels/{media_id} | build_reel_analysis_for_media(media_id) |
| GET | /api/comments | _comment_dashboard() |
| POST | /api/comments/refresh | discover_all(limit) |
| POST | /api/comments/refresh/{media_id} | discover(media_name, limit) |
| POST | /api/comments/reply | process() |
| POST | /api/comments/reply/{media_id} | process(media_name) |

Comment limit:

~~~text
minimum = 1
maximum = 500
default = 100
~~~

Critical behavior:

~~~text
GET /api/comments
    -> DB/read model only
    -> no Instagram discovery
~~~

---

# 13. WEB UI DATA FLOW

## Insights tab

Tab open:

~~~text
GET /api/dashboard
GET /api/reels
~~~

Actions:

~~~text
Refresh reels
    -> POST /api/reels/refresh

Reel Refresh
    -> POST /api/reels/{media_id}/refresh

Reel click
    -> GET /api/reels/{media_id}
~~~

## Comments tab

Tab open:

~~~text
GET /api/comments
GET /api/config
~~~

No discovery.

Actions:

~~~text
Refresh
    -> POST /api/comments/refresh

Per-Reel Refresh
    -> POST /api/comments/refresh/{media_id}

Reply All
    -> POST /api/comments/reply

Per-Reel Reply
    -> POST /api/comments/reply/{media_id}
~~~

## Config tab

Tab open:

~~~text
GET /api/config
~~~

Save:

~~~text
POST /api/config
~~~

---

# 14. UI LOADING MODEL

Long-running user actions use a shared button-loader helper.

Covered actions:

- Refresh reels
- single-Reel Insights Refresh
- Comments Refresh
- single-Reel Comments Refresh
- Reply All
- single-Reel Reply
- Save changes

While active:

1. original button content is stored
2. button is disabled
3. spinner is displayed
4. action completes or fails
5. original button content is restored in finally
6. button is re-enabled

Comments discovery also displays a table-level loader.

---

# 15. INSIGHTS DATA MODEL

Stored Reel fields:

~~~text
media_id
caption
media_type
media_product_type
timestamp
comments_count
snapshots
~~~

Snapshot:

~~~text
collected_at
metrics
~~~

Normalized special metric keys:

~~~text
ig_reels_avg_watch_time
    -> avg_watch_time_ms

ig_reels_video_view_total_time
    -> total_watch_time_ms

reels_skip_rate
    -> skip_rate
~~~

Derived dashboard values:

~~~text
avg_watch_time_seconds
total_watch_time_hours
engagement_rate
~~~

---

# 16. JSON PERSISTENCE

insights.json is read and written by the Insight modules.

Snapshot writes are performed using a temporary file:

~~~text
insights.json.tmp
      |
      v
os.replace(...)
      |
      v
insights.json
~~~

Snapshots are deduplicated by collected_at.

---

# 17. LOGGING ARCHITECTURE

app/logger.py exports one shared logger.

~~~text
shared logger
   ├── TimedRotatingFileHandler -> logs/instagram.log
   └── StreamHandler            -> stdout
~~~

Important logged context:

- media ID/name
- comment ID
- username
- API page
- HTTP status
- discovery counts
- processing progress
- retry counts
- summaries
- web actions

---

# 18. GITHUB ACTIONS

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
self-hosted, ARM64
~~~

Supported commands:

- media
- discover
- discover_all
- process

Current execution flow:

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
print database status
~~~

The workflow currently pulls main, so feature-branch changes are not deployed by this Action until merged into main.

The workflow also contains a manual media choice list. Runtime CLI discovery uses the SQLite-backed reply configuration instead.

---

# 19. SECURITY / OPERATIONS

Credentials:

- ACCESS_TOKEN is environment-provided.
- Do not commit the token.

Dashboard:

- no application-level authentication middleware exists
- localhost is the default binding
- network exposure should be placed behind an appropriate access-control boundary

Operational limits:

| Area | Value |
|---|---|
| Graph API request timeout | 30 seconds |
| Comment scan maximum | 500 |
| Default comment scan | 100 |
| Processing delay | 5–8 seconds |
| FastAPI default host | 127.0.0.1 |
| FastAPI default port | 8000 |
| Graph API version | v25.0 |

External Meta constraints such as permissions, token state, API restrictions, rate limits, and messaging availability remain outside the application's control.

---

# 20. ARCHITECTURAL DECISIONS

## Decision: SQLite is the queue boundary

Discovery and processing are separate operations. SQLite provides durable handoff between them.

## Decision: no local replied-comment history

Successful queue rows are deleted. Existing Instagram-side bot replies are used for duplicate detection during discovery.

## Decision: Reel reply configuration is SQLite-backed

The old static Reel map is not the source of truth. Reels are discovered through the Insight/catalog path and explicitly enabled/configured in SQLite.

## Decision: public reply is application behavior

The current public reply text is "Please check DM". It is not part of reply_config.

## Decision: JSON is used for Insight history

Insight history is small, local, append-style snapshot data, so JSON is used instead of adding another relational model.

## Decision: thin web layer

FastAPI routes map HTTP actions onto existing domain functions rather than implementing separate business logic.

---

# 21. MAINTENANCE CONTRACTS

When modifying the repository:

1. Keep Graph API transport in app/api.py.
2. Keep media/Insight facade functions in app/instagram.py.
3. Keep comment eligibility in app/comments/service.py.
4. Keep discovery in app/comments/discovery.py.
5. Keep queue processing in app/comments/processor.py.
6. Keep queue/config persistence in app/database.py.
7. Keep Insight persistence in app/insights/.
8. Keep HTTP route wiring in app/web/server.py.
9. Keep dashboard formatting in app/web/service.py.
10. Keep environment/static integration settings in app/config.py.
11. Keep README.md and this file synchronized when behavior or API contracts change.
12. Avoid introducing classes/ORM abstractions without a concrete requirement.

---

# 22. CURRENT ARCHITECTURAL SUMMARY

~~~text
Lightweight layered automation service
+
Instagram Graph API transport layer
+
SQLite durable pending-work queue
+
SQLite-backed Reel reply configuration
+
JSON-backed Reel catalog and Insight history
+
FastAPI dashboard
+
CLI orchestration
+
GitHub Actions operational entrypoint
~~~

The core separation is:

~~~text
Discovery
   -> finds eligible work

Persistence
   -> remembers unfinished work

Processing
   -> performs external side effects

Insights
   -> stores Reel analytics history

Web/API
   -> exposes read models and controls

Configuration
   -> defines which Reels are replyable

Logging
   -> provides operational visibility
~~~
