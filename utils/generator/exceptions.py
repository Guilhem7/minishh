class BadPortForPayloadError(Exception):
    """Error raised in case the port is not an integer"""
    pass

class IpOrPortNotSetError(Exception):
    """Error raised when trying to generate a reverse shell without setting Ip / Port"""
    pass

class BadArgumentProvidedError(Exception):
    """Error raised when an argument provided is not as it should"""
    pass
