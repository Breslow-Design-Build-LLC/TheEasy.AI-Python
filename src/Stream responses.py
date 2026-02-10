import json
import os
from openai import OpenAI

client = OpenAI(api_key=os.getenv("API_KEY"))

prompt_id = (
    os.getenv("OPENAI_PROMPT_ID")
    or "pmpt_6977d1cf2b208195b83507388f431b30072ae8d30040d02c"

)


stream = client.responses.create(
    prompt={
        "id": prompt_id,
        "version": "5",
        "variables": {
            "product_options": """
                A) R-Blade
                B) R-Breeze
                C) K-Bana
                D) X-Blast
                E) Sky-Tilt
            """,

            #"type3": "R-Breeze",
            #"topic4": "K-Bana 10x16",
        },
    },
    input=[
        {
            "role": "user",
            "content": "list all products options"
            #"content": "R-Breeze 12x18"
        }
    ],
    stream=True,
)

output_chunks: list[str] = []

for event in stream:
    if event.type == "response.output_text.delta":
        output_chunks.append(event.delta)
        print(event.delta, end="", flush=True)

full_text = "".join(output_chunks).strip()
if full_text:
    try:
        payload = json.loads(full_text)
    except json.JSONDecodeError:
        payload = None
    if isinstance(payload, dict) and payload.get("status") == "needs_info":
        questions = payload.get("questions") or []
        if questions:
            print()
            print(questions[0])
