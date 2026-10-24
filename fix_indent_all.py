import re

with open('unificador_listas/app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# I notice that `def prompt_api_key(self):` is indented with 4 spaces but the previous line 583 is indented with 8 spaces.
# `prompt_api_key` is a method of `class App(ctk.CTk):` so 4 spaces is correct.
# Why is there an unindent error on line 586?
# Ah, the `config_methods` we injected earlier were injected ABOVE `def setup_header`.
# Wait, `class App` starts at line 30, then `__init__` at line 515.
# Let's just use `autopep8` or do it manually properly.
