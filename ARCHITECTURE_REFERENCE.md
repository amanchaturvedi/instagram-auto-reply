# Engineering Reference: Instagram Auto Reply

This repository is a lightweight, single-process automation workflow that discovers Instagram comments, queues eligible interactions in SQLite, sends DM replies, and posts public replies when the DM succeeds. The implementation is intentionally simple and operationally oriented rather than framework-driven.

---

## 1. PROJECT SYSTEM ARCHITECTURE

### Directory & File Tree

```text
instagram-auto-reply/
├── .env
├── .git/
├── .github/
│   └── workflows/
│       └── instagram.yml
├── .gitignore
├── .venv/                                 # local virtual environment
├── __pycache__/
├── README.md
├── config.py
├── database.py
├── index.html
├── instagram.db                           # runtime SQLite database artifact
├── instagram.py
├── logger.py
├── main.py
├── media.json                             # runtime exported media list
├── requirements.txt
├── logs/
│   ├── instagram.log
│   ├── instagram.log.2026-08-18
│   ├── instagram.log.2026-08-19
│   ├── instagram.log.2026-08-20
│   ├── instagram.log.2026-08-21
│   ├── instagram.log.2026-08-22
│   ├── instagram.log.2026-08-24
│   ├── instagram.log.2026-09-02
│   ├── instagram.log.2026-09-03
│   ├── instagram.log.2026-09-04
│   ├── instagram.log.2026-09-10
│   ├── instagram.log.2026-09-14
│   ├── instagram.log.2026-09-21
│   ├── instagram.log.2026-09-29
│   └── instagram.log.2026-09-30
├── venv/                                  # alternate local environment artifact
└── generated runtime state (from execution):
    └── SQLite queue rows and response artifacts persisted in instagram.db
```

### High-Level Architecture

This project follows a layered CLI orchestration pattern with explicit separation of concerns:

- Presentation / orchestration layer:
  - [main.py](main.py) handles command parsing and user-driven workflow entrypoints.
  - Responsibilities:
    - `discover`
    - `discover_all`
    - `process`
    - `media`
- Business logic / service layer:
  - [instagram.py](instagram.py) is the integration facade for Meta Graph API actions:
    - fetch comments
    - decide whether a comment qualifies for a reply
    - send DM
    - post a public comment reply
- Data persistence layer:
  - [database.py](database.py) owns the SQLite queue and all queue-state transitions.
  - The database is the operational integration point between discovery and processing.
- Configuration / environment layer:
  - [config.py](config.py) stores fixed media IDs, DM templates, account metadata, and environment-derived `ACCESS_TOKEN`.
- Observability layer:
  - [logger.py](logger.py) creates a globally shared `logger` with rotating file handlers and colorized console output.

This is not a framework-based MVC or hexagonal architecture. It is more accurately:

- a layered automation service,
- with external API adapters,
- plus a durable SQLite queue as a state boundary.

Decoupling is achieved by:
- keeping HTTP and Instagram-specific logic in [instagram.py](instagram.py),
- keeping storage semantics in [database.py](database.py),
- keeping runtime constants in [config.py](config.py),
- letting [main.py](main.py) orchestrate execution instead of embedding business logic inside transport code.

### Component Interaction Data Flow

1. CLI entrypoint
   - [main.py](main.py) parses args via `argparse`.
   - Supported commands:
     - `discover`
     - `discover_all`
     - `process`
     - `media`

2. Discovery workflow
   - `discover(media_name, fetch_count)` calls `get_comments(media_id, fetch_count)` from [instagram.py](instagram.py).
   - Returned comment payloads are plain dicts from the Instagram Graph API.
   - Each comment is filtered by:
     - `username == MY_USERNAME`
     - `hidden`
     - `parent_id`
     - `should_reply(text)`
   - Eligible comments are passed to `enqueue(comment, media_name, media_id)` in [database.py](database.py).
   - `enqueue` inserts them into the `queue` table using `INSERT OR IGNORE`.

