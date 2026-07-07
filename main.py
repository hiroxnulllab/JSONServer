#!/usr/bin/env python3
"""
JSONServer — Lightweight JSON-based REST API database server.
Designed for PythonAnywhere free tier.

Usage:
    python main.py                          # Start with defaults
    python main.py --port 8080              # Custom port
    python main.py --env production         # Production mode
    JSONSERVER_API_KEYS=key1,key2 python main.py  # With auth

For PythonAnywhere deployment:
    Import 'jsonserver.app.create_app' as your WSGI entry point.
    See README.md for deployment instructions.
"""

import argparse
import sys

from jsonserver.app import create_app
from jsonserver.config import get_config
from jsonserver.auth import generate_api_key


def main():
    parser = argparse.ArgumentParser(
        description="JSONServer — JSON-based REST API database",
    )
    parser.add_argument(
        "--host", default=None, help="Host to bind (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--port", type=int, default=None, help="Port to bind (default: 5000)"
    )
    parser.add_argument(
        "--env",
        choices=["development", "production", "testing"],
        default=None,
        help="Environment (default: development, or JSONSERVER_ENV env var)"
    )
    parser.add_argument(
        "--generate-key",
        action="store_true",
        help="Generate a new API key and exit",
    )

    args = parser.parse_args()

    # Generate key mode
    if args.generate_key:
        key = generate_api_key()
        print(f"Generated API key: {key}")
        print(f"\nSet it via environment variable:")
        print(f'  set JSONSERVER_API_KEYS={key}    # Windows')
        print(f'  export JSONSERVER_API_KEYS={key}  # Linux/macOS')
        return

    # Override environment if specified
    if args.env:
        import os
        os.environ["JSONSERVER_ENV"] = args.env

    # Create app
    config = get_config()
    app = create_app(config)

    host = args.host or config.HOST
    port = args.port or config.PORT

    print(f"\nJSONServer v1.0.0")
    print(f"Environment: {'development' if config.DEBUG else 'production'}")
    print(f"Database: {config.DB_PATH}")
    print(f"Auth: {'required' if config.REQUIRE_AUTH else 'disabled'}")
    print(f"Rate limit: {config.RATE_LIMIT} req/min")
    print(f"\nListening on http://{host}:{port}")
    print(f"API docs: http://{host}:{port}/api\n")

    app.run(host=host, port=port, debug=config.DEBUG)


if __name__ == "__main__":
    main()
