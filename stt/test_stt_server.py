import pytest
import numpy as np
from unittest.mock import Mock, patch
from core.audio import pcm16le_to_float32, rms
from core.config import get_settings

settings = get_settings()
SAMPLE_RATE = settings.SAMPLE_RATE


class TestAudioProcessing:
    def test_pcm16le_to_float32_conversion(self):
        """Test PCM16LE to float32 conversion."""
        # Create test PCM16LE data (16-bit signed integers)
        pcm_data = np.array([0, 32767, -32768, 16384], dtype=np.int16)
        pcm_bytes = pcm_data.tobytes()

        result = pcm16le_to_float32(pcm_bytes)

        expected = pcm_data.astype(np.float32) / 32768.0
        np.testing.assert_array_almost_equal(result, expected)

    def test_rms_calculation(self):
        """Test RMS calculation."""
        # Test with simple array
        audio = np.array([1.0, -1.0, 1.0, -1.0])
        result = rms(audio)
        expected = 1.0  # RMS of alternating 1 and -1
        assert abs(result - expected) < 1e-6

        # Test with zeros
        audio = np.array([0.0, 0.0, 0.0])
        result = rms(audio)
        assert result <= 1e-6  # Should be very close to 0 (includes epsilon)


class TestBasicFunctionality:
    def test_sample_rate_constant(self):
        """Test that SAMPLE_RATE is set correctly."""
        assert SAMPLE_RATE == 16000

    def test_app_creation(self):
        """Test that the FastAPI app can be imported."""
        from stt.server import app
        assert app is not None