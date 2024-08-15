Make the HTTP timeout possible even from a session
When no session and a new one is created, then auto-enter it
Compile the conpty for windows and powershell

Reduce request number (do not relaunch each time each command)


Enhancements:
1. Add --debug and --verbose arguments [Done]
2. Allow reload config [Partially done, command available only from MENU]
3. https://github.com/microsoft/terminal/blob/main/samples/ConPTY/EchoCon/EchoCon/EchoCon.cpp
4. Add a local prompt (for nc-like shell) and a remote prompt (for pty) [DONE] (may be improved with custom placeholder)
5. Identify shell pty
6. When reset from Pty --> reset prompt needed [DONE]

Enhancements++:
1. Run command in another terminal
2. Integrate arsenal inside reverse shell
3. Forward X Server ?

