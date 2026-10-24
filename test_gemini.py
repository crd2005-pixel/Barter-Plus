try:
    from google import genai
    from pydantic import BaseModel, Field
    print("Dependencies ok")
except ImportError:
    print("Dependencies not found")
