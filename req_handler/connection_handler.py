import readline
import socket
import select
import sys
import os
from req_handler.connection_proxy import ConnectionProxy
from threading import Thread, Event, Lock
from utils.print_utils import Printer
from config.config import AppConfig
from req_handler.sessions import *
from req_handler.proxy_forwarder import ProxyForwarder

BUFF_SIZE = 2048

class SessionObserver:
    def __init__(self):
        self.connections = {}
        self.potential_connections = {}
        self.http_session = []
        self.readable_list = []
        self.download_server = None

    def add_in_readable(self, obj):
        self.readable_list.append(obj)

    def set_download_server(self, download_server):
        self.download_server = download_server

    def add_potential_connection(self, session):
        """When adding a new connection, we want this socket to be read"""
        self.potential_connections[session.get_connection()] = session
        self.add_in_readable(session.get_connection())

    def add_connection(self, session):
        self.connections[session.get_connection()] = session
        self.add_in_readable(session.get_connection())

    def get_connection(self, sock):
        conn = self.connections.get(sock)
        if conn is None:
            conn = self.potential_connections.get(sock)
        return conn

    def remove_from_readable(self, val):
        if val in self.readable_list:
            self.readable_list.remove(val)

    def remove_connection(self, sock, with_exit=True):
        self.remove_from_readable(sock)
        if self.connections.get(sock) is not None:
            self.connections[sock].close(with_exit)
            del self.connections[sock]

    def empty_readable(self):
        self.readable_list = []

    def get_session(self, index):
        if len(self.connections) > index:
            return list(self.connections.values())[index]
        else:
            Printer.err("No such session available...")

    def notify(self, session):
        """
        Notify handle the set up of a session once it has been analysed
        """
        if session.status == SessionStatus.Initialized:
            Printer.log("Session seems valid, adding it")
            self.connections[session.get_connection()] = session.build()
            self.connections[session.get_connection()].attach(self) # Attaching to observer
            self.connections[session.get_connection()].set_download_server(self.download_server)
            self.connections[session.get_connection()].run_config_script()

            del self.potential_connections[session.get_connection()]

        else:
            Printer.err("Session not valid, discarding")

            session.get_connection().setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, b'\x01\x00\x00\x00\x00\x00\x00\x00') # Send a RST if the connection is invalid
            session.close()
            self.remove_from_readable(session.get_connection())
            del self.potential_connections[session.get_connection()]

    def notify_close(self, valid_session):
        Printer.log(f"User requested closing of session: {valid_session}")
        self.remove_connection(valid_session.get_connection())

class ConnectionHandler(Thread):
    """ConnectionHandler is a class handling multiple session (TCP connection)"""
    TIMEOUT = 2
    is_listening = False

    def __init__(self):
        super().__init__(name="ConnectionHandlerThread")
        self.port = int(AppConfig.get("listening_port", "Connections"))
        self.max_conn = int(AppConfig.get("maximum_client", "Connections"))
        self.s = socket.socket()
        self.state_conn_lock = Lock()
        self.ProxyCo = ConnectionProxy()
        self._observer = SessionObserver()
        self._forwarder = ProxyForwarder(("127.0.0.1", int(AppConfig.get("port", "HttpServer"))),
                                         buff_size=8192)
        self.has_started = Event()

    def __str__(self):
        return f"ConnectionHandler(port={self.port}, max_connections={self.max_conn})"

    def set_download_server(self, download_server):
        self._observer.set_download_server(download_server)

    def get_connection(self, sock):
        return self._observer.get_connection(sock)

    def get_active_sessions(self):
        return self._observer.connections

    def remove_connection(self, sock, with_exit=True):
        self._observer.remove_connection(sock, with_exit=True)

    def remove_from_readable(self, val):
        self._observer.remove_from_readable(val)

    def add_in_readable(self, val):
        self._observer.add_in_readable(val)
    
    def get_session(self, index):
        return self._observer.get_session(index)

    def get_readable_list(self):
        return self._observer.readable_list

    def start_listening(self):
        try:
            # Allow to reuse Addr and Port
            self.s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)

            self.s.bind(('0.0.0.0', self.port))
            self.s.listen(self.max_conn)

            self.add_in_readable(self.s)

            Printer.log("Listening on port: {}".format(self.port))
            Printer.log("Max connections allowed: {}".format(self.max_conn))
            ConnectionHandler.is_listening = True
            self.has_started.set()
            return True

        except Exception as e:
            self.has_started.set()
            Printer.err(e)
            return False

    def run(self):
        if(ConnectionHandler.is_listening):
            return False

        if not(self.start_listening()):
            return False

        while self.get_readable_list():
            read_list, write_list, except_list = select.select(self.get_readable_list(), [], [], ConnectionHandler.TIMEOUT)

            with self.state_conn_lock:
                if not(ConnectionHandler.is_listening):
                    break

            for sock_fd in read_list:
                self.handle_read(sock_fd)

            for sock_fd in write_list:
                self.handle_write(sock_fd)

        try:
            self.s.shutdown(socket.SHUT_RDWR)
        except Exception:
            pass

        self._observer.empty_readable()
        self.s.close()

    def handle_read(self, sock_fd):
        if sock_fd is self.s:
            conn, addr = sock_fd.accept()

            if self._forwarder.isHttp(conn):
                Printer.vlog("[b green]\[HTTP][/b green] trafic found in socket")
                self._forwarder.forward(conn)

            else:
                potential_session = SessionInit(conn)
                self._observer.add_potential_connection(potential_session)

                potential_session.attach(self._observer)
                potential_session.start()

        elif sock_fd in self._observer.readable_list:
            try:
                session = self.get_connection(sock_fd)
                data = sock_fd.recv(BUFF_SIZE)
                if data:
                    self.ProxyCo.add_msg(session, data)

                else:
                    Printer.crlf().err(f"Connection lost from [red]{sock_fd.getpeername()[0]}[/red]")
                    self.remove_connection(sock_fd, with_exit=False)

            except ConnectionResetError:
                Printer.crlf().log("Connection [bold]closed[/bold] while reading, [red]killing[/red] it")
                self.remove_connection(sock_fd, with_exit=False)

    def handle_write(self, sock_fd):
        pass

    def stop_listening(self):
        Printer.vlog("Closing TCP server..")
        with self.state_conn_lock:
            ConnectionHandler.is_listening = False

        try:
            socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(('0.0.0.0', self.port))

        except ConnectionResetError:
            pass

        except ConnectionRefusedError:
            Printer.err("It seems the listener is not running at all")
            pass
