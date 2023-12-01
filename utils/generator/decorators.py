"""
Decorators available for reverse shell payload
"""
from urllib.parse import quote_plus
from base64 import b64encode

def b64psencode(val):
    return b64encode(val.encode('utf16')[2:]).decode()

class EncoderDecorator:
    """Class able to encode a payload object"""
    def __init__(self, payload):
        self._payload = payload

    def get_reverse_shell(self):
        return self._payload.get_reverse_shell()

class UrlEncodeDecorator(EncoderDecorator):
    """
    Enable to urlencode the payload
    """
    def get_reverse_shell(self):
        return quote_plus(self._payload.get_reverse_shell())

class Base64EncodeDecorator(EncoderDecorator):
    """
    Enable to base64 encode the payload
    """
    def get_reverse_shell(self):
        return b64encode(self._payload.get_reverse_shell().encode()).decode()

class Base64PsEncodeDecorator(EncoderDecorator):
    """
    Enable to base64 encode the payload for powershell
    """
    def get_reverse_shell(self):
        return b64psencode(self._payload.get_reverse_shell())

class DecoratorBuilder:
    """
    Return the encoder associated to a string
    """

    _ENCODERS = {
                  "url"      : UrlEncodeDecorator,
                  "base64"   : Base64EncodeDecorator,
                  "base64ps" : Base64PsEncodeDecorator
                }

    @classmethod
    def build_for(cls, target, payload):
        target_class = cls._ENCODERS.get(target.lower())
        if target_class:
            return target_class(payload)
        return None
