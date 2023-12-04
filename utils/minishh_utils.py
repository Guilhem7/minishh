"""
MinishhUtils helps with some function

In the minishh config file, you can add some scripts that will be run on different time
For instance when running a reverse shell payload you may want to bypass amsi
with your custom scripts

Then just add your scripts delimited by a coma in the config file
And minishh will load them when needed

This class can parse your script from the conf and check if they are accessible or not
"""
import os
from config.config import AppConfig
from utils.print_utils import Printer

class MinishhUtils:
    """
    MinishhUtils is the class providing minimal function to simplify some parts
    This class is defined with staticmethod only
    """

    @staticmethod
    def get_file(filename):
        """
        Checks if the file path gave as arguments is in current path,
        or is in the script directory and return its relative path if found
        if the file is not found, then None is returned
        """
        script_path = AppConfig.get("directory", "Script")
        if os.path.isfile(filename):
            return filename

        script_filename = script_path + "/" + filename
        if os.path.isfile(script_filename):
            return script_filename

        Printer.err(f"File not found [blue]{filename}[/blue]")
        return None

    @staticmethod
    def get_scripts(name, section):
        """
        Returns the scripts associated to the var 'name' in the config
        This functions does not checks that script exists

        ```python
        # In config.ini: app_script=test.ps1, safe.ps1
        >>> MinishhUtils.get_scripts("app_script")
        ['test.ps1', 'safe.ps1']
        ```
        """
        scripts_name = AppConfig.get(name, section)
        scripts = list(map(lambda x:x.strip(), scripts_name.split(',')))
        return scripts

    @staticmethod
    def parse_scripts(script_list):
        """
        Parse a list of script, and return a list of relative path to existing one
        Print a message if a script does not exists
        
        ```python
        >>> a = ['test.ps1', 'safe.ps1', 'IdontExist']
        >>> scripts = MinishhUtils.parse_scripts(a)
        File not found IdontExist
        >>> scripts
        ['scripts/test.ps1', 'scripts/safe.ps1']
        """
        if not script_list:
            return script_list

        map_existing_script = filter(None,
                                map(MinishhUtils.get_file, script_list)
                                ) # Filter script by existsing and remove None
        return list(map_existing_script)

    @staticmethod
    def recover_scripts(key, section):
        """Just a wrapper above both functions `get_scripts` and `parse_scripts`"""
        return MinishhUtils.parse_scripts(MinishhUtils.get_scripts(key, section))
