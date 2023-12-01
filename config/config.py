import os
from configparser import ConfigParser

class MinishhConfig:
    """
    C2Config is a class allowing to recover the configuration
    of the program from the configuration file
    """

    def __init__(self, config_file = "config.ini"):
        self._config_file = config_file
        self._parser = ConfigParser()
        self.extra_vars = {}

    def parse_config(self):
        self._parser.read(self._config_file)

    @property
    def parser(self):
        return self._parser

    def get(self, section, val, default=""):
        res = self._parser[section].get(val)
        if(res is not None):
            return res

        return default

    def set_extra_var(self, var, val):
        self.extra_vars[var] = val

    def get_extra_var(self, var):
        return self.extra_vars.get(var)


class AppConfig:
    """
    AppConfig is a class allowing to recover the configuration
    of the program from the configuration file
    AppConfig shall only be modified by the main thread
    """

    _ConfigurationFile = "config.ini"
    _SystemConfig = None
    _UserConfig = {}

    @classmethod
    def init_config(cls):
        cls._SystemConfig = ConfigParser()
        cls._SystemConfig.read(cls._ConfigurationFile)

    @classmethod
    def get(cls, val, section=None, default=""):
        """Get a config variable, do not pass an unknown section"""
        res = cls._UserConfig.get(val) if section is None else cls._SystemConfig[section].get(val)
        if res is not None:
            return res
        return default

    @classmethod
    def set_extra_var(cls, var, val):
        cls._UserConfig[var] = val

    @classmethod
    def get_and_set_if_not_exists(cls, var, val, section=None):
        """
        Try to get the value for the variable 'var' in the section 'section'
        Set a key to a val if this one is not already set
        Anyway, return the value associated to the var after being set
        python3:
            >>> res = AppConfig.get_and_set_if_not_exists("shell_script_route", "/random_route.log", "Route")
            >>> res
            '/random_route.log'
            >>> AppConfig.get("shell_script_route", "Route")
            '/random_route.log'
            >>> # Mainly used to set route for scripts if they are not already set from "config.ini" or at init time
        """
        if cls.get(var, section, default=None) is None:
            cls.set_extra_var(var, val)
        return cls.get(var, section)

class MinishhRequirements:

    @staticmethod
    def check_requirements():
        if not(os.path.isfile(AppConfig._ConfigurationFile)):
            raise MissingConfigurationFileError(f"Cannot find the file {AppConfig._ConfigurationFile}")

        if not(os.path.isdir(AppConfig.get("directory", "Script"))):
            raise MissingScriptDirectoriesError("Directory containing script is missing: {}".format(AppConfig.get("directory", "Script")))

class MissingConfigurationFileError(Exception):
    """Error raised if the configurationfile is missing"""
    pass

class MissingScriptDirectoriesError(Exception):
    """Error raised when the directory containing scripts is missing"""
    pass
