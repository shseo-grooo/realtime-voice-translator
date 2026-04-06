# Copyright 2025 Niklas Kaaf <nkaaf@protonmail.com>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Audio Receiver: ALSA."""

from __future__ import annotations

import tempfile
import wave
from threading import Lock
from typing import BinaryIO

import alsaaudio
import librosa
import numpy

from whisper_streaming import AudioReceiver

__all__ = ["AlsaReceiver"]


class AlsaReceiver(AudioReceiver):
    """Class for receiving audio from ALSA (Advanced Linux Sound Architecture).

    For more information about the terminology, see [the official documentation](
    https://larsimmisch.github.io/pyalsaaudio/terminology.html).
    """

    def __init__(
        self,
        device: str,
        chunk_size: float,
        target_sample_rate: int,
        *,
        periodsize: int = 1024,
    ) -> None:
        """Initialize the receiver.

        Args:
            device: ALSA device name.
            chunk_size: Length of each chunk in seconds.
            target_sample_rate: Sample rate of audio samples in Hertz.
            periodsize: Count of frames per period.
        """
        super().__init__()

        self.chunk_size = chunk_size
        self.target_sample_rate = target_sample_rate

        self.channels = 1
        self.pcm = alsaaudio.PCM(
            type=alsaaudio.PCM_CAPTURE,
            format=alsaaudio.PCM_FORMAT_S16_LE,
            channels=self.channels,
            periodsize=periodsize,
            rate=self.target_sample_rate,
            device=device,
        )

        self.iterations = self.chunk_size / (periodsize / self.target_sample_rate)
        self.pcm_lock = Lock()

    def _do_receive(self) -> str | BinaryIO | numpy.ndarray | None:
        """Receive data from ALSA device.

        Returns:
            Data, or None if receiver is stopped.
        """
        if self.stopped.is_set():
            audio = None
        else:
            with tempfile.NamedTemporaryFile() as temp_audio_file:
                with wave.open(temp_audio_file.name, mode="wb") as wavefile:
                    wavefile.setnchannels(self.channels)
                    wavefile.setsampwidth(2)  # PCM_FORMAT_S16_LE
                    wavefile.setframerate(self.target_sample_rate)

                    i = 1
                    while i < self.iterations and not self.stopped.is_set():
                        with self.pcm_lock:
                            data = self.pcm.read()[1]
                        wavefile.writeframes(data)
                        i += 1

                if self.stopped.is_set():
                    audio = None
                else:
                    audio = librosa.load(
                        temp_audio_file.name,
                        sr=self.target_sample_rate,
                        dtype=numpy.float32,
                    )[0]
                    # TODO: can the wavefile save and read be skipped?

        return audio

    def _do_close(self) -> None:
        with self.pcm_lock:
            self.pcm.close()
