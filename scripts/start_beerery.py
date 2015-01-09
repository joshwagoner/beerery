import sys
import os
sys.path.append(os.getcwd() + '/..')

print sys.path

from beerery.controller import Controller

ctrl = Controller()
ctrl.control()
