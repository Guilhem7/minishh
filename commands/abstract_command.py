import subprocess
from abc import ABC, abstractmethod
from shell_utils.shell_factory import *
from utils.print_utils import Printer
from prompt_toolkit.shortcuts import CompleteStyle, prompt
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit import PromptSession

class AbstractCommand(ABC):
    """
    Command abstract class, allowing to defines the command available in a dictionnary
    """

    @classmethod
    @property
    @abstractmethod
    def COMMANDS(cls):
        raise NotImplementedError

    @classmethod
    def _get_help_for_command(cls, command):
        if cls.COMMANDS.get(command) is not None:
            infos = cls.COMMANDS.get(command)
            if "usage" in infos:
                return infos["help"] + "\n\t" + infos["usage"]
            else:
                return infos["help"]
        return None

    @abstractmethod
    def print_help_header(self):
        pass

    @abstractmethod
    def execute_help(self, *args):
        pass 

    @staticmethod
    def parse_command(cmd):
        if type(cmd) == bytes:
            cmd = cmd.decode("utf-8", "ignore")

        cmd = cmd.strip()
        if cmd == "":
            return (None, None)

        splitted_cmd = cmd.split()

        cmd = splitted_cmd[0]
        if(len(splitted_cmd) >= 1):
            args = splitted_cmd[1:]
            return (cmd, args)

        return (cmd, None)

    @staticmethod
    def err(cmd, *args):
        Printer.err(f"Function [red]{cmd}[/red] is not known")

    def is_shell_command(self, cmd):
        return len(cmd) >= 2  and cmd[0] == '!'

    def handle_input(self, cmd):
        self.full_cli = cmd
        if(self.is_shell_command(cmd)):
            subprocess.run(cmd[1:], shell=True)

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


