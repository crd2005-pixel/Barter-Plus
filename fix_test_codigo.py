import re

with open('test_services.py', 'r') as f:
    content = f.read()

# Make the barcode unique by appending a random integer or timestamp
# In this case it is just a script, so we will append the time
import time
t = str(int(time.time()))

content = re.sub(
    r'codigo_barras="1234567890"',
    f'codigo_barras="{t}"',
    content
)

with open('test_services.py', 'w') as f:
    f.write(content)
