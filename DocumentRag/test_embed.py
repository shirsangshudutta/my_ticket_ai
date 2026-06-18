import os
from dotenv import load_dotenv
load_dotenv()

api_key   = os.environ.get("AZURE_OPENAI_API_KEY", "MISSING")
embed_dep = os.environ.get("AZURE_EMBED_DEPLOYMENT", "text-embedding-ada-002-1")

print(f"API_KEY   : {api_key[:15]}...")
print(f"EMBED_DEP : {embed_dep}\n")

from openai import OpenAI, AzureOpenAI

tests = [
    ("OpenAI client + openai.azure.com/openai/v1",
     lambda: OpenAI(
         base_url="https://shirsangshudutta-9937-resource.openai.azure.com/openai/v1",
         api_key=api_key)),

    ("OpenAI client + services.ai.azure.com/openai/v1",
     lambda: OpenAI(
         base_url="https://shirsangshudutta-9937-resource.services.ai.azure.com/openai/v1",
         api_key=api_key)),

    ("AzureOpenAI + openai.azure.com + api 2024-02-01",
     lambda: AzureOpenAI(
         azure_endpoint="https://shirsangshudutta-9937-resource.openai.azure.com",
         api_key=api_key,
         api_version="2024-02-01")),

    ("AzureOpenAI + openai.azure.com + api 2024-10-21",
     lambda: AzureOpenAI(
         azure_endpoint="https://shirsangshudutta-9937-resource.openai.azure.com",
         api_key=api_key,
         api_version="2024-10-21")),

    ("AzureOpenAI + services.ai.azure.com + api 2024-10-21",
     lambda: AzureOpenAI(
         azure_endpoint="https://shirsangshudutta-9937-resource.services.ai.azure.com",
         api_key=api_key,
         api_version="2024-10-21")),
]

for label, make_client in tests:
    print(f"Testing: {label}")
    try:
        client = make_client()
        r = client.embeddings.create(input="test", model=embed_dep)
        print(f"  ✅ SUCCESS — dims: {len(r.data[0].embedding)}\n")
        break
    except Exception as e:
        print(f"  ❌ {str(e)[:80]}\n")