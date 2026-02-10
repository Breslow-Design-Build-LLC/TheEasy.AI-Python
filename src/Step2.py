import os
from openai import OpenAI

client = OpenAI(api_key=os.getenv("API_KEY"))

prompt_id = (
    os.getenv("OPENAI_PROMPT_ID")
    or "pmpt_6977e7418e708193ba722b4422464f080876845b508020c9"  # Step 2
)


response = client.responses.create(
    prompt={
        "id": prompt_id,
        "variables": {},
    },
    input=[
        {
            "role": "user",
            "content": "I need a 16 x 23 R-Blade pergola.",
            # "content": "R-Breeze 12x18"
        }
    ],
    stream=False,
)
print(response.output_text)