3. Queue processing workflow
   - `process(media_name=None, limit=None)` pulls rows from `get_pending_comments(...)`.
   - Each queued row is processed sequentially, with a randomized delay between items.
   - The processing loop:
     - reads `comment_id`, `username`, `comment`, `media_name`, `status`, `retries`
     - calls `send_dm(comment_id, queued_media)`
     - if DM succeeds, calls `reply_comment(comment_id)`
     - on success, marks row as `DONE`
     - on failure, calls `mark_failed(comment_id)`

4. Persistence semantics
   - `mark_dm_sent`, `mark_done`, and `mark_failed` mutate state in `queue`.
   - Retry logic is encoded in `database.py`:
     - `retries = retries + 1`
     - status transitions are computed as:
       - if `retries + 1 >= 3` then `FAILED`
       - else if current status is `DM_SENT` keep `DM_SENT`
       - else revert to `PENDING`

5. Operational cleanup
   - `clear_done()` deletes rows whose status is `DONE`.
   - `reset_failed()` resets rows in `FAILED` back to `PENDING` with retries reset to 0.

6. Logging and diagnostics
   - Each major operation emits structured logs with `logger.info`, `logger.warning`, and `logger.exception`.
   - The logger writes to rotating files in `logs/` and to stdout concurrently.

---

## 2. CORE DATA DICTIONARY & DATA CLASS SCHEMAS

This repository does not define Python dataclasses, Pydantic models, or typed ORM entities. Runtime data is represented as:

- SQLite rows from `sqlite3.Row`
- plain Python `dict` objects returned by Instagram API responses
- configuration dictionaries loaded from [config.py](config.py)
- string templates in `DM_MESSAGES`

### 2.1 SQLite Entity: `queue`

| Field Name | Exact Python Type / Type Hint | Constraints | Short Functional Description |
| --- | --- | --- | --- |
| `comment_id` | `TEXT` | `PRIMARY KEY` | Unique Instagram comment identifier used as the queue key. |
| `username` | `TEXT` | nullable | Username of the person who commented. |
| `comment` | `TEXT` | nullable | Original comment body text as posted to the media thread. |
| `timestamp` | `TEXT` | nullable | Timestamp converted to IST format using `utc_to_ist(...)`. |
| `media_name` | `TEXT` | `NOT NULL` | Logical key identifying the configured media campaign, e.g. `dlf_midtown`. |
| `media_id` | `TEXT` | `NOT NULL` | Instagram media object identifier for the relevant post. |
| `status` | `TEXT` | `DEFAULT 'PENDING'` | Operational state: `PENDING`, `DM_SENT`, `DONE`, or `FAILED`. |
| `retries` | `INTEGER` | `DEFAULT 0` | Number of processing attempts for the comment item. |
| `created_at` | `DATETIME` | `DEFAULT CURRENT_TIMESTAMP` | Creation timestamp of the queue entry. |

Schema source:
- [database.py](database.py)

### 2.2 Configuration Dictionary: `MEDIA`

This is the main runtime configuration map. It is defined as a dictionary keyed by media slug.

| Field Name | Exact Python Type / Type Hint | Constraints | Short Functional Description |
| --- | --- | --- | --- |
| `MEDIA` | `dict[str, dict[str, str]]` | top-level key: media slug | Defines all monitored Instagram posts and their location metadata. |
| `MEDIA[slug]["media_id"]` | `str` | required | Graph API media object ID. |
| `MEDIA[slug]["location"]` | `str` | required | Human-readable place name for DM content generation. |

Example entries:
- `dlf_midtown`
- `dear_donna`
- `dhan_mill`
- `nukkad`
- `tehri_lake`
- `kijiji1`
- `kijiji2`

Source:
- [config.py](config.py)

### 2.3 Message Template Collection: `DM_MESSAGES`

| Field Name | Exact Python Type / Type Hint | Constraints | Short Functional Description |
| --- | --- | --- | --- |
| `DM_MESSAGES` | `list[str]` | non-empty list | A pool of DM templates used to build a personalized location message. |
| each template | `str` | must contain `{location}` placeholder | Template is formatted by `get_dm_message(media_name)`. |

