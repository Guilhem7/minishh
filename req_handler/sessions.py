import readline
import random
import socket
import select
import queue
import time
import os
import re
from enum import Enum, auto
from shell_utils.shell_factory import *
from utils.print_utils import Printer
from utils.pwsh_utils import ObfUtil
from threading import Thread, Lock
from req_handler.session_exec import SessionExec
from req_handler.proxy_forwarder import ProxyForwarder
from shell_utils.skeleton_shell import SkeletonShell
from commands.session_command import SessionCommand
from utils.minishh_utils import MinishhUtils
from config.config import AppConfig
from prompt_toolkit.formatted_text import ANSI
from prompt_toolkit.patch_stdout import patch_stdout

class SessionStatus(Enum):
    Uninitialized = auto()
    Initialized   = auto()
    Invalid       = auto()
    Http          = auto()
    Died          = auto()

class SessionAssets:
    def __init__(self):
        self.binaries = []
        self.shell_type = None
        self.current_user = ""

    def add_binary(self, binary):
        self.binaries.append(binary)

    def set_shell_type(self, shell_type):
        self.shell_type = shell_type

    def are_available(self, binaries):
        for b in binaries:
            if not self.is_available(b):
                Printer.log(f"Executable {b} not available...")
                return False
        return True

    def set_current_user(self, user):
        self.current_user = user

    def is_available(self, binary):
        return binary in self.binaries

class SessionUtils:
    def __init__(self, conn):
        self.status = SessionStatus.Uninitialized
        self.conn = conn
        self.command_executor = SessionExec(self.conn)
        self._observers = []

    def attach(self, observer):
        self._observers.append(observer)

    def get_answer_queue(self):
        return self.command_executor.answer_queue

    def empty_queue(self, q):
        with q.mutex:
            q.queue.clear()

    def get_connection(self):
        return self.conn

    def run_default_command(self, shell):
        self.command_executor.exec_all_no_result(
            shell.default_command(),
            wait=0.2)

    def is_waiting(self):
        return self.command_executor.is_waiting

    def close(self):
        self.conn.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, b'\x01\x00\x00\x00\x00\x00\x00\x00')
        self.conn.close()

class SessionInit(SessionUtils, Thread):
    """
    The SessionInit class init a session
    and act as a factory once the initialisation is complete
    """
    def __init__(self, conn):
        SessionUtils.__init__(self, conn)
        Thread.__init__(self)
        self.session_assets = SessionAssets()
        self.shell = None

    def build(self):
        return Session(self.conn, self.session_assets, self.shell)

    def is_session_valid(self):
        check_value = ObfUtil.get_random_string(32)
        res = self.command_executor.exec("echo {}".format(check_value), timeout=2.5) #, get_all=False)
        return check_value in res

    def enumerate_binary(self, shell_type):
        cmd = SkeletonShell.enumerate_binary_command(shell_type)
        if(cmd is None):
            return

        Printer.dbg(f"Enumerating binaries with: '{cmd}'")
        res = self.command_executor.exec(cmd, timeout=2.5, get_all=True)
        if res:
            for binary in SkeletonShell.get_useful_binaries(shell_type):
                Printer.dbg(f"Looking for binary {binary} in {res}")
                if binary in res:
                    self.session_assets.add_binary(binary)

    def get_shell_type(self, shell_type_list):
        for shell_type in shell_type_list:
            result_for_identification = self.command_executor.exec(
                                                                SkeletonShell.get_command_for_identify_shell(shell_type),
                                                                timeout=3,
                                                                get_all=True,
                                                                hide_error=True,
                                                                shell_type=shell_type)

            if(SkeletonShell.expected_answer(shell_type) in result_for_identification.lower()):
                return shell_type

        raise Exception("Cannot identify current shell...")

    def notify(self):
        """Notify each observers for the session"""
        for obs in self._observers:
            obs.notify(self)

    def set_shell_type(self, shell_type):
        """Wrapper for the set_shell_type method"""
        self.session_assets.set_shell_type(shell_type)

    def is_shell_type_tty(self, shell_type):
        """
        Check if the current shell is a tty or not
        """
        if shell_type & Shells.Basic:
            answer = self.command_executor.exec("tty", timeout=0.8, get_all=False)
            if re.match(r".*/dev/.*", answer, re.DOTALL):
                return True
        return False

    def run(self):
        """
        Function to init a session. This part is here to identify the kind of
        session that we receive. Is it a windows reverse shell or a unix or ...

        Also try to gather basic information, like binaries available and current user.
        We also need to prevent trying to starting a session from a HTTP request,
        that is why we sleep before
        """
        try:
            host, port = self.get_connection().getpeername()
            Printer.log("New Connection from [blue]{}:{}[/blue]".format(host, port))
            first_answer = self.command_executor.exec(SkeletonShell.DUMMY_COMMAND, timeout=0.8, get_all=False)
            if self.is_session_valid():
                shell_type = self.get_shell_type(SkeletonShell.recover_shell_type_from_prompt(first_answer))
                Printer.log(f"Identified Shell of type: [bold]{shell_type}[/bold]")
                self.set_shell_type(shell_type)

                self.enumerate_binary(shell_type)
                self.session_assets.set_current_user(self.command_executor.exec("whoami",
                                                                                timeout=1.5,
                                                                                get_all=True))
                is_tty = self.is_shell_type_tty(shell_type)
                self.shell = ShellFactory.build(shell_type, tty=is_tty)

                self.run_default_command(self.shell)
                self.status = SessionStatus.Initialized
            else:
                self.status = SessionStatus.Invalid

        except Exception:
            Printer.exception()
            pass

        finally:
            self.notify()

