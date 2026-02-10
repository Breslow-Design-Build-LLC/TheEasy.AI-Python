
import os
from openai import OpenAI
client = OpenAI(api_key=os.getenv("API_KEY2"))
#client = OpenAI()

models = client.models.list()

print("Models available to this API key:\n")
for m in models.data:
    print(m.id)
    
    
response = client.responses.create(
  model="gpt-4.1",
  input="Write a one-sentence bedtime story about a unicorn."
)

print(response.output_text)

