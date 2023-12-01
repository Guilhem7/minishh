"""Entry point for the program"""
from time import sleep
from rich.traceback import install
from http_handler.http_server import HttpServer, HttpDeliveringServer
from req_handler.connection_handler import ConnectionHandler
from utils.pwsh_utils import PwshUtils
from utils.print_utils import Printer
from utils.ipaddr import IpAddr
from config.config import AppConfig, MinishhRequirements
from commands.menu_command import MenuCommand
from prompt_toolkit.formatted_text import ANSI

class Main:
    """
    Main is the class managing the interactive menu
    It has the configuration and some commands about sessions
    """
    def __init__(self):
        super().__init__()
        self._prompt_menu = Printer.format(AppConfig.get("prompt", "Menu")) + " "
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
                )
            )

    def safe_start_server(self, server):
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
        """
        HttpDeliveringServer.init_permanent_route({
          AppConfig.get("amsi_route1", "Routes")         : AppConfig.get('amsi_step1', 'Script'),
          AppConfig.get("amsi_route2", "Routes")         : AppConfig.get('amsi_step2', 'Script')
        })

        # script = "scripts/test.ps1"
        # route_for_script = AppConfig.get_and_set_if_not_exists(script, "random_route.log", "Routes")
        # HttpDeliveringServer.init_permanent_route({
        #     route_for_script : script
        #     })
        # Init the reverse shell script each times it is launched
        self.http_server.prepare_rev_shell_script()
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
    except Exception as e:
        Printer.err(e)
        exit(1)

    menu = Main()
    menu.init_options()
    menu.run()
