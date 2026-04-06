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

"""Package importing all backends, that can be used for whisper-streaming."""

import importlib.util

__all__ = []

if importlib.util.find_spec("faster_whisper") is not None:
    from .faster_whisper_backend import (
        FasterWhisperASR,
        FasterWhisperFeatureExtractorConfig,
        FasterWhisperModelConfig,
        FasterWhisperTranscribeConfig,
    )

    __all__.extend(
        [
            "FasterWhisperASR",
            "FasterWhisperFeatureExtractorConfig",
            "FasterWhisperModelConfig",
            "FasterWhisperTranscribeConfig",
        ]
    )
