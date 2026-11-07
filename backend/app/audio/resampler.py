import audioop
from typing import Tuple

def resample_pcm(pcm_bytes: bytes, in_rate: int, out_rate: int, width: int = 2, channels: int = 1) -> bytes:
    """
    Resample PCM audio from in_rate to out_rate.
    """
    if in_rate == out_rate or not pcm_bytes:
        return pcm_bytes
    converted, _ = audioop.ratecv(pcm_bytes, width, channels, in_rate, out_rate, None)
    return converted

