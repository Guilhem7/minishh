import readline
import fcntl
import sys
import os
from abc import ABC
from enum import Enum, IntEnum, auto
from config.config import AppConfig
from utils.term_manager import Term
from utils.print_utils import Printer
from prompt_toolkit import PromptSession, ANSI
from prompt_toolkit.patch_stdout import patch_stdout

PTY = 1

BASIC = 2
Powershell = 4
Windows = 8

class Shells(IntEnum):
    Pty = 1
    Basic = 2
    Powershell = 4
    Windows = 8
    All = 2 | 4 | 8

class ShellTypes(Enum):
    Basic      = auto()
    Pty        = auto()
    Windows    = auto()
    Powershell = auto()

class InputHandler(ABC):
    """
    An Input Handler Interface
    """
    @staticmethod
    def init():
        """
        Init shell attributes
        """
        pass

    @staticmethod
    def reset_shell():
        """
        Reset shell attributes
        """
        pass

    def handle_special_cmd(self):
        pass

    def get_input(self):
        """
        Recover the input from the user
        """
        pass

class SimplePromptInput(InputHandler):
    """
    Simple prompt session
    """
    def __init__(self):
        self.prompt_session = PromptSession()
        self.prompt_line = ANSI(Printer.format(AppConfig.get("prompt",
                                                             "Local",
                                                             "[orange1]Minishh[/]@[b]user$[/b] ")))

    def get_input(self):
        """
        Recover the input of the user
        """
        with patch_stdout(raw=True):
            result = self.prompt_session.prompt(self.prompt_line)
            return result.encode() + b"\n"

    def help(self):
        Printer.print("Press [bold][Ctrl+C][/bold] to background the session or exit")

class PtyInput(InputHandler):
    """
    Input handler for pty
    """
    BACKGROUND_CHAR = ("CTRL+B", b"\x02")

    @staticmethod
    def init():
        Term.init()
        Term.start_raw_mode()

    @staticmethod
    def reset_shell():
        Term.reset()

    def handle_special_cmd(self, cmd):
        """
        If the cmd is the special char, then we background the session
        """
        if(cmd == self.BACKGROUND_CHAR[1]):
            raise KeyboardInterrupt("Background session requested")

    def get_input(self):
        """
        Recover the input
        """
        cmd = os.read(sys.stdin.fileno(), 4)
        self.handle_special_cmd(cmd)
        return cmd

    @classmethod
    def help(cls):
        Printer.print(f"Press [bold][{cls.BACKGROUND_CHAR[0]}][/bold] to background the session or exit")

class ShellHandler(ABC):
    """
    Class acting as the shell
    """
    @staticmethod
    def get_prompt_command():
        """
        Recover the command used to set the prompt
        """
        pass

    def default_command(self):
        """
        Return a List of the default commands to run
        when getting this shell
        """
        pass

    @staticmethod
    def help():
        """
        Show the help, basically this tell the
        user how to background the session
        """
        pass

    def get_type(self):
        """
        Return the informations needed for identifying the shell
        """
        if self.is_tty:
            return self.shell_type | Shells.Pty
        return self.shell_type

    @property
    def is_tty(self):
        """
        Check if the shell is a tty or not
        """
        return isinstance(self.input_handler, PtyInput)

    def reset_prompt(self):
        """
        Reset the prompt in use
        """
        pass

    def set_tty(self):
        """
        Set the shell to tty
        """
        self.input_handler = PtyInput()

    def reset_tty(self):
        """
        Reset the shell to non tty
        """
        self.input_handler = SimplePromptInput()

    def get_input(self):
        """
        Recover the user input
        """
        return self.input_handler.get_input()

    def init(self):
        self.input_handler.init()

    def reset_shell(self):
        self.input_handler.reset_shell()

class Unix(ShellHandler):
    """
    Shell used for unix-like connections
    """
    def __init__(self, handler=None):
        self.input_handler = handler if handler else SimplePromptInput()
        self.os = "Linux"
        self.shell_type = Shells.Basic

    @staticmethod
    def get_prompt_command():
        """
        Recover the command used to set the prompt
        """
        prompt = AppConfig.get("prompt", "Linux")
        if prompt:
            # Tell bash 0-length chars
            prompt = prompt.replace("[", "\\\[[").replace("]", "]\\\]").replace("\\n", "\n")

            prompt = Printer.format(prompt)
            if "\x1b" in prompt:
                prompt = prompt.replace("\x1b", '\\e')
            return f"export PS1=\"{prompt} \""
        return ""

    def reset_prompt(self):
        """
        Return the command for resetting the prompt
        """
        return "unset PS1"

    def default_command(self):
        default_commands = [
            " export HISTFILE=/dev/null",
            "export TERM=xterm-256color",
            "alias ls='ls --color=always'",
            "alias ll=\"ls -lhas\"",
            "alias c=\"clear\""
        ]
        if self.is_tty:
            prompt_command = Unix.get_prompt_command()
            if prompt_command:
                default_commands.append(prompt_command)

            columns, lines = os.get_terminal_size()
            default_commands.append(f"type stty && stty rows {lines} columns {columns}")

        else:
            default_commands.append(self.reset_prompt())

        return default_commands

