import collections
from typing import List, Optional

class AudioUtteranceBuffer:
    """
    Manages audio frames for a single conversational utterance.
    Maintains a rolling pre-roll buffer to prevent truncating initial phonemes
    when Voice Activity Detection triggers.
    """
    def __init__(self, sample_rate: int = 8000, bytes_per_sample: int = 2, pre_roll_ms: int = 300):
        self.sample_rate = sample_rate
        self.bytes_per_sample = bytes_per_sample
        self.bytes_per_ms = (sample_rate * bytes_per_sample) // 1000
        
        # Pre-roll queue holds the last N milliseconds of audio
        max_pre_roll_bytes = pre_roll_ms * self.bytes_per_ms
        self.pre_roll_chunks: collections.deque = collections.deque(maxlen=15)
        
        self.active_chunks: List[bytes] = []
        self.is_recording: bool = False
        self.start_timestamp: Optional[float] = None

    def add_frame(self, pcm_frame: bytes):
        """Append a frame to pre-roll or active recording buffer."""
        if not self.is_recording:
            self.pre_roll_chunks.append(pcm_frame)
        else:
            self.active_chunks.append(pcm_frame)

    def start_utterance(self, timestamp: float):
        """Transition to recording, transferring pre-roll audio into active utterance."""
        self.is_recording = True
        self.start_timestamp = timestamp
        self.active_chunks = list(self.pre_roll_chunks)
        self.pre_roll_chunks.clear()

    def get_duration_ms(self) -> int:
        """Calculate total audio duration currently buffered in ms."""
        total_bytes = sum(len(c) for c in self.active_chunks)
        if self.bytes_per_ms == 0:
            return 0
        return total_bytes // self.bytes_per_ms

    def get_pcm_bytes(self) -> bytes:
        """Get concatenated PCM audio bytes."""
        return b"".join(self.active_chunks)

    def reset(self):
        """Reset buffers for the next conversational turn."""
        self.is_recording = False
        self.active_chunks = []
        self.start_timestamp = None
        self.pre_roll_chunks.clear()

