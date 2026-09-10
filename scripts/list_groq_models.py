import os
from dotenv import load_dotenv
from groq import Groq

load_dotenv(r"c:\kfms\backend\.env")
client = Groq(api_key=os.environ["GROQ_API_KEY"])

for m in sorted(client.models.list().data, key=lambda x: x.id):
    print(m.id)
