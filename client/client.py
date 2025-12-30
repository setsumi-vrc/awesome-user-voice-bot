#!/usr/bin/env python3
"""
VRChat Talkback Bot - Real-time voice interaction client.

Captures game audio, transcribes via STT WebSocket, and responds with TTS.
"""
import asyncio
import logging
import sys
from contextlib import suppress
from pathlib import Path
from typing import Optional

from websockets.exceptions import ConnectionClosed, ConnectionClosedError

from app import (
    CrossPlatformRecorder,
    load_config,
    Metrics,
    metrics_logger,
    TTSClient,
    WebSocketHandler,
)

logger = logging.getLogger(__name__)


class TalkbackClient:
    """Main talkback bot client."""
    
    def __init__(self, config_path: Optional[Path] = None):
        """Initialize client with configuration.
        
        Args:
            config_path: Optional path to config.yaml.
        """
        self.config = load_config(config_path)
        self._setup_logging()
        
        self.metrics = Metrics()
        self.tts_client = TTSClient(self.config.server.tts_url)
        self.recorder = CrossPlatformRecorder(self.config.audio)
    
    def _setup_logging(self) -> None:
        """Configure logging from config."""
        logging.basicConfig(
            level=getattr(logging, self.config.logging.level),
            format=self.config.logging.format,
            datefmt=self.config.logging.date_format
        )
    
    async def run_session(self) -> None:
        """Run one complete client session."""
        audio_queue: asyncio.Queue[bytes] = asyncio.Queue(
            maxsize=self.config.queue.max_size
        )
        stop_event = asyncio.Event()
        
        # Start audio recorder
        await self.recorder.start()
        
        # Create tasks
        tasks = [
            asyncio.create_task(
                self._audio_reader_task(audio_queue, stop_event),
                name="audio_reader"
            ),
            asyncio.create_task(
                self._websocket_task(audio_queue, stop_event),
                name="websocket"
            ),
        ]
        
        # Add metrics logger if enabled
        if self.config.metrics.enabled:
            tasks.append(
                asyncio.create_task(
                    metrics_logger(
                        self.metrics,
                        self.config.metrics.log_interval,
                        stop_event
                    ),
                    name="metrics_logger"
                )
            )
        
        try:
            # Wait for first exception or completion
            done, pending = await asyncio.wait(
                tasks,
                return_when=asyncio.FIRST_EXCEPTION
            )
            
            # Signal stop to all tasks
            stop_event.set()
            
            # Cancel pending tasks
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
            
            # Re-raise first exception
            for task in done:
                exc = task.exception()
                if exc:
                    raise exc
        
        finally:
            await self.recorder.stop()
    
    async def _audio_reader_task(
        self,
        queue: asyncio.Queue[bytes],
        stop_event: asyncio.Event
    ) -> None:
        """Read audio chunks and queue them.
        
        Args:
            queue: Queue for audio chunks.
            stop_event: Event to signal shutdown.
        """
        # Start stderr drainer
        stderr_task = asyncio.create_task(
            self.recorder.drain_stderr(stop_event)
        )
        
        try:
            while not stop_event.is_set():
                chunk = await self.recorder.read_chunk()
                
                # Backpressure: drop oldest if queue full
                if queue.full():
                    with suppress(asyncio.QueueEmpty):
                        queue.get_nowait()
                
                await queue.put(chunk)
        
        finally:
            stderr_task.cancel()
            await asyncio.gather(stderr_task, return_exceptions=True)
    
    async def _websocket_task(
        self,
        queue: asyncio.Queue[bytes],
        stop_event: asyncio.Event
    ) -> None:
        """Manage WebSocket connection.
        
        Args:
            queue: Queue with audio chunks.
            stop_event: Event to signal shutdown.
        """
        handler = WebSocketHandler(
            self.config,
            queue,
            self.tts_client,
            self.metrics,
            stop_event
        )
        
        await handler.connect_and_run()
    
    async def run_with_reconnect(self) -> None:
        """Run client with automatic reconnection."""
        logger.info("🚀 Talkback bot starting...")
        logger.info(f"STT: {self.config.server.stt_ws_url}")
        logger.info(f"TTS: {self.config.server.tts_url}")
        
        while True:
            try:
                await self.run_session()
            
            except (ConnectionClosed, ConnectionClosedError) as e:
                logger.warning(f"🔌 WebSocket disconnected: {e}")
            
            except Exception as e:
                logger.error(f"⚠️  Session error: {e}", exc_info=True)
            
            # Log final metrics before reconnect
            if self.config.metrics.enabled:
                self.metrics.log_summary()
            
            # Reconnect delay
            logger.info(
                f"↻ Reconnecting in {self.config.websocket.reconnect_delay:.1f}s..."
            )
            await asyncio.sleep(self.config.websocket.reconnect_delay)
    
    def cleanup(self) -> None:
        """Cleanup resources."""
        self.tts_client.close()


async def main() -> None:
    """Main entry point."""
    client = TalkbackClient()
    
    try:
        await client.run_with_reconnect()
    except KeyboardInterrupt:
        logger.info("\n👋 Shutting down...")
    finally:
        client.cleanup()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
