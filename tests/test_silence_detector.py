import time
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.services.silence_detector import SilenceDetector

def test_silence_detector_full_lifecycle():
    # 20ms chunk = 160 samples = 320 bytes of 16-bit PCM at 8000Hz
    silence_chunk = b"\x00\x00" * 160
    # Create speech chunk with high amplitude (RMS ~1000+)
    speech_chunk = (b"\x50\x20\x50\xd0") * 80

    detector = SilenceDetector(
        silence_threshold_ms=200,  # 200ms for fast unit test
        min_utterance_ms=50,
        energy_threshold=300,
        sample_rate=8000
    )

    # 1. Feed silence -> state should remain NONE
    status, audio, dur = detector.process_frame(silence_chunk)
    assert status == "NONE"
    assert audio is None

    # 2. Feed speech frames (onset requires 4 consecutive frames to filter line clicks)
    assert detector.process_frame(speech_chunk)[0] == "NONE"  # Frame 1
    assert detector.process_frame(speech_chunk)[0] == "NONE"  # Frame 2
    assert detector.process_frame(speech_chunk)[0] == "NONE"  # Frame 3
    status4, _, _ = detector.process_frame(speech_chunk)
    assert status4 == "SPEECH_STARTED"  # Frame 4 triggers onset!

    # 3. Speech continuing
    for _ in range(5):
        status, _, _ = detector.process_frame(speech_chunk)
        assert status == "SPEECH_CONTINUING"

    # 4. Now simulate user stopped talking: feed silence chunks and wait threshold
    time.sleep(0.25)  # Wait past the 200ms silence threshold

    status, audio, dur = detector.process_frame(silence_chunk)
    assert status == "UTTERANCE_COMPLETE"
    assert audio is not None
    assert len(audio) > 0
    print("Silence detector unit tests passed successfully!")

if __name__ == "__main__":
    test_silence_detector_full_lifecycle()

