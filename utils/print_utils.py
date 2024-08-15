import sys
from rich import print as rp
from rich.console import Console
from rich.table import Table
from rich.markup import escape, render as render_markup

class Printer:
    """ Helper for logging output (static methods only)"""
    LOAD = ['\\', '-', '/', '-']
    ANSI_RED = "\x1b[31m"
    ANSI_GREEN = "\x1b[32m"
    ANSI_YELLOW = "\x1b[33m"
    ANSI_BLUE = "\x1b[34m"
    ANSI_RESET = "\x1b[0m"
    ANSI_LYELLOW = "\x1b[38;5;226m"
    UNDERLINE = "\x1b[4m"
    BOLD = "\x1b[1m"

    console = Console()

    verbose = False
    debug = False

    @staticmethod
    def escape(m):
        """
        Escape a value for rich
        """
        return escape(m)

    @staticmethod
    def log(m, end="\n"):
        rp("[blue bold][>][/blue bold] {}".format(m), end=end)

    @staticmethod
    def msg(m, end="\n"):
        rp("[green bold][+][/green bold] {}".format(m), end=end)

    @staticmethod
    def err(m, end="\n"):
        if isinstance(m, Exception):
            rp("[red bold][-][/red bold] [red]{}[/red]: [white]{}[/white]".format(type(m).__name__, m), end=end, file=sys.stderr)

        else:
            rp("[red bold][-][/red bold] {}".format(m), end=end, file=sys.stderr)

    @classmethod
    def dbg(cls, m, end="\n"):
        if Printer.debug:
            rp("[[yellow bold]>[/yellow bold]] {}".format(m), end=end)

    @staticmethod
    def crlf():
        print()
        return Printer

    @staticmethod
    def cr():
        print("\r", end="")
        return Printer

    @staticmethod
    def vdbg(m, end="\n"):
        if(Printer.verbose):
            Printer.dbg(m, end)

    @staticmethod
    def vlog(m, end="\n"):
        if(Printer.verbose):
            Printer.log(m, end)

    @staticmethod
    def vmsg(m, end="\n"):
        if(Printer.verbose):
            Printer.msg(m, end)

    @staticmethod
    def verr(m, end="\n"):
        if(Printer.verbose):
            Printer.err(m, end)
    
    @staticmethod
    def loading(i):
        if(i % 50 == 0):
            print("[{}] Loading...".format(str(Printer.LOAD[i % 4])), end="\r")

    @staticmethod
    def bar_load(i, max_bar):
        BAR_LENGTH = 40
        PERCENTAGE = ((i*BAR_LENGTH)//max_bar)

        print("[{}>{}]".format("="*PERCENTAGE, " "*(BAR_LENGTH - PERCENTAGE)), end="\r")

    @classmethod
    def pad(cls):
        print("  ", end="")
        return cls

    @classmethod
    def format(cls, val):
        """
        Format the value from rich to ANSI Code
        """
        return cls.console._render_buffer(cls.console.render(render_markup(val)))[:-1]

    @staticmethod
    def print(val, colorized=True, **kwargs):
        """Print to the terminal, with rich or without"""
        if colorized:
            rp(val, **kwargs)
        
        else:
            print(val, **kwargs)

    @staticmethod
    def table_show(columns_dict, rows, title=""):
        table = Table(title=title)
        for col,style in columns_dict.items():
            table.add_column(col, style=style)

        for row_tuple in rows:
            table.add_row(*row_tuple)

        Printer.print(table)

    @staticmethod
    def exception(max_frames=8):
        Printer.console.print_exception(max_frames=max_frames)

    @staticmethod
    def set_color(noColor):
        if (noColor):
            Printer.ANSI_RED = ""
            Printer.ANSI_GREEN = ""
            Printer.ANSI_YELLOW = ""
            Printer.ANSI_BLUE = ""
            Printer.ANSI_RESET = ""
            Printer.UNDERLINE = ""
            Printer.BOLD = ""
