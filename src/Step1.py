import os
from openai import OpenAI

client = OpenAI(api_key=os.getenv("API_KEY"))

prompt_id = (
    os.getenv("OPENAI_PROMPT_ID")
    or "pmpt_6977d1cf2b208195b83507388f431b30072ae8d30040d02c"
)


response = client.responses.create(
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
                F) New Product
            """,

            #"type3": "R-Breeze",
            #"topic4": "K-Bana 10x16",
        },
    },
    input=[
        {
            "role": "user",
            #"content": "list all products options"
            "content": "R-Breeze 12x18"
        }
    ],
    stream=False,
)
print(response.output_text)
