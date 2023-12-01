"""
Usage with cli

```python
>>> from payload_parser import PayloadParser
>>> parser = PayloadParser()
>>> parser.parse("generate -t linux -i 192.168.2.115 -p 8080")
>>> parser.ip
'192.168.2.115'
>>> parser.setval("tpl", "1")
>>> parser.tpl
'0'
>>> parser.setval("tpl", "1", force=True)
>>> parser.tpl
'1'
>>>
```
"""
import argparse

class PayloadParser:
    """
    Class that allows the parsing of the cli for creating a Payload
    """
    def __init__(self):
        self._parsed = None
        self._parser = argparse.ArgumentParser()
        self._parser.add_argument('-t', '--target', default="windows", help='Target to generate a payload for, default: %(default)s, available: linux, windows, powershell')
        self._parser.add_argument('-i', '--ip', help="Ip to use for payload generation")
        self._parser.add_argument('-p', '--port', help="Port to use for payload generation")
        self._parser.add_argument('-o', '--output', default="show", help="Output to use, infile or show")
        self._parser.add_argument('-e', '--enc', nargs='+', action="extend", help="Encoders to use for the payload (url, base64, base64ps)", required=False)
        self._parser.add_argument('--tpl', default="0", help="Template to use, default %(default)s")

    @property
    def parser(self):
        return self._parser

    @property
    def parsed(self):
        return self._parsed

    def parse(self, cli=None):
        """Parse argument from cli or from string"""
        if cli is None:
            self._parsed, _ = self._parser.parse_known_args()

        else:
            if len(cli.split()) >= 1:
                self._parsed, _ = self._parser.parse_known_args(cli.split()[1:])

    def __getattr__(self, var):
        """Wrapper to access easily variable inside the parsed variables"""
        if self._parsed is not None:
            return getattr(self._parsed, var)
        return None

    def setval(self, var, val, force=False):
        """Set a value for the parser var if it is not already set"""
        if(self._parsed is not None and (force or getattr(self._parsed, var) is None)):
            setattr(self._parsed, var, val)
