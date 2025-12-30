import importlib


def test_import_stt_and_tts_apps():
    stt = importlib.import_module("stt.server")
    tts = importlib.import_module("tts.server")
    assert hasattr(stt, "app"), "stt.server should expose `app`"
    assert hasattr(tts, "app"), "tts.server should expose `app`"


def test_core_modules_export():
    core_audio = importlib.import_module("core.audio")
    core_config = importlib.import_module("core.config")
    assert hasattr(core_audio, "pcm16le_to_float32")
    assert hasattr(core_audio, "rms")
    assert hasattr(core_config, "get_settings")
