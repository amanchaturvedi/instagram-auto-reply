import argparse
import json

from app.comments import discover, discover_all, process
from app.config import get_replyable_media
from app.insights.collector import collect_reel_insights
from app.instagram import get_media
from app.logger import logger

DISCOVER_DEFAULT = 100


def main():
    parser = argparse.ArgumentParser(
        description="Instagram automation"
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    discover_parser = subparsers.add_parser(
        "discover",
        help="Fetch latest comments and enqueue eligible ones",
    )
    discover_parser.add_argument(
        "media_name",
        help="Configured Reel name",
    )
    discover_parser.add_argument(
        "count",
        type=int,
        nargs="?",
        default=DISCOVER_DEFAULT,
        help="Number of comments to scan",
    )

    process_parser = subparsers.add_parser(
        "process",
        help="Process queued comments",
    )
    process_parser.add_argument(
        "media_name",
        nargs="?",
        default=None,
        help="Configured Reel name. If omitted, processes all pending comments.",
    )
    process_parser.add_argument(
        "-n",
        "--count",
        type=int,
        default=None,
        help="Number of queued comments to process",
    )

    subparsers.add_parser(
        "media",
        help="List recent media",
    )

    discover_all_parser = subparsers.add_parser(
        "discover_all",
        help="Discover comments for all configured media",
    )
    discover_all_parser.add_argument(
        "count",
        type=int,
        nargs="?",
        default=DISCOVER_DEFAULT,
        help="Number of top-level comments to scan per media",
    )

    insights_parser = subparsers.add_parser(
        "insights",
        help="Collect Reel Insights snapshots",
    )
    insights_parser.add_argument(
        "media_id",
        nargs="?",
        default=None,
        help="Optional Instagram media ID. If omitted, collects all Reels.",
    )

    web_parser = subparsers.add_parser(
        "web",
        help="Start the FastAPI web UI",
    )
    web_parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Bind host",
    )
    web_parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Bind port",
    )

    args = parser.parse_args()

    if args.command == "discover":
        if args.media_name not in get_replyable_media():
            parser.error("Unknown or disabled Reel: " + args.media_name)
        discover(args.media_name, args.count)

    elif args.command == "process":
        process(args.media_name, args.count)

    elif args.command == "media":
        media_list = list(get_media())

        with open("media.json", "w", encoding="utf-8") as f:
            json.dump(
                media_list,
                f,
                indent=4,
                ensure_ascii=False,
            )

        print(f"Saved {len(media_list)} media items to media.json")

    elif args.command == "discover_all":
        discover_all(args.count)

    elif args.command == "insights":
        logger.info(
            "Starting insights command media_id=%s",
            args.media_id,
            extra={"highlight": "start"},
        )
        collect_reel_insights(args.media_id)

    elif args.command == "web":
        import uvicorn

        uvicorn.run(
            "app.web.server:app",
            host=args.host,
            port=args.port,
        )


if __name__ == "__main__":
    main()
