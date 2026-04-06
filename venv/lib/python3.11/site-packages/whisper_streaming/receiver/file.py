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
"""Audio Receiver: File."""

from __future__ import annotations

import errno
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, BinaryIO

import librosa
import numpy

from whisper_streaming import AudioReceiver

if TYPE_CHECKING:
    import audioread
    import soundfile


# TODO: implement file looping
class FileReceiver(AudioReceiver):
    def __init__(
        self,
        path: int
        | os.PathLike[Any]
        | soundfile.SoundFile
        | audioread.AudioFile
        | BinaryIO,
        chunk_size: float,
        target_sample_rate: int,
    ) -> None:
        """Initialize the receiver.

        Args:
            path: Path to the file. This can be any :py:class:`os.PathLike`, a file
            descriptor, a supported object or a binary file-like object.
            chunk_size: Length of each chunk in seconds.
            target_sample_rate: Sample rate of the audio file in Hertz.

        Raises:
             FileNotFoundError: File does not exist at path.
        """
        super().__init__()

        self.chunk_size = chunk_size
        self.target_sample_rate = target_sample_rate

        if isinstance(path, os.PathLike):
            path = path if isinstance(path, Path) else Path(path)

            if not path.is_file():
                raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), path)

        self.audio, _ = librosa.load(
            path,
            sr=self.target_sample_rate,
            dtype=numpy.float32,
        )

        # TODO: Implement offset
        self.begin = 0
        self.end = self.begin + self.chunk_size

    def _do_receive(self) -> str | BinaryIO | numpy.ndarray | None:
        """Receive data from.

        Returns:
            Data, or None if receiver is stopped or file is read completely.
        """
        if self.stopped.is_set() or self.begin * self.target_sample_rate > len(
            self.audio
        ):
            audio = None
        else:
            if self.end * self.target_sample_rate > len(self.audio):
                self.end = len(self.audio)

            audio = self.audio[
                int(self.begin * self.target_sample_rate) : int(
                    self.end * self.target_sample_rate,
                )
            ]
            self.begin = self.end
            self.end += self.chunk_size
        return audio

    def _do_close(self) -> None:
        pass