Source:
- [config.py](config.py)

### 2.4 Instagram Comment Payload Shape

The Graph API returns comment objects in `data` arrays. The project consumes a minimal subset.

| Field Name | Exact Python Type / Type Hint | Constraints | Short Functional Description |
| --- | --- | --- | --- |
| `id` | `str` | required | Comment identifier. |
| `text` | `str | None` | optional | Raw text of the comment. |
| `username` | `str | None` | optional | Username within nested `from` object. |
| `from` | `dict[str, str]` | optional | Container object with `username` field. |
| `parent_id` | `str | None` | optional | If present, comment is considered nested. |
| `hidden` | `bool` | optional | Indicates hidden or filtered comment. |
| `timestamp` | `str` | optional | ISO timestamp returned by the API. |

The code accesses these as:
- `comment["id"]`
- `comment.get("from", {}).get("username")`
- `comment.get("text")`
- `comment.get("parent_id")`
- `comment.get("hidden", False)`

Source:
- [instagram.py](instagram.py)

### 2.5 Instagram Media Payload Shape

The `media` listing endpoint is used in the `media` command.

| Field Name | Exact Python Type / Type Hint | Constraints | Short Functional Description |
| --- | --- | --- | --- |
| `id` | `str` | required | Media object identifier. |
| `caption` | `str | None` | optional | Caption text associated with the media item. |
| `comments_count` | `int` | optional | Count of comments on the media. |

Source:
- [instagram.py](instagram.py)

### 2.6 Runtime Error Payload: DM failure body

| Field Name | Exact Python Type / Type Hint | Constraints | Short Functional Description |
| --- | --- | --- | --- |
| `status_code` | `int` | required | HTTP status returned by the Instagram API call. |
| `message` | `str` | required | Parsed error message. |
| `body` | `dict | str` | required | Raw JSON body or fallback text returned by the API. |

Used by `_dm_error(response)` in [instagram.py](instagram.py).

---

## 3. API CONTRACT & SERVICE INTERFACES

The project exposes mostly module-level functions rather than classes. The public interfaces are function-based, imperative, and not wrapped by an object-oriented service interface.

### 3.1 [main.py](main.py)

| Method Signature | Expected Inputs | Return Types | Exceptions Raised | Short Description |
| --- | --- | --- | --- | --- |
| `discover(media_name: str, fetch_count: int) -> None` | `media_name`: configured slug from `MEDIA`; `fetch_count`: number of comments to scan | `None` | Propagates exceptions from `get_comments()` and `enqueue()` | Scans a specific media item, filters comments, and enqueues eligible ones. |
| `discover_all(fetch_count: int) -> None` | `fetch_count`: scan limit per media | `None` | Catches and logs per-media exceptions only | Iterates through all configured media and discovers pending comment candidates. |
| `process(media_name: str | None = None, limit: int | None = None) -> None` | Optional media slug and optional row count | `None` | Propagates exceptions from DM and reply calls; caught per row to continue processing | Pulls queued comments, sends DMs, posts replies, and updates queue statuses. |
| `main() -> None` | CLI arguments from `argparse` | `None` | Standard CLI parsing errors, runtime errors from workflow handlers | Parses subcommands and dispatches execution. |

### 3.2 [instagram.py](instagram.py)

