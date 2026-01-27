
import base64
import os
import requests
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

image_url = "https://upload.wikimedia.org/wikipedia/commons/3/3b/LeBron_James_Layup_%28Cleveland_vs_Brooklyn_2018%29.jpg"
# Download locally to avoid host blocks on server-side fetches.
image_bytes = requests.get(image_url, timeout=30).content
image_b64 = base64.b64encode(image_bytes).decode("utf-8")

response = client.responses.create(
    model="gpt-4.1",
    input=[
        {
            "role": "user",
            "content": [
                {
                    "type": "input_text",
                    "text": "What teams are playing in this image?",
                },
                {
                    "type": "input_image",
                    "image_url": f"data:image/jpeg;base64,{image_b64}",
                },
            ],
        }
    ],
)

print(response.output_text)
