import subprocess
from abc import ABC, abstractmethod
from utils.print_utils import Printer

class AbstractCommand(ABC):
    """
    Command abstract class, allowing to defines the command available in a dictionnary
    """

    @abstractmethod
    def __init__(self):
        self.full_cli = None

    @classmethod
    @property
    @abstractmethod
    def COMMANDS(cls):
        """A dictionnary holding all available commands"""
        raise NotImplementedError("No commands defined")

    @classmethod
    def _get_help_for_command(cls, command):
        """Return the help for the command and its usage"""
        if cls.COMMANDS.get(command) is not None:
            infos = cls.COMMANDS.get(command)
            if "usage" in infos:
                return infos["help"] + "\n\t" + infos["usage"]
            return infos["help"]

        return None

    @abstractmethod
    def print_help_header(self):
        """Show header above the help"""
        raise NotImplementedError("No help header defined")

    @abstractmethod
    def execute_help(self, *args):
        """Function called when typing help <cmd>"""
        raise NotImplementedError("No help method defined")

    @staticmethod
    def parse_command(cmd):
        """
        This functions parses the command as string
        It returns a tuple containing the command and its argument
        """
        if isinstance(cmd, bytes):
            cmd = cmd.decode("utf-8", "ignore")

        cmd = cmd.strip()
        if cmd == "":
            return (None, None)

        splitted_cmd = cmd.split()

        cmd = splitted_cmd[0]
        if len(splitted_cmd) >= 1:
            args = splitted_cmd[1:]
            return (cmd, args)

        return (cmd, None)

    @staticmethod
    def err(cmd):
        Printer.err(f"Function [red]{cmd}[/red] is not known")

    def is_shell_command(self, cmd):
        """
        Check if a command is meant to be run by the underlying shell
        If the command starts with a '!'
        ```bash
        └─$ python3 main.py
        [>] Listening on port: 9000
        [>] Max connections allowed: 5
        [>] Http server started on port 9001
        [Menu] !uname -r
        6.5.0-kali3-amd64
        [Menu]
        ```
        """
        return len(cmd) >= 2  and cmd[0] == '!'

    def handle_input(self, cmd):
        """
        Dispatch the command
          1. Checks if it is a shell command
          2. Checks if a function execute_<cmd> exists
          3. Dispatch the command to the function it exists else to err function
        """
        self.full_cli = cmd
        if self.is_shell_command(cmd):
            subprocess.run(cmd[1:], shell=True, check=False)

        else:
            method, args = self.parse_command(cmd)
            if method is not None:
                self.call(method, *args)

    def call(self, cmd, *args):
        callback_function = getattr(self, f"execute_{cmd}", None)
        if callback_function is None:
            AbstractCommand.err(cmd)

        else:
            callback_function(*args)