class Session(SessionUtils):

    EXIT_COMMANDS = ["x", "quit", "exit"]

    def __init__(self, conn, sess_assets, shell):
        """
        self.status : SessionStatus : status of the current session
        self.session_assets : SessionAssets : Link to the current session attributes
        self.connection : Connection : Link to the class Connection
        self.prompt : str : Current prompt of the session
        self.commands : SessionCommand : Link to the class handling command in this configuration
        self.download_server : HttpServer : Link to interact with the download server
        """
        super().__init__(conn)
        self.status = SessionStatus.Initialized
        self.session_assets = sess_assets
        self.connection = Connection(conn, shell)
        self.prompt = Printer.format("[u]Session[/u]([yellow]" + self.connection.host + "[/yellow])> ")
        self.commands = SessionCommand(self)
        self.download_server = None

    def __str__(self):
        return "Session[[blue]{}[/blue]]".format(self.connection.host)

    def set_download_server(self, download_server):
        self.download_server = download_server

    def run(self):
        self.cmd = ""

        while (self.status == SessionStatus.Initialized):
            with patch_stdout(raw=True):
                self.cmd = self.commands.session.prompt(ANSI(self.prompt))

            if(self.cmd in Session.EXIT_COMMANDS or self.status != SessionStatus.Initialized):
                break

            elif(self.cmd == ""):
                print()

            else:
                try:
                    self.commands.handle_input(self.cmd)
                except Exception:
                    Printer.err(f"Command [red]{self.cmd}[/red] failed..")
                    Printer.exception()

    def show_session_info(self):
        Printer.table_show(
            {"Ip Address": "green", "Shell in Use": "yellow", "Whoami": "red"},
            [(self.connection.host, self.connection.shell_handler.shell_type.name, self.session_assets.current_user)],
            "Session info")

    def notify_close(self):
        """Notify the observer that the session is closed"""
        for obs in self._observers:
            obs.notify_close(self)

    def upgrade(self):
        """
        Upgrade current shell to tty
        """
        if not self.connection.shell_handler.is_tty:
            self.connection.shell_handler.set_tty()
            self.run_default_command(self.connection.shell_handler)
        else:
            Printer.verr(f"Trying to upgrade an already tty shell")

    def downgrade(self):
        """
        Downgrading the shell
        """
        self.connection.shell_handler.reset_tty()
        self.command_executor.exec_no_result(self.connection.shell_handler.reset_prompt())

    def run_config_script(self):
        """Run the default command from config"""
        target_section = AppConfig.translate_target_to_section(self.connection.shell_handler.os)
        if AppConfig.get("auto_upgrade", section=target_section, default='N').upper() == 'Y':
            Printer.log("auto_upgrade set to true, upgrading session...")
            self.commands.execute_upgrade()

        script_to_load = MinishhUtils.parse_scripts(AppConfig.get("auto_load_scripts", section=target_section).split(','))
        for script in script_to_load:
            Printer.log(f"Loading script [yellow]{script}[/yellow]")
            self.commands.execute_load(script)

    def close(self, with_exit=True):
        try:
            if(with_exit):
                self.command_executor.exec_no_result("exit")
        except Exception:
            pass

        self.connection.close()
        self.status = SessionStatus.Died

class Connection:

    def __init__(self, conn, shell, is_active = False):
        self.conn = conn
        self.is_active = is_active
        self._MQ = queue.Queue()
        self._host, self._port = self.conn.getpeername()
        self.shell_handler = shell

    def get_queue(self):
        return self._MQ

    @property
    def shell_type(self):
        """
        Return the type of shell associated to the connection
        """
        return self.shell_handler.get_type()

    @property
    def host(self):
        return self._host

    def flush_queue(self, q):
        for item in q.queue:
            sys.stdout.write(item)

        sys.stdout.flush()
        self.empty_queue(q)

    def empty_queue(self, q):
        with q.mutex:
            q.queue.clear()

    def init_shell(self):
        self.shell_handler.help()
        self.shell_handler.init()

    def reset_shell(self):
        if self.shell_handler is not None:
            self.shell_handler.reset_shell()

    def run(self):
        """
        Interact with the reverse shell here ! If the config variable is set to 'Y', then
        the message between the reverse shell and the sessions will not be output when
        the session is not active.
        """
        self.is_active = True
        if AppConfig.get("hide_communication", "Connections", "N").upper() == 'Y':
            self.empty_queue(self._MQ)
        self.flush_queue(self._MQ)
        msg = ""

        try:
            self.conn.send(b"\n")
            self.init_shell()
            while self.is_active:
                CMD = self.shell_handler.get_input()
                if(self.is_active):
                    self.conn.send(CMD)

        except Exception as e:
            Printer.dbg(e)
            pass

        except KeyboardInterrupt:
            msg = "Connection put in [blue]background[/blue]"
            pass

        finally:
            self.shell_handler.reset_shell()
            self.is_active = False
            if(msg != ""):
                Printer.crlf().log(msg)

    def close(self):
        self.conn.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, b'\x01\x00\x00\x00\x00\x00\x00\x00') # Send TCP RST
        self.conn.close()
        self.is_active = False
