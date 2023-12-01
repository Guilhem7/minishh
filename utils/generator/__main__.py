from .payload_generator import Generator

generator = Generator()
payload = generator.generate_payload(cli=None)
print(payload)
