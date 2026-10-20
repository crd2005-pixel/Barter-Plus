import re
text = "```json\n{\"bloques\": []}\n```"
text = re.sub(r'^```json\s*', '', text, flags=re.IGNORECASE)
text = re.sub(r'```\s*$', '', text)
print(text.strip())
