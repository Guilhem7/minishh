from .payload_parser import PayloadParser
from .payload import *
from .decorators import *
from .exceptions import BadArgumentProvidedError

class Generator:
    """
    Generator class that can generate different kind of payload from a cli strings
    It handles initialisation of parser variable
    """
    def __init__(self):
        self._parser = PayloadParser()
        self._payload = None
        self.ip = None
        self.port = None

    def get_encoders(self, encoders, payload):
        """
        Return the nested encoder from each encoder
        raise BadArgumentProvidedError if an encoder is not among the known encoders
        """
        if encoders is None:
            return payload

        current_encoder = payload
        for encoder in encoders:
            current_encoder = DecoratorBuilder.build_for(encoder, current_encoder)
            if current_encoder is None:
                raise BadArgumentProvidedError("Encoder '{}' is not among {}".format(encoder, list(DecoratorBuilder._ENCODERS.keys())))
        return current_encoder

    def generate_payload(self, cli, ip=None, port=None, route=None):
        """
        Generate a payload from cli
        Init ip and port if there are not set, else took them from cli

        In case of any missing argument, raise a custom exception containing the error message
        """
        if(cli != None and ("-h" in cli.split() or "--help" in cli.split())):
            self._parser.parser.print_help()
            return ""

        self._parser.parse(cli)
        self._parser.setval("ip", ip)
        self._parser.setval("port", port)

        if route is None:
            self._payload = PayloadBuilder.build_for(self._parser.target)
            self._parser.setval("output", self._payload.default_output)
        
        else:
            self._payload = PayloadBuilder.build_for("remote" + self._parser.target)


        if self._payload is None:
            raise BadArgumentProvidedError(f"The target argument is not known: {self._parser.target}")

        self.ip = self._parser.ip
        self.port = self._parser.port
        if(self.ip is None or self.port is None):
            raise BadArgumentProvidedError(f"The ip argument or port is incorrect: ip -> {self.ip}, port -> {self.port}")

        tpl = self._parser.tpl
        self._payload.with_ip(self.ip).with_port(self.port).using_template(tpl)
        if route is not None:
            self._payload.for_route(route)

        final_payload = self.get_encoders(self._parser.enc, self._payload)
        return final_payload.get_reverse_shell()

    def get_parser_val(self, val):
        """Wrapper to get the value of a parser"""
        return getattr(self._parser.parsed, val)

    def get_payload_for_type(self, target, tpl="0"):
        """
        Return a reverse shell payload for a target type
        It allows to recover shell for other target than cli
        This is used when generating a shell for a windows target, the shell stores in file is a powershell rev shell
        """
        self._payload = PayloadBuilder.build_for(target).with_ip(self.ip).with_port(self.port).using_template(tpl)
        return self._payload.get_reverse_shell()

    def get_remote_payload_for_type(self, target, port, route):
        """
        Return the remote payload for a type, by giving it the route,
        the ip has been saved in the first call to generate_payload
        """
        return PayloadBuilder.build_for("remote" + target).get_remote_payload(self.ip, port, route)
