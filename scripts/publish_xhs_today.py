from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nsg_price.config import load_config
from nsg_price.paths import publish_dir, today_date
from nsg_price.publish import build_publish_pack, normalize_session
from nsg_price.xiaohongshu import publish_to_xiaohongshu


def latest_existing_session(config: dict, date: str) -> str | None:
    base = publish_dir(date, config)
    for session in ("pm", "am"):
        if (base / session / "manifest.json").exists():
            return session
    if (base / "manifest.json").exists():
        return None
    return "pm"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build today's publish pack, open controllable Edge, and fill Xiaohongshu Creator Center."
    )
    parser.add_argument("--config", default=str(ROOT / "config.json"), help="config path")
    parser.add_argument("--date", default=today_date(), help="YYYY-MM-DD; defaults to today")
    parser.add_argument("--session", choices=["am", "pm"], help="am/pm publish pack; defaults to latest existing pack")
    parser.add_argument("--port", type=int, default=9223, help="Edge remote debugging port")
    parser.add_argument("--profile-dir", help="Edge user-data-dir; defaults to the project automation profile")
    parser.add_argument("--edge-path", help="path to msedge.exe")
    parser.add_argument("--no-regenerate", action="store_true", help="use the existing report/publish pack")
    parser.add_argument("--no-launch-edge", action="store_true", help="connect to an already running remote-debugging Edge")
    parser.add_argument("--publish", action="store_true", help="click the final publish button after filling the post")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    config = load_config(args.config)
    session = normalize_session(args.session) if args.session else latest_existing_session(config, args.date)

    pack_dir, outputs = build_publish_pack(
        config,
        target_date=args.date,
        target_session=session,
        regenerate_report=not args.no_regenerate,
    )
    print(f"publish pack: {pack_dir}")
    for output in outputs:
        print(f"  {output}")

    result = publish_to_xiaohongshu(
        config=config,
        target_date=args.date,
        target_session=session,
        pack_dir=pack_dir,
        port=args.port,
        publish=args.publish,
        launch_edge=not args.no_launch_edge,
        profile_dir=args.profile_dir,
        edge_path=args.edge_path,
    )
    print(f"xhs status: {result.status}")
    print(f"title: {result.title}")
    print(f"images: {result.image_count}")
    print(f"url: {result.url}")
    print(f"screenshot: {result.screenshot}")
    print(result.message)


if __name__ == "__main__":
    main()
