import re
import time
import socket
import select
from utils.print_utils import Printer

class TimeoutReachError(Exception):
    """Error raised when the timeout is reach during socket communication"""
    pass

class ProxyForwarder:
    """
    Forward connection to local one if needed
    """
    TIMEOUT = 0.4
    HTTP_TIMEOUT = 5
    reContentLength = re.compile(rb".*Content-Length: (\d+)", re.I | re.DOTALL)

    def __init__(self, forward_server, buff_size, connections=None):
        self.forward_server = forward_server
        self.buff_size = buff_size
        if connections:
            self.connections = connections
        else:
            self.connections = {}

    def __str__(self):
        return f"ProxyForwarder(target={self.forward_server})"

    def _try_parse(self, socket, msg):
        """
        Try to parse the incoming http message
        """
        if msg.startswith(b"GET /"):
            self.connections[socket] = {"type": "GET"}

        elif msg.startswith(b"POST /"):
            try:
                content_length = int(re.match(self.reContentLength, msg).group(1))
                end_headers = msg.find(b"\r\n\r\n")
                if end_headers == -1:
                    return
                total_request_size = content_length + end_headers + len(b"\r\n\r\n")
                self.connections[socket] = {"type": "POST", "content-length": content_length, "size": total_request_size}

            except Exception:
                pass


    def isHttp(self, new_socket):
        """
        Check if the TCP exchange actually contains HTTP

        :param socket: The socket to check
        """
        start_time = time.time()
        while True:
            read_list, _, _ = select.select([new_socket], [], [], self.TIMEOUT)
            for sock_fd in read_list:
                data = sock_fd.recv(self.buff_size, socket.MSG_PEEK) # MSG_PEEK does not consume the socket data
                if not data:
                    raise ConnectionResetError

                if isinstance(data, str):
                    data = data.encode()

                self._try_parse(sock_fd, data)
                return self.connections.get(sock_fd) is not None

            if time.time() - start_time > self.TIMEOUT:
                return False

    def _forward_http_request(self, from_socket, dest_socket):
        """
        Forward Request from from_socket to dest_socket

        :raises ConnectionResetError: When the connection is interrupted
        :raises TimeoutReachError: When a timeout is encoutered during the HTTP exchange

        :param from_socket: The socket with incoming trafic
        :type from_socket: class:`socket`

        :param dest_socket: The socket that will receive the incoming trafic
        :param dest_socket: class:`socket`
        """
        start_time = time.time()
        readable_sockets = [from_socket]
        writable_sockets = [dest_socket]

        socket_infos = self.connections.get(from_socket)
        request_type = socket_infos["type"]
        readed_bytes = 0
        to_send = b""
        while writable_sockets:
            read_list, write_list, _ = select.select(readable_sockets, writable_sockets, [], self.TIMEOUT)
            for sock_fd in read_list:
                data = sock_fd.recv(self.buff_size)
                if not data:
                    raise ConnectionResetError
                readed_bytes += len(data)
                Printer.vlog(f"Reading {len(data)} bytes")
                to_send += data
                if((request_type == "GET" and data.endswith(b"\r\n\r\n"))
                   or (request_type == "POST" and readed_bytes == socket_infos["size"])):
                    readable_sockets = []

            for wsock_fd in write_list:
                if to_send:
                    Printer.vlog(f"Forwarding {len(to_send)} bytes")
                    wsock_fd.send(to_send)
                    to_send = b""
                    if not readable_sockets:
                        writable_sockets = []
                        break

            if time.time() - start_time > self.HTTP_TIMEOUT:
                raise TimeoutReachError("Max Time for forwarding communication reached")

    def _forward_http_response(self, from_socket, dest_socket):
        """
        Forward Response from from_socket to dest_socket

        :raises ConnectionResetError: When the connection is interrupted
        :raises TimeoutReachError: When a timeout is encoutered during the HTTP exchange

        :param from_socket: The socket with incoming trafic
        :type from_socket: class:`socket`

        :param dest_socket: The socket that will receive the incoming trafic
        :param dest_socket: class:`socket`
        """
        start_time = time.time()
        readable_sockets = [from_socket]
        writable_sockets = [dest_socket]

        response_infos_size = None
        readed_bytes = 0

        to_send = b""

        while writable_sockets:
            read_list, write_list, _ = select.select(readable_sockets, writable_sockets, [], self.TIMEOUT)
            for sock_fd in read_list:
                data = sock_fd.recv(self.buff_size)
                if not data:
                    raise ConnectionResetError

                if not response_infos_size:
                    content_length = re.match(self.reContentLength, data)
                    if content_length:
                        content_length = int(content_length.group(1))
                        end_headers = data.find(b"\r\n\r\n")
                        if end_headers == -1:
                            return
                        response_infos_size = content_length + end_headers + len(b"\r\n\r\n")
                        Printer.vlog(f"Response size {response_infos_size}")
                    else:
                        # No content length in response
                        response_infos_size = len(data)

                readed_bytes += len(data)
                to_send += data

                if readed_bytes == response_infos_size:
                    readable_sockets = []

            for sock_fd in write_list:
                if to_send:
                    sock_fd.send(to_send)
                    to_send = b""
                    if not readable_sockets:
                        writable_sockets = []
                        break

            if time.time() - start_time > self.HTTP_TIMEOUT:
                raise TimeoutReachError("Max Time for forwarding communication reached")

    def forward(self, socket_used):
        """
        Forward a HTTP Connection

        1. We take the data from the first socket
        2. We forward to the sever
        3. We take the result from the server
        4. We forward to the first socket
        5. We send a FIN ACK to close the connection
        """
        try:
            socket_forward = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            socket_forward.connect(self.forward_server)
            self._forward_http_request(socket_used, socket_forward)
            self._forward_http_response(socket_forward, socket_used)

        except TimeoutReachError:
            Printer.err("HTTP communication timed out")

        except Exception:
            pass

        finally:
            self.close(socket_used)
            self.close(socket_forward)

    def close_connection(self, socket_used):
        """
        Remove a socket from the connection

        :param socket_used: The socket to remove from the connections
        :type socket_used: class:`Socket`
        """
        if self.connections.get(socket_used):
            del self.connections[socket_used]

    def close(self, socket, violent=False):
        """
        Close a socket

        :param violent: Send a RST if true
        :type violent: bool
        """
        try:
            if violent:
                socket.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, b'\x01\x00\x00\x00\x00\x00\x00\x00')
            socket.close()
        except Exception:
            pass
