"""Smoke-test script: verifies GOOGLE_API_KEY is set and the Gemini SDK can reach gemini-2.5-flash."""

import os

from dotenv import load_dotenv
from google import genai

load_dotenv()

client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
response = client.models.generate_content(
    model="gemini-flash-latest",
    contents="Say hello and tell me what model you are",
)
print(response.text)
