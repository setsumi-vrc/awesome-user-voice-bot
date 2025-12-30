"""Voice Activity Detection (VAD) state management."""
import time
from dataclasses import dataclass


@dataclass
class VADState:
    """Manages voice activity detection state."""
    
    # Configuration
    silence_threshold: float
    silence_max_seconds: float
    min_utterance_seconds: float
    utterance_cooldown: float
    
    # State
    in_utterance: bool = False
    utterance_start: float = 0.0
    last_voice_time: float = 0.0
    last_utterance_end: float = 0.0
    
    def can_start_utterance(self, now: float) -> bool:
        """Check if enough time has passed to start new utterance.
        
        Args:
            now: Current monotonic timestamp.
            
        Returns:
            True if cooldown period has elapsed.
        """
        return (now - self.last_utterance_end) >= self.utterance_cooldown
    
    def start_utterance(self, now: float) -> None:
        """Begin a new utterance.
        
        Args:
            now: Current monotonic timestamp.
        """
        self.in_utterance = True
        self.utterance_start = now
        self.last_voice_time = now
    
    def update_voice_activity(self, now: float) -> None:
        """Mark voice detected at current time.
        
        Args:
            now: Current monotonic timestamp.
        """
        self.last_voice_time = now
    
    def should_end_utterance(self, now: float) -> bool:
        """Check if utterance should end due to silence.
        
        Args:
            now: Current monotonic timestamp.
            
        Returns:
            True if silence duration exceeds threshold.
        """
        if not self.in_utterance:
            return False
        return (now - self.last_voice_time) >= self.silence_max_seconds
    
    def end_utterance(self, now: float) -> float:
        """End current utterance and return its duration.
        
        Args:
            now: Current monotonic timestamp.
            
        Returns:
            Utterance duration in seconds.
        """
        duration = now - self.utterance_start
        self.in_utterance = False
        self.last_utterance_end = now
        return duration
    
    def is_utterance_valid(self, duration: float) -> bool:
        """Check if utterance meets minimum duration requirement.
        
        Args:
            duration: Utterance duration in seconds.
            
        Returns:
            True if duration meets minimum threshold.
        """
        return duration >= self.min_utterance_seconds
