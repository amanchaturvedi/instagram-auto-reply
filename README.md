# instagram-auto-reply

Instagram comment automation with Reel Insights collection and a lightweight FastAPI dashboard.

## CLI

\`\`\`bash
python main.py discover <media_name> [count]
python main.py discover_all [count]
python main.py process [media_name] [--count N]
python main.py media
python main.py insights [media_id]
python main.py web [--host HOST] [--port PORT]
\`\`\`

## Web UI

Install dependencies:

\`\`\`bash
pip install -r requirements.txt
\`\`\`

Start locally:

\`\`\`bash
python main.py web
\`\`\`

Open:

http://127.0.0.1:8000

FastAPI docs:

http://127.0.0.1:8000/docs

Insights reads historical Reel data from \`insights.json\`. The Comments tab follows the same terminal workflow: Refresh runs \`discover_all\`, the per-Reel Reply runs \`process(media_name)\`, and Reply All runs \`process()\`.

For a network-accessible deployment:

\`\`\`bash
python main.py web --host 0.0.0.0 --port 8000
\`\`\`


Reply configuration is managed from the Config tab. You can enable or disable individual Reels and set each Reel's location. The UI stores these settings in the local `reply_config.json` file; this keeps runtime settings separate from Python source code.

Comment status is derived from the Instagram comment data during discovery; there is no separate `comments.json` state file. The existing `instagram.db` remains the queue/state boundary.