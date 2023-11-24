import readline
import random
import socket
import select
import queue
import os
import re
from enum import Enum, auto
from shell_utils.shell_factory import *
from utils.print_utils import Printer
from utils.pwsh_utils import ObfUtil
from threading import Thread, Lock
from req_handler.session_exec import SessionExec
from shell_utils.skeleton_shell import SkeletonShell
from commands.session_command import SessionCommand
from config.config import AppConfig
from prompt_toolkit.formatted_text import ANSI

class SessionStatus(Enum):
    Uninitialized = auto()
    Initialized   = auto()
    Invalid       = auto()
    Died          = auto()

class SessionAssets:
    def __init__(self):
        self.os = OperatingSystem.Linux
        self.binaries = []
        self.shell_type = None
        self.current_user = ""

    def add_binary(self, binary):
        self.binaries.append(binary)

    def set_shell_type(self, shell_type):
        self.shell_type = shell_type

    def are_available(self, binaries):
        for b in binaries:
            if not(self.is_available(b)):
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

    def run_default_command(self, shell_type):
        self.command_executor.exec_all_no_result(
            ShellFactory.Shells[shell_type].default_command(),
            shell_type,
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

    def build(self):
        return Session(self.conn, self.session_assets)

    def is_session_valid(self):
        check_value = ObfUtil.get_random_string(32)
        res = self.command_executor.exec("echo {}".format(check_value), timeout=2.5) #, get_all=False)
        return check_value in res

    def enumerate_binary(self, shell_type):
        cmd = SkeletonShell.enumerate_binary_command(shell_type)
        if(cmd is None):
            return

        res = self.command_executor.exec(cmd, timeout=2.5, get_all=True)
        if(res != ""):
            for binary in SkeletonShell.get_useful_binaries(shell_type):
                if(binary in res):
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

    def run(self):
        try:
            first_answer = self.command_executor.exec(SkeletonShell.DUMMY_COMMAND, timeout=0.8, get_all=False)
            if(self.is_session_valid()):
                shell_type = self.get_shell_type(SkeletonShell.recover_shell_type_from_prompt(first_answer))
                Printer.msg(f"Identified Shell of type: [bold]{shell_type}[/bold]")
                self.set_shell_type(shell_type)
                self.run_default_command(shell_type)
                self.enumerate_binary(shell_type)
                self.session_assets.set_current_user(self.command_executor.exec("whoami", timeout=1.5, get_all=True))
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

    def __init__(self, conn, sess_assets):
        super().__init__(conn)
        self.status = SessionStatus.Initialized
        self.session_assets = sess_assets
        self.connection = Connection(conn, self.session_assets.shell_type)
        self.prompt = Printer.format("{underline}Session{reset}({yellow}" + self.connection.host + "{reset})> ")
        self.commands = SessionCommand(self)
        self.download_server = None

    def __str__(self):
        return "Session[[blue]{}[/blue]]".format(self.connection.host)

    def set_download_server(self, download_server):
        self.download_server = download_server

    def run(self):
        self.cmd = ""
        
        while (self.status == SessionStatus.Initialized):
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
            [(self.connection.host, self.connection.shell_type.name, self.session_assets.current_user)],
            "Session info")

    def notify_close(self):
        for obs in self._observers:
            obs.notify_close(self)

    def close(self, with_exit=True):
        try:
            if(with_exit):
                self.command_executor.exec_no_result("exit", shell_type=self.connection.shell_type)
        except Exception:
            pass

        self.connection.close()
        self.status = SessionStatus.Died

class Connection:

    def __init__(self, conn, shell_type, is_active = False):
        self.conn = conn
        self.is_active = is_active
        self._MQ = queue.Queue()
        self._host, self._port = self.conn.getpeername()
        self.shell_type = shell_type
        self.shell_handler = ShellFactory.build(self.shell_type)

    def get_queue(self):
        return self._MQ

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
        if(self.shell_handler is not None):
            self.shell_handler.reset_shell()

    def change_shell(self, shell_type):
        previous_shell = self.shell_type

        if previous_shell is ShellTypes.Pty:
            self.shell_type = self.shell_handler.previous_shell if self.shell_handler.previous_shell else shell_type

        else:
            self.shell_type = shell_type
        
        self.shell_handler = ShellFactory.build(self.shell_type)
        if self.shell_type is ShellTypes.Pty:
            self.shell_handler.previous_shell = previous_shell

    def run(self):
        self.is_active = True
        self.flush_queue(self._MQ)
        msg = ""

        try:
            self.init_shell()
            while self.is_active:
                CMD = self.shell_handler.get_input()
                if(self.is_active):
                    self.conn.send(CMD)
        
        except Exception as e:
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