# -*- coding=UTF-8 -*-
"""Translators.  """

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import logging
import re

from .codectools import get_unicode as u
from .mixin import UnicodeTrMixin

LOGGER = logging.getLogger(__name__)


class ConsoleTranslator(UnicodeTrMixin):
    """Translate for render output.  """

    _cached_patterns = None

    @property
    def patterns(self):
        """Translate patterns.  """

        if not ConsoleTranslator._cached_patterns:
            ConsoleTranslator._cached_patterns = self._patterns()
        return ConsoleTranslator._cached_patterns

    def _patterns(self):
        return {k: v for k, v in
                {"(.+?: )Error reading LUT file\\. (.+?: )unable to open file\\.": self.tr(
                    "\\1Error reading LUT file\\. \\2unable to open file\\."),
                 ("(.+?: )Error reading pixel data from image file (\".*\")\\. "
                  "Early end of file: read (.+?) out of (.+?) requested bytes."): self.tr(
                      "\\1Error reading pixel data from image file \\2\\. "
                      "Early end of file: read \\3 out of \\4 requested bytes."),
                 ("(.+?: )Error reading pixel data from image file (\".*\")\\. "
                  "Scan line (.+?) is missing\\."): self.tr(
                      "\\1Error reading pixel data from image file \\2\\. "
                      "Scan line \\3 is missing\\."),
                 "Missing input channel": self.tr(
                     "Missing input channel"),
                 "Read error: No such file or directory": self.tr(
                     "Read error: No such file or directory"),
                 "There are no active Write operators in this script": self.tr(
                     "There are no active Write operators in this script"),
                 "Can't read (.+?): Permission denied": self.tr(
                     "Can't read \\1: Permission denied"),
                 "Can't read (.+?): No such file or directory": self.tr(
                     "Can't read \\1: No such file or directory"),
                 "\\[.*?\\] ERROR: (.+)":
                 "\\1",
                 "Writing (.+?) took (.+?) seconds": self.tr(
                     "Writing <a href=\"\\1\">\\1</a> took \\2 seconds"),
                 "Frame": self.tr(
                     "Frame"),
                 "All Rights Reserved": self.tr(
                     "All Rights Reserved"), }.items()}

    @staticmethod
    def translate(text):
        """Translate the text.  """

        if not isinstance(text, (str, unicode)):
            LOGGER.warning('Try localization non-str: %s', text)
            return text
        ret = u(text).strip('\r\n')

        for k, v in ConsoleTranslator().patterns.items():
            try:
                ret = re.sub(k, v, ret)
            except TypeError as ex:
                LOGGER.debug(
                    'Translate fail: re.sub(%s, %s, %s)\n %s', k, v, ret, ex)
        return ret
