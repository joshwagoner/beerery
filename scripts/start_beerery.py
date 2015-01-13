#!/usr/bin/env python

import sys
import os

# add directories above script directory to path
base_dir = os.path.abspath(os.path.dirname(os.path.realpath(__file__)) + "/..")
sys.path.append(base_dir)
sys.path.append(os.path.abspath(base_dir + "/.."))

from beerery.controller import Controller

ctrl = Controller(base_dir)
ctrl.control()
