from unificador_listas.app import App

app = App()
app.api_key = "dummy"

# Simulate a 429 error and see if it sleeps and retries.
import time
start = time.time()

# We expect it to break eventually since dummy key isn't valid, but it should take some time if it retries.
# Wait, a dummy key usually causes 400 (Bad Request), which won't retry.
# Let's mock the genai client to raise 429 explicitly.
class MockModels:
    def generate_content(self, *args, **kwargs):
        raise Exception("429 Too Many Requests")

class MockClient:
    def __init__(self, *args, **kwargs):
        self.models = MockModels()

import google.genai as genai
genai.Client = MockClient

try:
    res = app._analyze_sheet_structure_with_llm("test", "test")
except Exception as e:
    pass

end = time.time()
print(f"Elapsed: {end-start} seconds. Res: {res}")
# Expected elapsed: 2 + 4 + 6 = ~12 seconds
