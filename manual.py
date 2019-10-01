"""
Manual controller for an output with a few options
"""


class ManualController(object):
    def __init__(self, **kwargs):
        self.on = kwargs["on"]

    def update_config(self, config):
        self.on = config["on"]

    def compute(self):
        if self.on:
            self.output = 100
        else:
            self.output = 0

        return True
