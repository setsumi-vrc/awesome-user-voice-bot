"""Metrics tracking for talkback client."""
import asyncio
import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class Metrics:
    """Tracks performance and usage metrics."""
    
    # Counters
    transcriptions: int = 0
    responses_generated: int = 0
    responses_skipped: int = 0
    
    # Latencies (running totals for averaging)
    total_stt_latency: float = 0.0
    total_tts_latency: float = 0.0
    total_e2e_latency: float = 0.0
    
    # Errors
    stt_errors: int = 0
    tts_errors: int = 0
    
    def record_transcription(self, duration: float) -> None:
        """Record successful transcription.
        
        Args:
            duration: STT processing time in seconds.
        """
        self.transcriptions += 1
        self.total_stt_latency += duration
    
    def record_response(self, tts_duration: float, e2e_duration: float) -> None:
        """Record successful response.
        
        Args:
            tts_duration: TTS generation time in seconds.
            e2e_duration: Total end-to-end time in seconds.
        """
        self.responses_generated += 1
        self.total_tts_latency += tts_duration
        self.total_e2e_latency += e2e_duration
    
    def record_skip(self) -> None:
        """Record skipped response (cooldown)."""
        self.responses_skipped += 1
    
    def record_stt_error(self) -> None:
        """Record STT error."""
        self.stt_errors += 1
    
    def record_tts_error(self) -> None:
        """Record TTS error."""
        self.tts_errors += 1
    
    @property
    def avg_stt_latency(self) -> float:
        """Average STT latency in seconds."""
        return self.total_stt_latency / self.transcriptions if self.transcriptions > 0 else 0.0
    
    @property
    def avg_tts_latency(self) -> float:
        """Average TTS latency in seconds."""
        return self.total_tts_latency / self.responses_generated if self.responses_generated > 0 else 0.0
    
    @property
    def avg_e2e_latency(self) -> float:
        """Average end-to-end latency in seconds."""
        return self.total_e2e_latency / self.responses_generated if self.responses_generated > 0 else 0.0
    
    def log_summary(self) -> None:
        """Log metrics summary."""
        logger.info(
            f"📊 Metrics - "
            f"Transcriptions: {self.transcriptions}, "
            f"Responses: {self.responses_generated}, "
            f"Skipped: {self.responses_skipped}, "
            f"STT errors: {self.stt_errors}, "
            f"TTS errors: {self.tts_errors}"
        )
        
        if self.transcriptions > 0:
            logger.info(
                f"⏱️  Latency - "
                f"STT: {self.avg_stt_latency:.2f}s, "
                f"TTS: {self.avg_tts_latency:.2f}s, "
                f"E2E: {self.avg_e2e_latency:.2f}s"
            )


async def metrics_logger(metrics: Metrics, interval: float, stop_event: asyncio.Event) -> None:
    """Periodically log metrics summary.
    
    Args:
        metrics: Metrics object to log.
        interval: Logging interval in seconds.
        stop_event: Event to signal shutdown.
    """
    while not stop_event.is_set():
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval)
        except asyncio.TimeoutError:
            metrics.log_summary()
