import sys
import os
sys.path.append(os.getcwd() + '/..')

from beerery.controller import Controller

ctrl = Controller()
ctrl.control()