| Method Signature | Expected Inputs | Return Types | Exceptions Raised | Short Description |
| --- | --- | --- | --- | --- |
| `get_dm_message(media_name: str) -> str` | `media_name` must exist in `MEDIA` | `str` | `KeyError` if media slug is missing; `IndexError`/`ValueError` pathologically if template invalid | Selects a random DM template and injects the location string. |
| `_response_body(response: requests.Response) -> dict | str` | An HTTP response object | `dict | str` | None explicitly; may fail only if `.json()` raises `ValueError` | Converts response body to JSON or plain text for error logging. |
| `_error_message(response: requests.Response) -> str | dict | None` | HTTP response with error payload | `str | dict | None` | None explicitly; parser handles dict/list | Extracts the error message from Graph API payloads. |
| `_safe_url(url: str) -> str` | URL containing the access token | `str` | None | Redacts `ACCESS_TOKEN` before logging the URL. |
| `get_comments(media_id: str, limit: int) -> Iterator[dict]` | `media_id`: Instagram media ID; `limit`: max comment count | `Iterator[dict]` | `requests.HTTPError`, `requests.RequestException` | Paginated generator that yields comments from the Graph API. |
| `should_reply(text: str) -> bool` | Raw comment string | `bool` | None | Checks text for keywords such as `location`, `link`, `where`, `map`, or `📍`. |
| `reply_comment(comment_id: str) -> None` | Instagram comment ID to reply to | `None` | `requests.HTTPError`, `requests.RequestException` | Posts a public reply using the configured rotating list of canned responses. |
| `_dm_error(response: requests.Response) -> dict[str, object]` | Response object from DM API call | `dict[str, object]` | None | Normalizes failure payload into a structured dict with status, message, and raw body. |
| `send_dm(comment_id: str, media_name: str) -> tuple[bool, dict | None]` | comment ID and media slug | `tuple[bool, dict | None]` | None at the function boundary; API errors are handled internally and converted to structured errors | Sends a DM to the user using the configured media location template. |
| `get_media() -> Iterator[dict]` | None | `Iterator[dict]` | `requests.HTTPError`, `requests.RequestException` | Lists media objects for the configured `IG_USER_ID` and yields them page by page. |

### 3.3 [database.py](database.py)

| Method Signature | Expected Inputs | Return Types | Exceptions Raised | Short Description |
| --- | --- | --- | --- | --- |
| `enqueue(comment: dict, media_name: str, media_id: str) -> bool` | `comment`: Instagram comment dict; `media_name`: slug; `media_id`: Graph ID | `bool` | None directly; DB or data shape issues may raise `KeyError`/`TypeError` | Inserts a comment into the queue if it is not already present, using `INSERT OR IGNORE`. |
| `get_pending_comments(media_name: str | None = None, limit: int | None = None) -> list[sqlite3.Row]` | Optional media filter and optional row limit | `list[sqlite3.Row]` | SQLite errors | Fetches rows in `PENDING`, `DM_SENT`, or `FAILED` states ordered by timestamp. |
| `mark_dm_sent(comment_id: str) -> None` | comment identifier | `None` | SQLite errors | Sets a queue row status to `DM_SENT` after DM success. |
| `mark_done(comment_id: str) -> None` | comment identifier | `None` | SQLite errors | Sets a queue row status to `DONE`. |
| `mark_failed(comment_id: str) -> None` | comment identifier | `None` | SQLite errors | Increments `retries` and sets `FAILED`/`PENDING` based on retry threshold. |
| `queue_size(status: str = "PENDING") -> int` | status string | `int` | SQLite errors | Returns the number of rows in a given queue state. |
| `clear_done() -> None` | None | `None` | SQLite errors | Logs completed rows and removes them from `queue`. |
| `reset_failed() -> None` | None | `None` | SQLite errors | Resets all `FAILED` entries to `PENDING` with zero retries. |
| `utc_to_ist(timestamp: str | None) -> str | None` | ISO 8601 string | `ValueError` if timestamp format is malformed; `TypeError` if `timestamp` is not string-like | Converts UTC timestamp to Asia/Kolkata string format for DB readability. |

### 3.4 [logger.py](logger.py)

This module does not expose functions; it exposes a shared singleton:

- `logger: logging.Logger`

Contract:
- Logging emits to:
  - `logs/instagram.log` via `TimedRotatingFileHandler`
  - stdout via `logging.StreamHandler`
- `logger` is configured once at import time and reused globally.

---

## 4. DEPENDENCIES & ENVIRONMENT SPECIFICATIONS

### Production Dependencies

Exact package set from [requirements.txt](requirements.txt):

