# Retail Azure Integration Pattern Advisor

Streamlit + LangChain app that recommends Azure integration patterns
grounded in your company's pattern catalogue.

## Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set environment variables
export AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
export AZURE_OPENAI_API_KEY=your-key
export AZURE_SONNET_DEPLOYMENT=claude-sonnet
export AZURE_EMBED_DEPLOYMENT=text-embedding-ada-002

# 3. Index your pattern catalogue (run once)
python ingest.py

# 4. Launch the app
streamlit run app.py
```

## Add New Patterns
Drop a new `.md` file into `/patterns/` and re-run `python ingest.py`.
No code changes needed.

## Project Structure
```
retail-pattern-advisor/
├── app.py                          ← Streamlit UI
├── chain.py                        ← LangChain RAG chain
├── ingest.py                       ← One-time vector store builder
├── doc_generator.py                ← Word doc generation
├── patterns/
│   ├── batch-servicebus.md
│   ├── realtime-eventhub.md
│   └── masterdata-servicebus-pubsub.md
├── vectorstore/                    ← auto-created by ingest.py
└── requirements.txt
```
