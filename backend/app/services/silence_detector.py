import time
import logging
from typing import Optional, Tuple
from app.audio.codec import calculate_rms
from app.audio.buffer import AudioUtteranceBuffer

logger = logging.getLogger("sales_agent.silence_detector")

class SilenceDetector:
    """
    Real-time Voice Activity and Silence Detector.
    Tracks audio energy over streaming PCM chunks, manages speech onset,
    maintains audio buffering, and triggers an utterance completion event
    precisely after 1000ms of sustained post-speech silence.
    """
    def __init__(
        self,
        silence_threshold_ms: int = 1000,
        min_utterance_ms: int = 300,
        energy_threshold: int = 300,
        sample_rate: int = 8000
    ):
        self.silence_threshold_ms = silence_threshold_ms
        self.min_utterance_ms = min_utterance_ms
        self.energy_threshold = energy_threshold
        self.sample_rate = sample_rate

        self.buffer = AudioUtteranceBuffer(sample_rate=sample_rate)
        self.is_speech_active = False
        self.consecutive_speech_frames = 0
        self.required_speech_frames = 4  # ~80ms of speech to confirm onset (filters clicks/line noise)
        self.last_speech_time: Optional[float] = None
        self.utterance_start_time: Optional[float] = None

    def process_frame(self, pcm_chunk: bytes) -> Tuple[str, Optional[bytes], int]:
        """
        Process an incoming linear PCM audio chunk (~20ms).
        Returns:
            status: 'NONE' | 'SPEECH_STARTED' | 'SPEECH_CONTINUING' | 'UTTERANCE_COMPLETE'
            audio_bytes: Captured PCM bytes if status == 'UTTERANCE_COMPLETE', else None
            duration_ms: Current utterance duration
        """
        now = time.time()
        rms = calculate_rms(pcm_chunk)
        is_frame_speech = rms > self.energy_threshold

        # Append frame to buffer
        self.buffer.add_frame(pcm_chunk)

        if not self.is_speech_active:
            # Idle state - listening for speech onset
            if is_frame_speech:
                self.consecutive_speech_frames += 1
                if self.consecutive_speech_frames >= self.required_speech_frames:
                    self.is_speech_active = True
                    self.utterance_start_time = now
                    self.last_speech_time = now
                    self.buffer.start_utterance(now)
                    logger.debug(f"[VAD] Speech onset detected! RMS={rms}")
                    return "SPEECH_STARTED", None, 0
            else:
                self.consecutive_speech_frames = 0
            return "NONE", None, 0

        else:
            # Active speech state
            if is_frame_speech:
                self.last_speech_time = now
                self.consecutive_speech_frames += 1
                return "SPEECH_CONTINUING", None, self.buffer.get_duration_ms()
            else:
                # Frame is silent or background noise
                self.consecutive_speech_frames = 0
                silence_duration_ms = (now - self.last_speech_time) * 1000 if self.last_speech_time else 0
                
                # Check if silence timer has crossed threshold (2.0 seconds)
                if silence_duration_ms >= self.silence_threshold_ms:
                    total_duration_ms = self.buffer.get_duration_ms()
                    
                    if total_duration_ms >= self.min_utterance_ms:
                        # Meaningful utterance finished
                        logger.info(
                            f"[VAD] Utterance complete! Duration={total_duration_ms}ms, "
                            f"Silence={int(silence_duration_ms)}ms"
                        )
                        audio_pcm = self.buffer.get_pcm_bytes()
                        self.reset()
                        return "UTTERANCE_COMPLETE", audio_pcm, total_duration_ms
                    else:
                        # Transient noise or cough < 300ms, discard
                        logger.debug(f"[VAD] Discarding short noise ({total_duration_ms}ms)")
                        self.reset()
                        return "NONE", None, 0

                return "SPEECH_CONTINUING", None, self.buffer.get_duration_ms()

    def reset(self):
        """Reset state machine for the next conversational turn."""
        self.is_speech_active = False
        self.consecutive_speech_frames = 0
        self.last_speech_time = None
        self.utterance_start_time = None
        self.buffer.reset()

