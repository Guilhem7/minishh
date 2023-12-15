# MiniSHh
A mini shell handler to work with on pentesting lab

## Basis
This tool aims at helping for handling default reverse shell. It can enables **raw mode** in different environment and providing a fully interactive shell (AV bypass needed on windows).

It allows using *load* / *upload* and *download* function. All the file transfer functions are based on a **custom Http Server** that must be accessible by the victim machine.

## Config
The file **config.ini** provides the argument for the server.

Default port used by the server:
 - tcp: 9000
 - http: 9001

