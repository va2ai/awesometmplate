from dotenv import load_dotenv
import os
import anthropic

load_dotenv(override=True)
k = os.getenv("ANTHROPIC_API_KEY")
print(f"key len: {len(k)}")
print(f"key prefix: {k[:25]}")

c = anthropic.Anthropic(api_key=k)
r = c.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=50,
    messages=[{"role": "user", "content": "say hi in 5 words"}],
)
print(f"Response: {r.content[0].text}")
