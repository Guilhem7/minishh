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
        if res is not None:
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

    _SystemConfig = ConfigParser()
    ConfigFile = "config.ini"

    @classmethod
    def init_config(cls):
        cls._SystemConfig.read(cls.ConfigFile)

        # Add a custom user section to the config dict if not already present
        if 'UserSection' not in cls._SystemConfig.sections():
            cls._SystemConfig.add_section('UserSection')

        if 'Routes' not in cls._SystemConfig.sections():
            cls._SystemConfig.add_section('Routes')

    @classmethod
    def get(cls, var, section="UserSection", default=""):
        """Get a config variable, do not pass an unknown section"""
        res = cls._SystemConfig[section].get(var)
        if res is not None:
            return res
        return default

    @classmethod
    def get_section(cls, section):
        """Get a config section"""
        if not cls._SystemConfig.has_section(section):
            return None
        return cls._SystemConfig[section]

    @classmethod
    def set_extra_var(cls, var, val, section="UserSection", force=False):
        """
        Set the value 'val' of the variable named 'var' in the config if it does not already exists
        If force is True, then the value overwrite the existing one
        """
        if(not(var in cls._SystemConfig[section]) or force):
            cls._SystemConfig.set(section, var, val)

    @classmethod
    def get_and_set_if_not_exists(cls, var, val, section=None):
        """
        Try to get the value for the variable 'var' in the section 'section'
        Set a key to a val if this one is not already set
        Anyway, return the value associated to the var after being set
        python:
        >>> res = AppConfig.get_and_set_if_not_exists(
                        "shell_script_route",
                        "/random_route.log",
                        "Route")
        >>> res
        '/random_route.log'
        >>> AppConfig.get("shell_script_route", "Route")
        '/random_route.log'
        >>> # Mainly used to set route for scripts if they are not already set from "config.ini"
        """
        if cls.get(var, section, default=None) is None:
            cls.set_extra_var(var, val, section=section, force=False)
        return cls.get(var, section)

    @staticmethod
    def translate_target_to_section(target):
        if target == "linux":
            return target.capitalize()
        return 'Powershell'

class MinishhRequirements:
    """
    Class that check requirement
    """

    @staticmethod
    def check_requirements():
        """Check some requirements before running mniishh to avoid problems"""
        if not os.path.isfile(AppConfig.ConfigFile):
            raise RequirementsError(f"Cannot find the file {AppConfig.ConfigFile}")

        script_dir = MinishhRequirements.check_existing_section_value("directory", "Script")
        if not os.path.isdir(script_dir):
            raise RequirementsError(f"Directory containing script is missing: {script_dir}")

        loot_dir = MinishhRequirements.check_existing_section_value("directory", "Download")
        if not os.path.isdir(loot_dir):
            raise RequirementsError(f"Download directory '{loot_dir}' is not found")

    @staticmethod
    def check_existing_section_value(name, section):
        """
        Return the value stores in the config file
        ```.ini
        [Section]
        name=value
        ```
        """
        value = MinishhRequirements.check_section(section).get(name)
        if value is None:
            raise InvalidConfigurationFile(f"Mandatory value {name} not found in section {section}")
        return value

    @staticmethod
    def check_section(section_name):
        """Return the section in the config if found, else raise InvalidConfigurationFile"""
        section = AppConfig.get_section(section_name)
        if section is None:
            raise InvalidConfigurationFile(f"Missing mandatory section: {section_name} in config")
        return section

class RequirementsError(Exception):
    """Exception raised when one of the requirement is not satisfied"""

class InvalidConfigurationFile(Exception):
    """Exception raised when the config val is missing some required values"""
