"""
programs for running the controllers
"""


class Program(object):

    """
    class representing a program to be run by the controller.
    programs are configured in config/programs.json.
    """

    def __init__(self, program_name):
        self.name = program_name

    def run(self):
        """
        calculate any changes needed based on the time. 
        returns True if an input or output change resulted
        """
        return False

    def start(self):
        """activate the program and start running it"""
