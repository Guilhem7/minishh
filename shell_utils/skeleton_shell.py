import re
import base64
from utils.pwsh_utils import PwshUtils
from shell_utils.shell_factory import ShellTypes

class SkeletonShell:
    """
    SkeletonShell keep the command of the different shell for identification or other
    """

    IDENTIFICATION_COMMANDS_DICT = {
                                    ShellTypes.Basic      : {"cmd": "PS1='' && ls /etc/passwd", "expect": "/etc/passwd"},
                                    ShellTypes.Powershell : {"cmd": "[System.Environment]::OSVersion.VersionString", "expect": "microsoft windows"},
                                    ShellTypes.Windows    : {"cmd": "VER", "expect": "microsoft windows"}
                                    }

    USEFUL_BINARIES          = {
                                    ShellTypes.Basic      : ["python3", "python", "socat", "bash", "wget", "curl", "stty", "timeout", "xxd", "zip", "tar", "base64"],
                                    ShellTypes.Powershell : ["wget", "curl", "certutil", "xor", "tar", "download"],
                                    ShellTypes.Windows    : ["wget", "curl", "certutil", "tar"]
                                }

    DUMMY_COMMAND = "echo 1337"

    @staticmethod
    def get_command_for_identify_shell(shell_type):
        return SkeletonShell.IDENTIFICATION_COMMANDS_DICT[shell_type]["cmd"]

    @staticmethod
    def expected_answer(shell_type):
        return SkeletonShell.IDENTIFICATION_COMMANDS_DICT[shell_type]["expect"]

    @staticmethod
    def get_useful_binaries(shell_type):
        return SkeletonShell.USEFUL_BINARIES[shell_type]

    @staticmethod
    def enumerate_binary_command(shell_type):
        binaries = SkeletonShell.USEFUL_BINARIES.get(shell_type)
        cmd = ""
        if(shell_type is ShellTypes.Powershell):
            binary_list = '"' + '","'.join(binaries) + '"'
            cmd = 'Do{ foreach($b in ' + binary_list + '){if(Get-Command $b -errorAction SilentlyContinue){echo $b;}} } While($false)'

        elif(shell_type is ShellTypes.Basic):
            binary_list = " ".join(binaries)
            cmd = f'sh -c \'for b in {binary_list};do which $b 2>/dev/null;done\''

        elif(shell_type is ShellTypes.Windows):
            binary_list = " ".join(binaries)
            cmd = f'echo off & (for %c IN (' + binary_list + f') DO (WHERE %c 2>nul)) & echo on'

        else:
            return None

        return cmd

    @staticmethod
    def recover_shell_type_from_prompt(answer):
        if(re.match(WindowsShellPrompt.PS_PROMPT, answer)):
            return [ShellTypes.Powershell, ShellTypes.Windows, ShellTypes.Basic]

        elif(re.match(WindowsShellPrompt.WIN_PROMPT, answer)):
            return [ShellTypes.Windows, ShellTypes.Powershell, ShellTypes.Basic]

        else:
            return [ShellTypes.Basic, ShellTypes.Windows, ShellTypes.Powershell]


class WindowsShellPrompt:
    PS_PROMPT = re.compile(r"PS [A-Z]:\\.*>")
    WIN_PROMPT = re.compile(r"[A-Z]:\\.*>")