class Powershell(ShellHandler):
    """
    Shell used for unix-like connections
    """
    def __init__(self, handler=None):
        self.input_handler = handler if handler else SimplePromptInput()
        self.os = "Windows"
        self.shell_type = Shells.Powershell

    @staticmethod
    def get_prompt_command():
        """
        Recover the command used to set the prompt
        """
        prompt = AppConfig.get("prompt", "Powershell")
        if prompt:
            prompt = prompt.replace("\\n", "\n")
            return f"function prompt(){{\"{prompt} \";}}"
        return ""

    def reset_prompt(self):
        """
        Return the command for resetting the prompt
        """
        return "function prompt(){}"

    def default_command(self):
        default_commands = [
            'function xor($a, $b){$c="";for($i=0;$i -lt $a.Length;$i++){$c += [char]($a[$i] -bxor $b[$i%$b.Length])}return $c;}',
        ]
        if self.is_tty:
            prompt_command = Powershell.get_prompt_command()
            if prompt_command:
                default_commands.append(prompt_command)

        else:
            default_commands.append(self.reset_prompt())

        return default_commands

class Windows(ShellHandler):
    """
    Shell used for unix-like connections
    """
    def __init__(self, handler=None):
        self.input_handler = handler if handler else SimplePromptInput()
        self.os = "Windows"
        self.shell_type = Shells.Windows

    def reset_prompt(self):
        """
        Return the command for resetting the prompt
        """
        return "echo off"

    def default_command(self):
        return []

# class Shell:
#     """
#     The default shell interface
#     """
#     @staticmethod
#     def init():
#         pass

#     @staticmethod
#     def reset_shell():
#         pass

#     def handle_special_cmd(self):
#         pass

#     @staticmethod
#     def is_stdin_non_blocking():
#         flags = fcntl.fcntl(sys.stdin, fcntl.F_GETFL)
#         return (flags | os.O_NONBLOCK == flags)

#     @staticmethod
#     def default_command():
#         """
#         Return the default command to run on the target
#         """
#         return []

#     @staticmethod
#     def get_prompt_command(prompt):
#         """
#         Return the command to set the prompt
        
#         :param prompt: The prompt value to set
#         """
#         return ""

#     @staticmethod
#     def help():
#         Printer.print("Press [bold][Ctrl+C][/bold] to background the session or exit")

# class UnixShell(Shell):
#     """UnixShell is an object representing an instance of a shell for Unix-type OS"""
#     def __init__(self):
#         super().__init__()
#         self.os = "linux"
#         self.type = ShellTypes.Basic

#     def is_writtable_cmd(self):
#         return ('[ -w /dev/shm ] && echo "YEP" || echo "NOPE"', "YEP")

#     @staticmethod
#     def get_prompt_command(prompt):
#         # if "'" in prompt:
#         #     Printer.vlog("The prompt config contains unwanted char: (')")

#         # Tell bash 0-length chars
#         prompt = prompt.replace("[", "\\\[[").replace("]", "]\\\]").replace("\\n", "\n")

#         prompt = Printer.format(prompt)
#         if "\x1b" in prompt:
#             prompt = prompt.replace("\x1b", '\\e')
#         return f"export PS1=\"{prompt} \""

#     @staticmethod
#     def default_command():
#         default_commands = [
#             " export HISTFILE=/dev/null",
#             "export TERM=xterm-256color",
#             "alias ls='ls --color=always'",
#             "alias ll=\"ls -lhas\"",
#             "alias c=\"clear\""
#         ]

#         return default_commands

#     @staticmethod
#     def enumerate_binary_command(binaries):
#         """
#         This functions return the command to enumerate binaries on a target,
#         however if the binary is present it must be returned in the response
#         """
#         binary_list = " ".join(binaries)
#         cmd = f'sh -c \'for b in {binary_list};do type $b 2>/dev/null;done\''
#         return cmd

# class WindowsShell(Shell):
#     """WindowsShell is an object representing an instance of a shell for Windows OS"""
#     def __init__(self):
#         super().__init__()
#         self.os = "windows"
#         self.type = ShellTypes.Powershell

#     def get_input(self):
#         cmd = input().encode()
#         if(cmd == b"exit"):
#             raise KeyboardInterrupt("Background session requested")
#         return cmd + b"\n"

# class BasicShell(UnixShell):
#     """BasicShell handler for unix system"""
#     def __init__(self):
#         super().__init__()

#     def __str__(self):
#         return "Unix shell"

#     def get_input(self):
#         return input().encode() + b"\n"

# class Powershell(WindowsShell):
#     def __init__(self):
#         super().__init__()

