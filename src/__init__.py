# For relative imports to work in Python 3.6 with the poetry script entrypoint
import os
import sys

sys.path.append(os.path.dirname(os.path.realpath(__file__)))
