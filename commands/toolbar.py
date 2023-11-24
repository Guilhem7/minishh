from config.config import AppConfig
from prompt_toolkit.formatted_text import ANSI

class MinishToolbar:
    
    refresh_interval = 1.0

    @staticmethod
    def get_toolbar():
        return ANSI(" Current ip address: [\x1b[1;41m{}\x1b[0m]".format(AppConfig.get("default_ip_address")))