#     def __str__(self):
#         return "Powershell"

#     def get_temp_dir(self):
#         return "$env:Temp"

#     def command_exists(self, cmd):
#         return ('if(Get-Command ' + cmd + ' -errorAction SilentlyContinue){echo "Yes"}', "Yes")

#     @staticmethod
#     def get_prompt_command(prompt):
#         prompt = prompt.replace("\\n", "\n")
#         return f"function prompt(){{\"{prompt} \"}}"

#     @staticmethod
#     def enumerate_binary_command(binaries):
#         """
#         This functions return the command to enumerate binaries on a target,
#         however if the binary is present it must be returned in the response
#         """
#         binary_list = '"' + '","'.join(binaries) + '"'
#         cmd = 'Do{ foreach($b in ' + binary_list + '){if(Get-Command $b -errorAction SilentlyContinue){echo $b;}} } While($false)'
#         return cmd

#     @staticmethod
#     def _default_command():
#         return [
#         'function xor($a, $b){$c="";for($i=0;$i -lt $a.Length;$i++){$c += [char]($a[$i] -bxor $b[$i%$b.Length])}return $c;}',
#         ]

#     @classmethod
#     def default_command(cls):
#         default_commands = cls._default_command()
#         prompt = AppConfig.get("prompt", "Powershell")
#         if prompt:
#             set_ps1 = Powershell.get_prompt_command(prompt)
#             default_commands.append(set_ps1)
#         return default_commands

# class Pty(Shell):
#     """Class responsible for Pty shell"""

#     BACKGROUND_CHAR = ("CTRL+B", b"\x02")

#     def __init__(self, previous_shell=None):
#         super().__init__()
#         self.history = b""
#         self.last_command = b""
#         self.previous_shell = previous_shell

#     @staticmethod
#     def init():
#         # super().init()
#         Term.init()
#         Term.start_raw_mode()

#     @staticmethod
#     def reset_shell():
#         # super().reset_shell()
#         Term.reset()

#     @property
#     def os(self):
#         """Return the Operating System associated to the shell"""
#         return self.previous_shell.os

#     @os.setter
#     def os(self, val):
#         self.previous_shell.os = val

#     def handle_special_cmd(self, cmd):
#         """
#         If the cmd pressed is CTRL+Z (\x1a) then we background the connection
#         Escape is \x1b but all key pree like key up start with escape sequence...
#         CTRL+A ==> \x01
#         """
#         if(cmd == Pty.BACKGROUND_CHAR[1]):
#             raise KeyboardInterrupt("Background session requested")

#     def get_input(self):
#         # cmd = sys.stdin.read(1).encode() # Line buffering prevent correct usage on raw tty windows
#         cmd = os.read(sys.stdin.fileno(), 4)
#         self.handle_special_cmd(cmd)
#         return cmd

#     @classmethod
#     def help(cls):
#         Printer.print(f"Press [bold][{cls.BACKGROUND_CHAR[0]}][/bold] to background the session or exit")

# class UnixPty(UnixShell, Pty):
#     """
#     Pty for unix shell
#     """
#     def __init__(self):
#         Pty.__init__(self)
#         self.type = ShellTypes.Pty

# class PowershellPty(Powershell, Pty):
#     """
#     Pty for windows shell
#     """
#     def __init__(self):
#         Pty.__init__(self)
#         self.type = ShellTypes.Pty

# class PtyShell(UnixShell, Pty):
#     """
#     Pty for unix-like shell
#     """
#     def __init__(self):
#         # UnixShell.__init__(self)
#         Pty.__init__(self)
#         self.type = ShellTypes.Pty

#     @staticmethod
#     def default_command():
#         columns, lines = os.get_terminal_size()
#         default_commands = [
#             " export HISTFILE=/dev/null",
#             "export TERM=xterm-256color",
#             "alias ls='ls --color=always'",
#             "alias ll=\"ls -lhas\"",
#             "alias c=\"clear\"",
#             f"tty && type stty && stty rows {lines} columns {columns}"
#         ]

#         unix_prompt = AppConfig.get("prompt", "Linux")
#         if unix_prompt:
#             set_ps1 = UnixShell.get_prompt_command(unix_prompt)
#             default_commands.append(set_ps1)
#         return default_commands

#     def __str__(self):
#         return "Pseudo TTY shell"

class ShellFactory:

    # Shells = {
    #     ShellTypes.Basic      : BasicShell,
    #     ShellTypes.Pty        : PtyShell,
    #     ShellTypes.Powershell : Powershell,
    #     ShellTypes.Windows    : WindowsShell,
    #     }
    Shells = {
        Shells.Basic      : Unix,
        Shells.Powershell : Powershell,
        Shells.Windows    : Windows,
        }

    @classmethod
    def build(cls, shell_type, tty=False):
        if tty:
            return cls.Shells[shell_type](PtyInput())
        return cls.Shells[shell_type]()
