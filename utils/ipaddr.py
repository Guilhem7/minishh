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


    @staticmethod
    def _is_up(interface):
        """
        Check if an interface is up or not, if failure, then return False
        """
        try:
            with open(f"/sys/class/net/{interface}/operstate", "r") as f:
                running = f.read().strip() == "up"
            return running
        except Exception:
            pass
        return False

    def get_default(self, interface=None):
        """
        Get the default ip address
        Try from the interface name
        Else the first one which is not 127.0.0.1 and UP
        Else the first one which is not 127.0.0.1
        Else 127.0.0.1
        """
        if(interface and self.ip_available.get(interface)):
            return self.ip_available[interface]

        up_ifaces = filter(IpAddr._is_up, self.ip_available)
        choosen = next(up_ifaces, None)
        if choosen:
            return self.ip_available[choosen]

        for _, ip_addr in self.ip_available.items():
            if ip_addr != IpAddr.LOCALHOST:
                return ip_addr

        return IpAddr.LOCALHOST
