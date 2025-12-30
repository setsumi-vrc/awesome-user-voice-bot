import numpy as np
import numpy.typing as npt


def pcm16le_to_float32(pcm: bytes) -> npt.NDArray[np.float32]:
    """Convert PCM16LE audio bytes to float32 numpy array.
    
    Args:
        pcm: Raw PCM16LE audio data.
        
    Returns:
        Normalized float32 audio array in range [-1.0, 1.0].
    """
    audio_i16 = np.frombuffer(pcm, dtype=np.int16)
    return audio_i16.astype(np.float32) / 32768.0


def rms(x: npt.NDArray[np.float32]) -> float:
    """Calculate root mean square (RMS) of audio signal.
    
    Args:
        x: Audio signal array.
        
    Returns:
        RMS value of the signal.
    """
    return float(np.sqrt(np.mean(x * x) + 1e-12))
