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

from __future__ import annotations

from enum import Enum
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, BinaryIO

if TYPE_CHECKING:
    import numpy

__all__ = ["ASRBase", "Segment", "Word", "Backend"]


@dataclass
class Word:
    start: float
    end: float
    word: str

    def with_offset(self, offset: float) -> Word:
        self.start += offset
        self.end += offset
        return self

    @staticmethod
    def join(words: list[Word]) -> Word:
        return Word(
            start=words[0].start,
            end=words[-1].end,
            word="".join(word.word for word in words),
        )


@dataclass
class Segment:
    start: float
    end: float
    words: list[Word] | None


class Backend(Enum):
    FASTER_WHISPER = 1


class ASRBase(ABC):
    @dataclass
    class ModelConfig:
        pass

    @dataclass
    class TranscribeConfig:
        pass

    @dataclass
    class FeatureExtractorConfig:
        pass

    def __init__(
        self,
        logname: str,
        model_config: ModelConfig,
        transcribe_config: TranscribeConfig,
    ) -> None:
        self.logger = logging.getLogger(logname)

        self.transcribe_config = transcribe_config
        self.model_config = model_config

        self.model = self._load_model(self.model_config)

    @abstractmethod
    def _load_model(self, model_config: ModelConfig):
        pass

    @abstractmethod
    def transcribe(
        self, audio: str | BinaryIO | numpy.ndarray, init_prompt: str
    ) -> tuple[list[Segment], str]:
        pass

    @abstractmethod
    def segments_to_words(self, segments: list[Segment]) -> list[Word]:
        pass

    @staticmethod
    @abstractmethod
    def get_supported_sampling_rates() -> list[int]:
        pass

    @staticmethod
    def check_support_sampling_rate(backend: Backend, sampling_rate: int) -> None:
        if backend == Backend.FASTER_WHISPER:
            from whisper_streaming.backend import FasterWhisperASR

            supported_sampling_rates = FasterWhisperASR.get_supported_sampling_rates()

        else:
            msg = f"Backend {backend} is not supported"
            raise ValueError(msg)

        if sampling_rate not in supported_sampling_rates:
            msg = (
                f"Sampling rate {sampling_rate} is not supported"
                f"The Backend supports: {supported_sampling_rates}"
            )
            raise ValueError(msg)
