import re
import base64
from utils.pwsh_utils import PwshUtils
from shell_utils.shell_factory import Shells

class SkeletonShell:
    """
    SkeletonShell keep the command of the different shell for identification or other
    """

    IDENTIFICATION_COMMANDS_DICT = {
                                    Shells.Basic      : {"cmd": "PS1='' && ls /etc/passwd", "expect": "/etc/passwd"},
                                    Shells.Powershell : {"cmd": "[System.Environment]::OSVersion.VersionString", "expect": "microsoft windows"},
                                    Shells.Windows    : {"cmd": "VER", "expect": "microsoft windows"}
                                    }

    USEFUL_BINARIES          = {
                                    Shells.Basic      : ["python3", "python", "socat", "bash", "wget", "curl", "stty", "timeout", "xxd", "zip", "tar", "base64"],
                                    Shells.Powershell : ["wget", "curl", "certutil", "xor", "tar"],
                                    Shells.Windows    : ["wget", "curl", "certutil", "tar"]
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
        if shell_type & Shells.Powershell:
            binary_list = '"' + '","'.join(binaries) + '"'
            cmd = 'Do{ foreach($b in ' + binary_list + '){if(Get-Command $b -errorAction SilentlyContinue){echo $b;}} } While($false)'

        elif shell_type & Shells.Basic:
            binary_list = " ".join(binaries)
            cmd = f'sh -c \'for b in {binary_list};do type $b 2>/dev/null;done\''

        elif shell_type & Shells.Windows:
            binary_list = " ".join(binaries)
            cmd = f'echo off & (for %c IN (' + binary_list + f') DO (WHERE %c 2>nul)) & echo on'

        else:
            return None

        return cmd

    @staticmethod
    def recover_shell_type_from_prompt(answer):
        """
        Try to predict the shell in use by looking at the prompt
        ```python
        >>> prompt_ps = "...\n PS C:\\Users\\svc_example\\Desktop > "
        >>> prompt_win = "[Microsoft Windows]\nC:\\Users\\svc_example\\Desktop > "
        >>> prompt_lin = "...$"
        >>>
        >>> SkeletonShell.recover_shell_type_from_prompt(prompt_ps)[0]
        Shells.Powershell

        >>> SkeletonShell.recover_shell_type_from_prompt(prompt_win)[0]
        Shells.Windows
        
        >>> SkeletonShell.recover_shell_type_from_prompt(prompt_lin)[0]
        Shells.Basic

        >>> 
        """
        if re.search(WindowsShellPrompt.PS_PROMPT, answer):
            return [Shells.Powershell, Shells.Windows, Shells.Basic]

        elif re.search(WindowsShellPrompt.WIN_PROMPT, answer):
            return [Shells.Windows, Shells.Powershell, Shells.Basic]

        else:
            return [Shells.Basic, Shells.Windows, Shells.Powershell]


class WindowsShellPrompt:
    PS_PROMPT = re.compile(r"^\s*PS [A-Z]:\\.*>", re.MULTILINE)
    WIN_PROMPT = re.compile(r"^\s*[A-Z]:\\.*>", re.MULTILINE)
