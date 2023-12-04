from commands.abstract_command import AbstractCommand
from utils.minishh_utils import MinishhUtils
from utils.pwsh_utils import PwshUtils, ObfUtil
from utils.print_utils import Printer
from config.config import AppConfig
from http_handler.http_server import HttpDeliveringServer
from prompt_toolkit.shortcuts import CompleteStyle
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit import PromptSession
from commands.toolbar import MinishToolbar
from utils.generator.payload_generator import Generator

class MenuCommand(AbstractCommand):
    """
    Handler for menu command
    """

    COMMANDS = {
            "help"     : {"help": "Show this help, or the help for a command",
                            "usage": "Usage: help ?<[bold yellow]command[/bold yellow]>"},
            "generate" : {"help": "Generate a reverse shell payload", "usage": "Use [yellow]generate -h[/yellow] to see more information on this command"},
            "list"     : {"help": "List the current sessions available"},
            "servers"  : {"help": "Print the running servers"},
            "sess"     : {"help": "Interact with a session",
                            "usage": "Usage: sess <[bold blue]number[/bold blue]>"},
            "set"      : {"help": "Set a key to a value",
                            "usage": "set <[bold blue]key[/bold blue]> <[bold yellow]val[/bold yellow]>\nKeys available: ip"},
            "exit"     : {"help": "Exit the program"}
        }

    KEYS_UPGRADABLE = {"ip":"default_ip_address"}

    def __init__(self, main_menu):
        """Init this class with a direct link to the main menu class"""
        self.main_menu = main_menu
        self.full_cli = None
        self.generator = Generator()
        self.init_session()

    def init_session(self):
        self.session = PromptSession(completer=WordCompleter(list(MenuCommand.COMMANDS.keys())),
                                     complete_style=CompleteStyle.MULTI_COLUMN,
                                     bottom_toolbar=MinishToolbar.get_toolbar,
                                     refresh_interval=MinishToolbar.refresh_interval)

    def print_help_header(self):
        Printer.print("========== [blue]Menu [bold]Commands[/blue][/bold] ==========")

    def execute_help(self, *args):
        self.print_help_header()
        if(len(args) >= 1):
            usage = MenuCommand._get_help_for_command(args[0])
            if(usage is not None):
                Printer.print(usage)
            else:
                Printer.err("No such function")

        else:
            for cmd, info in self.COMMANDS.items():
                Printer.print(f" - [dodger_blue1]{cmd:<12}[/dodger_blue1]\t" + info['help'])
        print()

    def execute_sess(self, *sess_number):
        if(len(sess_number) == 0):
            Printer.err("Invalid usage for this command")

        else:
            if(sess_number[0].isdigit()):
                sess = self.main_menu.socket_server.get_session(int(sess_number[0]))
                if sess is not None:
                    sess.run()

            else:
                Printer.err("An integer is required")

    def execute_list(self, *args):
        all_sessions = list(self.main_menu.socket_server.get_active_sessions().values())
        Printer.print("Current [bold]sessions:[/bold]")
        for i in range(len(all_sessions)):
            Printer.pad().print(f" - {i} --> {all_sessions[i]} ({all_sessions[i].session_assets.current_user})")

    def execute_servers(self, *args):
        Printer.log("Current [blue]servers[/blue]:")
        Printer.pad().log(self.main_menu.socket_server)
        Printer.pad().log(self.main_menu.http_server)

    def execute_set(self, *values):
        if len(values) == 2:
            set_key, set_val = values
            if MenuCommand.KEYS_UPGRADABLE.get(set_key) is None:
                Printer.err(f"{set_key} is not known")

            else:
                target_key = MenuCommand.KEYS_UPGRADABLE.get(set_key)
                AppConfig.set_extra_var(target_key, set_val, section="UserSection", force=True)
                Printer.log(f"[blue]{target_key}[/blue] is now set to [yellow]{set_val}[/yellow]")

        else:
            Printer.err("Missing arguments for set function")

    def execute_generate(self, *args):
        """Generate a payload, see utils/generator/__init__.py for more details"""
        payload = ""

        try:
            inline_payload = self.generator.generate_payload(self.full_cli,
                ip=AppConfig.get('default_ip_address'),
                port=AppConfig.get('listening_port', 'Connections'))

            if inline_payload != "":
                if self.generator.get_parser_val("output") == 'infile':
                    section_target = AppConfig.translate_target_to_section(self.generator.get_parser_val("target").lower())
                    # At this time, we requested an infile generated payload
                    # Check if on_before_shell is set for the target (not usable with linux by now)
                    script_content = []
                    scripts = MinishhUtils.recover_scripts("on_before_shell", section_target)
                    script_dest = MinishhUtils.recover_scripts("reverse_shell_script", section_target)[0]
                    scripts.append(script_dest)
                    for script in scripts:
                        route = HttpDeliveringServer.get_route_for_script(script)
                        script_content.append(
                                self.generator.get_remote_payload_for_type(section_target,
                                        AppConfig.get('port', 'HttpServer'),
                                            route)
                                )

                    script_dest_all = MinishhUtils.recover_scripts("all_in_one_script", section_target)[0]
                    if script_dest != "" and script_dest_all != "":
                        with open(script_dest, "w") as rev_shell_script, open(script_dest_all, "w") as all_payload:
                            rev_shell_script.write(self.generator.get_payload_for_type(section_target, self.generator.get_parser_val("tpl")))
                            all_payload.write("\n".join(script_content))

                    else:
                        Printer.err("[red]Config value missing[/red] 'reverse_shell_script' in section {}".format(section_target))

                    download_payload = self.generator.generate_payload(self.full_cli,
                        ip=AppConfig.get('default_ip_address'),
                        port=AppConfig.get('port', 'HttpServer'),
                        route=HttpDeliveringServer.get_route_for_script(script_dest_all))

                    Printer.print(download_payload)
                    MinishhUtils.copy(download_payload)

                else:
                    Printer.print(inline_payload)
                    MinishhUtils.copy(inline_payload)

        except Exception as e:
            Printer.err(e)
