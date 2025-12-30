#!/usr/bin/env python3
"""Example usage of talkback client with custom config."""
import asyncio
import sys
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent))

from client import TalkbackClient


async def main():
    """Run talkback bot with custom configuration."""
    # Option 1: Use default config.yaml in client directory
    client = TalkbackClient()
    
    # Option 2: Use custom config path
    # custom_config = Path("my_custom_config.yaml")
    # client = TalkbackClient(config_path=custom_config)
    
    try:
        await client.run_with_reconnect()
    except KeyboardInterrupt:
        print("\n👋 Shutting down gracefully...")
    finally:
        client.cleanup()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
