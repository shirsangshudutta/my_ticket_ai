"""
chain.py
LangChain RAG chain for pattern recommendation.
Uses cosmos_store for retrieval instead of FAISS.
"""

import os
from dotenv import load_dotenv
load_dotenv()

from langchain_openai import AzureChatOpenAI
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from cosmos_store import search, format_context

SYSTEM_PROMPT = """You are an Azure Integration Architecture Advisor for a retail company.

You ONLY recommend integration patterns from the retrieved CIS catalogue below.
Do NOT invent patterns not present in the context.

Context (retrieved patterns):
{context}

Based on the user's requirements, recommend the best matching pattern.
Structure your response as:

RECOMMENDED PATTERN: <pattern name>
REASON: <2-3 sentences why this fits>
FLOW: <Source → MS → Broker → Consumer(s)>
KEY AZURE SERVICES: <comma separated>
WATCH OUT FOR: <one risk or gotcha>
"""


from openai import OpenAI

def recommend_pattern(query: str) -> dict:
    """Retrieve top matching CIS patterns and recommend one."""
    results = search(query, k=2)
    context = format_context(results)

    prompt_text = SYSTEM_PROMPT.format(context=context) + f"\n\nUser requirement: {query}"

    client = OpenAI(
        base_url=os.environ["AZURE_OPENAI_ENDPOINT"],
        api_key=os.environ["AZURE_OPENAI_API_KEY"],
    )
    response = client.chat.completions.create(
        model=os.environ.get("AZURE_CHAT_DEPLOYMENT", "gpt-4o-1"),
        messages=[{"role": "user", "content": prompt_text}],
        temperature=0,
        max_tokens=800,
    )
    answer = response.choices[0].message.content

    return {
        "result":           answer,
        "source_documents": results,
    }