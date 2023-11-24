import readline
import fcntl
import sys
import os
from enum import Enum, auto
from utils.print_utils import Printer
from utils.term_manager import Term

class ShellTypes(Enum):
    Basic      = auto()
    Pty        = auto()
    Windows    = auto()
    Powershell = auto()

class OperatingSystem(Enum):
    Linux   = auto()
    Windows = auto()

class Shell:

    @staticmethod
    def init():
        pass

    @staticmethod
    def reset_shell():
        pass

    def handle_special_cmd(self):
        pass
    
    @staticmethod
    def is_stdin_non_blocking():
        flags = fcntl.fcntl(sys.stdin, fcntl.F_GETFL)
        return (flags | os.O_NONBLOCK == flags)

    @staticmethod
    def default_command():
        return []

    @staticmethod
    def help():
        Printer.print("Press [bold][Ctrl+C][/bold] to background the session or exit")

class UnixShell(Shell):
    """UnixShell is an object representing an instance of a shell for Unix-type OS"""
    def __init__(self):
        super().__init__()
        self.os = OperatingSystem.Linux
        self.type = ShellTypes.Basic

    def is_writtable_cmd(self):
        return ('[ -w /dev/shm ] && echo "YEP" || echo "NOPE"', "YEP")

    @staticmethod
    def default_command():
        columns, lines = os.get_terminal_size()
        return [
            "export HISTFILE=/dev/null",
            "export TERM=xterm-256color",
            "alias ll=\"ls -lhas\"",
            "alias c=\"clear\"",
            f"tty && which stty && stty rows {lines} columns {columns}"
        ]

    @staticmethod
    def enumerate_binary_command(binaries):
        """
        This functions return the command to enumerate binaries on a target,
        however if the binary is present it must be returned in the response
        """
        binary_list = " ".join(binaries)
        cmd = f'sh -c \'for b in {binary_list};do which $b 2>/dev/null;done\''
        return cmd

class WindowsShell(Shell):
    """WindowsShell is an object representing an instance of a shell for Windows OS"""
    def __init__(self):
        super().__init__()
        self.os = OperatingSystem.Windows
        self.type = ShellTypes.Powershell

    def get_input(self):
        cmd = input().encode()
        if(cmd == b"exit"):
            raise KeyboardInterrupt("Background session requested")
        return cmd + b"\n"


class BasicShell(UnixShell):
    """BasicShell handler for unix system"""
    def __init__(self):
        super().__init__()

    def __str__(self):
        return "Unix shell"

    def get_input(self):
        return input().encode() + b"\n"

class Powershell(WindowsShell):
    def __init__(self):
        super().__init__()

    def __str__(self):
        return "Powershell"

    def get_temp_dir(self):
        return "$env:Temp"

    def command_exists(self, cmd):
        return ('if(Get-Command ' + cmd + ' -errorAction SilentlyContinue){echo "Yes"}', "Yes")

    @staticmethod
    def enumerate_binary_command(binaries):
        """
        This functions return the command to enumerate binaries on a target,
        however if the binary is present it must be returned in the response
        """
        binary_list = '"' + '","'.join(binaries) + '"'
        cmd = 'Do{ foreach($b in ' + binary_list + '){if(Get-Command $b -errorAction SilentlyContinue){echo $b;}} } While($false)'
        return cmd

    @staticmethod
    def default_command():
        return [
        'function xor($a, $b){$c="";for($i=0;$i -lt $a.Length;$i++){$c += [char]($a[$i] -bxor $b[$i%$b.Length])}return $c;}',
        'function download($file){if(Test-Path "$file"){$bytes = [System.IO.File]::ReadAllBytes("$file");echo ([System.BitConverter]::ToString($bytes)).Replace("-","");}}'
        ]

class Pty(Shell):
    """Class responsible for Pty shell"""

    BACKGROUND_CHAR = ("CTRL+B", b"\x02")

    def __init__(self, previous_shell=None):
        super().__init__()
        self.history = b""
        self.last_command = b""
        self.previous_shell = previous_shell

    @staticmethod
    def init():
        # super().init()
        Term.init()
        Term.start_raw_mode()

    @staticmethod
    def reset_shell():
        # super().reset_shell()
        Term.reset()

    def handle_special_cmd(self, cmd):
        """
        If the cmd pressed is CTRL+Z (\x1a) then we background the connection
        Escape is \x1b but all key pree like key up start with escape sequence...
        CTRL+A ==> \x01
        """
        if(cmd == Pty.BACKGROUND_CHAR[1]):
            raise KeyboardInterrupt("Background session requested")

    def get_input(self):
        # cmd = sys.stdin.read(1).encode() # Line buffering prevent correct usage on raw tty windows
        cmd = os.read(sys.stdin.fileno(), 4)
        self.handle_special_cmd(cmd)
        return cmd

    @classmethod
    def help(cls):
        Printer.print(f"Press [bold][{cls.BACKGROUND_CHAR[0]}][/bold] to background the session or exit")


class PtyShell(UnixShell, Pty):

    def __init__(self):
        UnixShell.__init__(self)
        Pty.__init__(self)
        self.type = ShellTypes.Pty

    def __str__(self):
        return "Pseudo TTY shell"


class ShellFactory:

    Shells = {
        ShellTypes.Basic      : BasicShell,
        ShellTypes.Pty        : PtyShell,
        ShellTypes.Powershell : Powershell,
        ShellTypes.Windows    : WindowsShell,
        }

    @staticmethod
    def build(shell_type):
        return ShellFactory.Shells[shell_type]()
