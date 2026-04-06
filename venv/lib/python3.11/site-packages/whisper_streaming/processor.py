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

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from queue import Empty, Queue
from threading import Event, Thread
from typing import BinaryIO

from mosestokenizer import MosesTokenizer
import numpy

from .base import ASRBase, Word, Backend

__all__ = [
    "ASRProcessor",
    "AudioReceiver",
    "OutputSender",
    "SentenceTrimming",
    "TimeTrimming",
]


class AudioReceiver(ABC, Thread):
    def __init__(self) -> None:
        Thread.__init__(self, target=self._run)

        self.queue = Queue()

        self._logger = logging.getLogger(self.__class__.__name__)
        self.stopped = Event()

    def _run(self) -> None:
        while not self.stopped.is_set():
            try:
                data = self._do_receive()
            except:  # noqa: PERF203
                self._logger.exception("Audio receiver throw exception")
                self.stopped.set()
            else:
                if data is None:
                    self.stopped.set()
                else:
                    self.queue.put_nowait(data)

    def close(self) -> None:
        self.stopped.set()
        self._do_close()

    @abstractmethod
    def _do_receive(self) -> str | BinaryIO | numpy.ndarray | None:
        pass

    @abstractmethod
    def _do_close(self) -> None:
        pass


class OutputSender(ABC, Thread):
    def __init__(self) -> None:
        Thread.__init__(self, target=self._run)

        self.queue = Queue()

        self._logger = logging.getLogger(self.__class__.__name__)
        self.stopped = Event()

    def _run(self) -> None:
        while not self.stopped.is_set():
            try:
                data = self.queue.get_nowait()
            except Empty:  # noqa: PERF203
                time.sleep(0.1)
                continue
            else:
                try:
                    self._do_output(data)
                except:
                    self._logger.exception("Output sender throw exception")
                    break

    def close(self) -> None:
        self.stopped.set()
        self._do_close()

    @abstractmethod
    def _do_output(self, data: Word) -> None:
        pass

    @abstractmethod
    def _do_close(self) -> None:
        pass


# TODO: Rework
class TranscriptionBuffer:
    @dataclass
    class Config:
        max_n_gramms_to_commit: int = 5
        """Count of n-grams (between new transcriptions and transcriptions in limbo) to 
        commit the transcription. If there are less than max_n_gramms_to_commit new 
        transcriptions or transcriptions in limbo, than use its size."""
        overlap_committed_and_new_transcription: float = 0.1
        # TODO:
        watch_interval: float = 1
        # TODO:

    def __init__(self, config: Config) -> None:
        self.config = config

        self.logger = logging.getLogger(self.__class__.__name__)

        self._transcriptions_committed: list[Word] = []
        self._transcriptions_in_limbo: list[Word] = []

        self._last_committed_offset: None | float = None
        self._index_first_committed_in_buffer: None | int = None

    @property
    def context(self) -> list[Word]:
        if self._index_first_committed_in_buffer is None:
            return []

        return list(
            self._transcriptions_committed[: self._index_first_committed_in_buffer]
        )

    @property
    def prompt_candidates(self) -> list[Word]:
        if self._index_first_committed_in_buffer is None:
            return []

        return list(
            self._transcriptions_committed[self._index_first_committed_in_buffer :]
        )

    @property
    def transcriptions_in_limbo(self) -> list[Word]:
        return list(self._transcriptions_in_limbo)

    def insert(self, words: list[Word]) -> list[Word]:
        """Insert new transcriptions.

        Args:
            words: List of new transcriptions

        Returns:
            List of newly committed transcriptions
        """
        commit: list[Word] = []

        new_transcriptions = [
            word
            for word in words
            if self._last_committed_offset is None
            or word.start
            > (
                self._last_committed_offset
                - self.config.overlap_committed_and_new_transcription
            )
        ]

        if not (
            len(new_transcriptions) == 0
            or self._index_first_committed_in_buffer is None
        ):
            if (
                next(
                    (
                        word
                        for word in new_transcriptions
                        if abs(word.start - self._last_committed_offset)
                        < self.config.watch_interval
                    ),
                    None,
                )
                is None
            ):
                return commit

            for i in range(
                1,
                min(
                    len(new_transcriptions),
                    (
                        len(self._transcriptions_committed)
                        - self._index_first_committed_in_buffer
                    ),
                    self.config.max_n_gramms_to_commit,
                )
                + 1,
            ):
                committed_ngram = " ".join(
                    reversed(
                        [
                            self._transcriptions_committed[
                                self._index_first_committed_in_buffer :
                            ][-j].word
                            for j in range(1, i + 1)
                        ]
                    )
                )
                new_ngram = " ".join(
                    new_transcriptions[j - 1].word for j in range(1, i + 1)
                )

                if committed_ngram == new_ngram:
                    for j in range(i):
                        new_transcriptions.pop(j)

        while len(new_transcriptions) > 0:
            new_transcript = new_transcriptions[0]

            if len(self._transcriptions_in_limbo) == 0:
                break

            if new_transcript.word == self._transcriptions_in_limbo[0].word:
                commit.append(new_transcript)
                self._transcriptions_in_limbo.pop(0)
                new_transcriptions.pop(0)
                self._last_committed_offset = new_transcript.end
            else:
                break

        self._transcriptions_in_limbo = new_transcriptions
        # TODO: This should be correct, but with the prompt and context, the whisper
        #   model result in recalculation with temperature adjustment.
        # if self._index_first_committed_in_buffer is None and len(commit) != 0:
        #    self._index_first_committed_in_buffer = len(
        #        self._transcriptions_committed)
        self._transcriptions_committed.extend(commit)

        return commit

    def trim(self, start_time_of_buffer: float) -> None:
        if (
            self._last_committed_offset is None
            or self._index_first_committed_in_buffer is None
        ):
            return

        while (
            self._transcriptions_committed[self._index_first_committed_in_buffer].start
            < start_time_of_buffer
        ):
            self._index_first_committed_in_buffer += 1
            if self._index_first_committed_in_buffer >= len(
                self._transcriptions_committed
            ):
                self._last_committed_offset = None
                self._index_first_committed_in_buffer = None
            else:
                self._last_committed_offset = self._transcriptions_committed[
                    self._index_first_committed_in_buffer
                ].end


