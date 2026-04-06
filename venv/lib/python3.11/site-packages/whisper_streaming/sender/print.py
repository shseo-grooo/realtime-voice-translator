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

"""Output Sender: Print."""

from whisper_streaming import OutputSender, Word

__all__ = ["PrintSender"]


class PrintSender(OutputSender):
    """Class simply printing the output."""

    def _do_output(self, data: Word) -> None:
        """Printing the output.

        Args:
            data: Output of STT.

        Returns:
            None
        """
        print(data.word)  # noqa: T201

    def _do_close(self) -> None:
        pass