| Package | Version | Purpose |
| --- | --- | --- |
| `requests` | `2.34.2` | Primary HTTP client for Meta Graph API calls and pagination. |
| `urllib3` | `2.7.0` | Underlying HTTP stack used by `requests`. |
| `charset-normalizer` | `3.5.1` | Character encoding detection for HTTP responses. |
| `certifi` | `2026.7.22` | CA bundle for TLS verification during outbound API requests. |
| `idna` | `3.19` | Internationalized domain handling for URL encoding. |
| `python-dotenv` | `1.2.3` | Loads environment variables from `.env` into process environment. |

Critical runtime configuration:
- `.env` provides `ACCESS_TOKEN`
- [config.py](config.py) calls `load_dotenv()`
- `BASE_URL = "https://graph.instagram.com/v25.0"`

### Development / Tooling Stack

The repository does not declare a formal dev toolchain such as:

- `ruff`
- `black`
- `mypy`
- `pytest`
- `poetry`
- `uv`

What is actually present is:

- Python interpreter runtime in a local virtual environment (`.venv/` or `venv/`)
- `pip` installation via [requirements.txt](requirements.txt)
- CLI execution through `python main.py ...`
- SQLite CLI interrogation via GitHub Action and shell commands in [.github/workflows/instagram.yml](.github/workflows/instagram.yml)
- GitHub Actions self-hosted runner:
  - `runs-on: [self-hosted, ARM64]`
  - command dispatches for `media`, `discover`, `discover_all`, and `process`

This means the project is a manually managed Python automation script, not a fully standardized dev environment.

---

## 5. IMPLEMENTATION DESIGN PRINCIPLES & STYLE CONVENTIONS

### Coding Standards

The repository follows a practical, minimalistic Python style rather than a formal enterprise framework standard.

Observed conventions:
- snake_case for function names and variables
- UPPERCASE constant names for configuration and static values
- imperative, top-to-bottom workflow logic
- no classes for domain modeling
- no dataclasses
- no Pydantic models
- minimal type hints only on major functions, not enforced globally
- direct dictionary access for API payloads rather than Pydantic validation
- no explicit package/service layer abstraction beyond module boundaries

Important contract reality:
- There is no enforced static typing environment.
- There is no dedicated linter configuration.
- There is no formal test suite in the repo.
- There are no custom exception classes.

### State & Error Handling Strategy

State management:
- Persistent state is stored in SQLite in [database.py](database.py)
- Queue status transitions are the primary system state machine:
  - `PENDING`
  - `DM_SENT`
  - `DONE`
  - `FAILED`
- `mark_failed` is the retry/failure gatekeeper and enforces escalation logic:
  - increment retries
  - if `retries + 1 >= 3`, mark `FAILED`
  - otherwise keep row in `PENDING` unless it was already `DM_SENT`

Error handling:
- API-level errors are captured locally and logged with `logger.exception(...)`
- `requests.HTTPError` is explicitly caught in:
  - `get_comments`
  - `reply_comment`
- DM failures are not raised as exceptions; they are converted into a structured result:
  - `send_dm(...) -> (False, error_dict)`
- generic `Exception` is caught in orchestration loops in [main.py](main.py) to prevent a single failed item from killing the entire batch
- `logger.exception` is used to preserve traceback context

Configuration and security:
- `ACCESS_TOKEN` is loaded from `.env` via `python-dotenv`
- redaction logic exists in `_safe_url(...)` to avoid leaking secrets in logs

Operational patterns:
- randomness is intentionally introduced using `random.choice(...)` and `random.uniform(...)` to reduce predictable behavior
- slow down between queued records with `time.sleep(delay)`
- run loop is sequential and single-threaded, which makes the system easy to reason about but not horizontally scalable

---

## Architectural Summary for AI Code Generators

This project should be treated as:

- a single-process automation script,
- with SQLite as the durable queue,
- Instagram Graph API as the external integration boundary,
- and `main.py` as the orchestrator.

The minimal high-value contract for downstream generators is:

1. preserve the `queue` state machine semantics,
2. keep `instagram.py` as the HTTP adapter layer,
3. keep persistence logic out of `main.py`,
4. retain the current logging conventions,
5. avoid introducing dataclasses or Pydantic unless the project is explicitly refactored to a typed domain model.