@dataclass
class TrimmingConfig:
    pass


@dataclass
class SentenceTrimming(TrimmingConfig):
    pass


@dataclass
class TimeTrimming(TrimmingConfig):
    seconds: float


class ASRProcessor:
    @dataclass
    class ProcessorConfig:
        sampling_rate: int
        prompt_size: int
        audio_receiver_timeout: float
        buffer_config: TranscriptionBuffer.Config = field(
            default_factory=lambda: TranscriptionBuffer.Config()
        )
        audio_trimming: TrimmingConfig = field(
            default_factory=lambda: SentenceTrimming()
        )
        language: str | None = None

    def __init__(  # noqa: PLR0913
        self,
        processor_config: ProcessorConfig,
        audio_receiver: AudioReceiver,
        output_senders: OutputSender | list[OutputSender],
        backend: Backend,
        model_config: ASRBase.ModelConfig,
        transcribe_config: ASRBase.TranscribeConfig,
        feature_extractor_config: ASRBase.FeatureExtractorConfig,
    ) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)

        self.processor_config = processor_config
        self.audio_receiver = audio_receiver
        self.output_senders = (
            output_senders if isinstance(output_senders, list) else [output_senders]
        )

        self._audio_buffer = numpy.array([], dtype=numpy.float32)
        self._transcription_buffer = TranscriptionBuffer(
            self.processor_config.buffer_config
        )

        self.buffer_offset = 0

        """
        When SenstenceTrimming and NO language
mosestokenizer/__init__.py", line 87, in __init__
    params.lang_iso = lang
    ^^^^^^^^^^^^^^^
TypeError: (): incompatible function arguments. The following argument types are 
supported:
    1. (self: mosestokenizer.lib._mosestokenizer.MosesTokenizerParameters, arg0: str) 
    -> None

Invoked with: <mosestokenizer.lib._mosestokenizer.MosesTokenizerParameters object at 
0x792f3d9b81f0>, None
        """
        self._tokenizer = (
            MosesTokenizer(self.processor_config.language)
            if isinstance(self.processor_config.audio_trimming, SentenceTrimming)
            else None
        )

        ASRBase.check_support_sampling_rate(
            backend, self.processor_config.sampling_rate
        )

        if backend == Backend.FASTER_WHISPER:
            self.logger.info("Selected Backend: Faster Whisper")

            from .backend import FasterWhisperASR

            self.backend = FasterWhisperASR(
                model_config,
                transcribe_config,
                feature_extractor_config,
                self.processor_config.sampling_rate,
                self.processor_config.language,
            )
        else:
            msg = f"Backend {backend} is not supported"
            raise ValueError(msg)

    def run(self) -> None:
        """Run the processor.

        Returns:
            None
        """
        try:
            for output_sender in self.output_senders:
                output_sender.start()
            self.audio_receiver.start()

            stop = Event()
            while not stop.is_set():
                try:
                    audio = self.audio_receiver.queue.get(
                        timeout=self.processor_config.audio_receiver_timeout,
                    )
                except Empty:
                    self.logger.debug("Audio Receiver timeout")
                    stop.set()
                    output = Word.join(
                        self._transcription_buffer.transcriptions_in_limbo
                    )
                else:
                    output = self._process(audio)

                if output is not None:
                    for output_sender in self.output_senders:
                        output_sender.queue.put_nowait(output)
        except:
            self.logger.exception("Exception in run thrown")
        finally:
            for output_sender in self.output_senders:
                output_sender.close()
            self.audio_receiver.close()

    def _prompt(self) -> tuple[str, str]:
        """Building prompt and context for the audio buffer.

        "Prompt" is a sequence of committed words, that are now outside the audio
        buffer. It is as long, as configured.
        "Context" is the committed text, that is still inside the audio buffer.

        Returns:
            Tuple of prompt and context.

        """
        prompt_candidates = self._transcription_buffer.prompt_candidates
        prompt_length = 0
        prompt: list[str] = []
        for prompt_candidate in prompt_candidates:
            candidate_word = prompt_candidate.word
            if (
                prompt_length + len(candidate_word)
            ) > self.processor_config.prompt_size:
                break

            prompt.append(candidate_word)

        context = [word.word for word in self._transcription_buffer.context]

        return "".join(prompt), "".join(context)

    def _process(self, audio: str | BinaryIO | numpy.ndarray) -> Word | None:
        self._audio_buffer = numpy.append(self._audio_buffer, audio)

        prompt, context = self._prompt()
        self.logger.debug("PROMPT: %s", prompt)
        self.logger.debug("CONTEXT: %s", context)
        self.logger.debug(
            "transcribing %s seconds starting at %s",
            len(self._audio_buffer) / self.processor_config.sampling_rate,
            self.buffer_offset,
        )

        segments, language = self.backend.transcribe(self._audio_buffer, prompt)

        newly_committed_transcript = self._transcription_buffer.insert(
            [
                word.with_offset(self.buffer_offset)
                for word in self.backend.segments_to_words(segments)
            ]
        )
        if len(newly_committed_transcript) > 0:
            self.logger.debug("Complete now: %s", Word.join(newly_committed_transcript))
        if len(self._transcription_buffer.transcriptions_in_limbo) > 0:
            self.logger.debug(
                "Incomplete: %s",
                Word.join(self._transcription_buffer.transcriptions_in_limbo),
            )

        if isinstance(self.processor_config.audio_trimming, SentenceTrimming):
            raise Exception()
        elif isinstance(self.processor_config.audio_trimming, TimeTrimming):
            audio_length = len(self._audio_buffer) / self.processor_config.sampling_rate
            max_seconds_in_buffer = self.processor_config.audio_trimming.seconds
            time_to_trim = int(audio_length - max_seconds_in_buffer)
            if audio_length > max_seconds_in_buffer:
                self._audio_buffer = numpy.delete(
                    self._audio_buffer,
                    range(
                        0,
                        time_to_trim * self.processor_config.sampling_rate,
                    ),
                )
                self.buffer_offset += time_to_trim
                self._transcription_buffer.trim(self.buffer_offset)

        self.logger.debug(
            "New buffer length: %s",
            len(self._audio_buffer) / self.processor_config.sampling_rate,
        )

        return (
            Word.join(newly_committed_transcript)
            if len(newly_committed_transcript) > 0
            else None
        )
