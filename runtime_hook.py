"""Pyinstaller runtime hook.  """

import os
import sys

import pytzdata

pytzdata.set_directory(os.path.join(getattr(sys, '_MEIPASS', ''), 'zoneinfo'))
