"""Module helping for setting terminal in other mode"""
import termios
import tty
import sys
import os

class Term:
    """
    Class allowing to save the current terminal state
    And allow switching between raw and cooked mode
    """

    INIT_STATE = None

    @classmethod
    def init(cls):
        """Save the initial flags of the terminal"""
        if cls.INIT_STATE is None:
            cls.INIT_STATE = termios.tcgetattr(sys.stdin.fileno())

    @staticmethod
    def start_raw_mode():
        """Set the terminal in raw mode, equivalent to stty raw -echo"""
        tty.setraw(sys.stdin)

    @classmethod
    def reset(cls):
        """Reset the terminal with all the previous flags"""
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, cls.INIT_STATE)

    @staticmethod
    def get_size():
        return os.get_terminal_size()
