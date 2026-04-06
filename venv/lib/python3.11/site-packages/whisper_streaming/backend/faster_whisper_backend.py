# This file includes code derived from "whisper_streaming", licensed under the MIT
# License:
# https://github.com/ufal/whisper_streaming
#
# Original copyright:
# Copyright (c) 2023 ÚFAL
# Licensed under the MIT License. See LICENSE-MIT for details.
#
# Modifications Copyright 2025 Niklas Kaaf <nkaaf@protonmail.com>
# Licensed under the Apache License, Version 2.0
# http://www.apache.org/licenses/LICENSE-2.0

"""Wrapper implementation for Faster-Whisper."""

from __future__ import annotations

import dataclasses
import json
import tempfile
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, BinaryIO

from faster_whisper import WhisperModel
from faster_whisper.transcribe import Segment as FasterWhisperSegment
from faster_whisper.transcribe import Word as FasterWhisperWord

from whisper_streaming.base import ASRBase
from whisper_streaming.base import Segment as BaseSegment
from whisper_streaming.base import Word as BaseWord

if TYPE_CHECKING:
    import numpy
    from faster_whisper.vad import VadOptions

__all__ = [
    "FasterWhisperASR",
    "FasterWhisperFeatureExtractorConfig",
    "FasterWhisperModelConfig",
    "FasterWhisperTranscribeConfig",
]


@dataclass
class FasterWhisperModelConfig(ASRBase.ModelConfig):
    """Model configuration for Faster-Whisper.

    Information about the parameters can be found in the in-code documentation of
    Faster-Whisper,
    more precisely in :py:meth:`faster_whisper.transcribe.WhisperModel.__init__()` and
    :py:meth:`ctranslate2.models.Whisper.__init__()`.
    """

    model_size_or_path: str
    device: str = "auto"
    """ :py:attr:`ctranslate2.models.Whisper.device` """
    device_index: int | list[int] = 0
    """ :py:attr:`ctranslate2.models.Whisper.device_index` """
    compute_type: str = "default"
    """ :py:attr:`ctranslate2.models.Whisper.compute_type` """
    cpu_threads: int = 0
    num_workers: int = 1
    download_root: str | None = None
    local_files_only: bool = False
    # files: dict = None
    max_queued_batches: int = 0
    flash_attention: bool = False
    tensor_parallel: bool = False
    """ :py:attr:`ctranslate2.models.Whisper.tensor_parallel` """


@dataclass
class FasterWhisperTranscribeConfig(ASRBase.TranscribeConfig):
    """Transcribe configuration for Faster-Whisper.

    Information about the parameters can be found in the in-code documentation of
    Faster-Whisper,
    more precisely in :py:meth:`faster_whisper.transcribe.WhisperModel.transcribe`.
    """

    # language: str | None = None
    task: str = "transcribe"
    log_progress: bool = False
    beam_size: int = 5
    best_of: int = 5
    patience: float = 1
    length_penalty: float = 1
    repetition_penalty: float = 1
    no_repeat_ngram_size: int = 0
    temperature: list[float] = field(
        default_factory=lambda: [0.0, 0.2, 0.4, 0.6, 0.8, 1.0],
    )
    compression_ratio_threshold: float | None = 2.4
    log_prob_threshold: float | None = -1.0
    no_speech_threshold: float | None = 0.6
    # condition_on_previous_text: bool = True
    prompt_reset_on_temperature: float = 0.5
    # initial_prompt: Optional[Union[str, Iterable[int]]] = None
    prefix: str | None = None
    suppress_blank: bool = True
    suppress_tokens: list[int] | None = field(default_factory=lambda: [-1])
    without_timestamps: bool = False
    max_initial_timestamp: float = 1.0
    # word_timestamps: bool = False
    prepend_punctuations: str = "\"'“¿([{-"
    append_punctuations: str = "\"'.。,，!！?？:：”)]}、"
    multilingual: bool = False
    vad_filter: bool = False
    vad_parameters: dict | VadOptions | None = None
    max_new_tokens: int | None = None
    chunk_length: int | None = None
    clip_timestamps: str | list[float] = "0"
    hallucination_silence_threshold: float | None = None
    hotwords: str | None = None
    language_detection_threshold: float | None = 0.5
    language_detection_segments: int = 1


@dataclass
class FasterWhisperFeatureExtractorConfig(ASRBase.FeatureExtractorConfig):
    """FeatureExtractor configuration for Faster-Whisper."""

    feature_size: int = 80
    # sampling_rate: int = 16000
    hop_length: int = 160
    chunk_length: int = 30
    n_fft: int = 400


@dataclass
class Word(BaseWord, FasterWhisperWord):
    """Class defining a Word (or sequence of words) in Faster-Whisper.
    Because of convention from publications and wide-spread implementations, this is
    called 'Word'
    too.
    """

    @classmethod
    def create_from(cls, word: FasterWhisperWord) -> Word:
        """Args:
            word:

        Returns:

        """
        word.__class__ = dataclasses.make_dataclass(
            cls.__name__,
            fields=[
                (_field.name, _field.type) for _field in dataclasses.fields(BaseWord)
            ],
            bases=(BaseWord,),
        )
        word.start = word.start
        word.end = word.end
        word.word = word.word
        return word


@dataclass
class Segment(BaseSegment, FasterWhisperSegment):
    pass


class FasterWhisperASR(ASRBase):
    def __init__(
        self,
        model_config: FasterWhisperModelConfig,
        transcribe_config: FasterWhisperTranscribeConfig,
        feature_extractor_config: FasterWhisperFeatureExtractorConfig,
        sample_rate: int,
        language: str | None,
    ) -> None:
        # Set sample rate
        feature_extractor_config_dict = dataclasses.asdict(feature_extractor_config)
        feature_extractor_config_dict["sampling_rate"] = sample_rate

        self.temp_file_feature_extractor = tempfile.NamedTemporaryFile(
            mode="w+",
            encoding="UTF-8",
        )
        self.temp_file_feature_extractor.write(
            json.dumps(feature_extractor_config_dict),
        )
        self.temp_file_feature_extractor.flush()

        super().__init__("FasterWhisper", model_config, transcribe_config)

        # Set language
        self.language = language

    def _load_model(self, model_config: FasterWhisperModelConfig):
        return WhisperModel(
            **dataclasses.asdict(model_config),
            # TODO: Setting files, will result in an exception, because all relevant files are required here
            #  files={"preprocessor_config.json": self.temp_file_feature_extractor.name},
        )

    def transcribe(
        self,
        audio: str | BinaryIO | numpy.ndarray,
        init_prompt: str,
    ) -> tuple[list[Segment], str]:
        model: WhisperModel = self.model
        segments, info = model.transcribe(
            audio,
            initial_prompt=init_prompt,
            word_timestamps=True,
            condition_on_previous_text=True,
            language=self.language,
            **dataclasses.asdict(self.transcribe_config),
        )
        return list(segments), info.language

    def segments_to_words(self, segments: list[Segment]) -> list[Word]:
        return [
            Word.create_from(word) for segment in segments for word in segment.words
        ]

    def get_supported_sampling_rates() -> list[int]:
        return [16000]

    def __del__(self) -> None:
        self.temp_file_feature_extractor.close()
