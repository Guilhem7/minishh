"""Module recovering the default ip address of the computer"""
from netifaces import interfaces, ifaddresses, AF_INET

class IpAddr:
    """IpAddr is the class responsible for choosing the ip address of the current computer"""

    LOCALHOST = "127.0.0.1"

    def __init__(self):
        self.ip_available = {}

    def init_ip(self):
        """Init the ip dictionnary like: {'lo': '127.0.0.1'}"""
        for iface_name in interfaces():
            addresses = []
            for elt in ifaddresses(iface_name).setdefault(AF_INET, [{'addr':'127.0.0.1'}]):
                addresses.append(elt["addr"])
            self.ip_available[iface_name] = addresses[0]

    def get_default(self, interface=None):
        """
        Get the default ip address
        Try from the interface name
        Else the first one which is not 127.0.0.1
        Else 127.0.0.1
        """
        if(interface is not None and self.ip_available.get(interface) is not None):
            return self.ip_available[interface]

        for _, ip_addr in self.ip_available.items():
            if ip_addr != IpAddr.LOCALHOST:
                return ip_addr

        return IpAddr.LOCALHOST
