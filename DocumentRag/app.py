"""
app.py
Streamlit UI — Retail Azure Integration Pattern Advisor
Run: streamlit run app.py
"""

import streamlit as st
import tempfile, os
from dotenv import load_dotenv
load_dotenv()
from chain import recommend_pattern
from doc_chain import generate_document_content
from doc_generator import generate_doc
from knowledge_loader import (
    build_vectorstore_from_uploads,
    extract_template_sections,
    SUPPORTED_TYPES,
)

# ── Page config ────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Azure Integration Advisor",
    page_icon="🔷",
    layout="wide"
)

st.title("🔷 Retail Azure Integration Advisor")
st.caption("Recommends integration patterns grounded in your uploaded knowledge base")

# ── Sidebar: credentials ───────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Configuration")
    st.success("✅ Credentials loaded from .env")
    st.caption(f"Endpoint: {os.environ.get('AZURE_OPENAI_ENDPOINT','not set')[:40]}...")
    st.caption(f"Model: {os.environ.get('AZURE_CHAT_DEPLOYMENT','not set')}")
    st.caption(f"Cosmos: {os.environ.get('COSMOS_ENDPOINT','not set')[:40]}...")
    st.divider()
    st.caption("To change credentials update your .env file and restart the app.")

# ══════════════════════════════════════════════════════════════════════════
# SECTION 1 — KNOWLEDGE BASE UPLOAD
# ══════════════════════════════════════════════════════════════════════════
st.subheader("1️⃣ Upload Knowledge Base")
st.caption(
    "Upload your company's CIS pattern documents and the standard interface "
    "architecture template. These ground the AI — it will only recommend "
    "patterns from what you upload."
)

col_kb, col_tmpl = st.columns(2)

with col_kb:
    st.markdown("**📂 CIS Pattern Documents**")
    st.caption(f"Supported: {', '.join(SUPPORTED_TYPES)}")
    uploaded_patterns = st.file_uploader(
        label="Upload pattern files",
        type=["pdf", "docx", "txt"],  # "md" temporarily disabled
        accept_multiple_files=True,
        help="Upload Azure Cloud Integration Service (CIS) pattern documents. "
             "Each file should describe one integration pattern.",
        label_visibility="collapsed",
    )
    if uploaded_patterns:
        for f in uploaded_patterns:
            st.success(f"✓ {f.name}  ({round(f.size/1024, 1)} KB)")

with col_tmpl:
    st.markdown("**📄 Interface Doc Template (.docx)**")
    st.caption("The output document will mirror this template's section structure")
    uploaded_template = st.file_uploader(
        label="Upload interface template",
        type=["docx"],
        accept_multiple_files=False,
        help="Upload your standard interface architecture document template. "
             "The generated spec will follow its exact headings and sections.",
        label_visibility="collapsed",
    )
    if uploaded_template:
        st.success(f"✓ {uploaded_template.name}  ({round(uploaded_template.size/1024, 1)} KB)")

# Index uploaded patterns into vector store
vectorstore_ready   = False
template_sections   = None

if uploaded_patterns:
    if st.button("📥 Index Knowledge Base", use_container_width=False):
        if not os.environ.get("AZURE_OPENAI_ENDPOINT"):
            st.error("AZURE_OPENAI_ENDPOINT missing in .env file.")
        else:
            with st.spinner("Embedding and indexing your pattern documents..."):
                try:
                    count = build_vectorstore_from_uploads(
                        uploaded_files=uploaded_patterns,
                    )
                    st.session_state["kb_indexed"] = True
                    st.success(f"✅ Indexed {count} chunks from {len(uploaded_patterns)} file(s) into Cosmos DB.")
                except Exception as e:
                    st.error(f"Indexing failed: {e}")

# Extract template sections if template uploaded
if uploaded_template:
    if "template_sections" not in st.session_state or st.session_state.get("last_template") != uploaded_template.name:
        with st.spinner("Reading template structure..."):
            uploaded_template.seek(0)
            sections = extract_template_sections(uploaded_template)
            st.session_state["template_sections"] = sections
            st.session_state["last_template"]     = uploaded_template.name

        if st.session_state["template_sections"]:
            with st.expander("📋 Detected template sections"):
                for s in st.session_state["template_sections"]:
                    indent = "　" * (s["level"] - 1)
                    st.markdown(f"{indent}**H{s['level']}** — {s['title']}")
        else:
            st.warning("No headings detected in template. Using default layout.")

st.divider()

# ══════════════════════════════════════════════════════════════════════════
# SECTION 2 — DESCRIBE THE INTEGRATION
# ══════════════════════════════════════════════════════════════════════════
st.subheader("2️⃣ Describe Your Integration")

col1, col2 = st.columns(2)

with col1:
    source = st.selectbox("Source System", [
        "REST API", "SFTP / File", "IoT Device",
        "POS Terminal", "Webhook", "Legacy Database"
    ])

with col2:
    targets = st.multiselect("Target System(s)", [
        "ERP (SAP/Oracle)", "Azure Data Lake",
        "Power BI", "eCommerce Platform",
        "Loyalty System", "Notification Service",
        "CRM", "Downstream API"
    ])

col3, col4 = st.columns(2)

with col3:
    frequency = st.radio("Data Frequency", [
        "Real-time (continuous)",
        "Scheduled batch (hourly/daily)",
        "Event-triggered"
    ])

with col4:
    volume = st.select_slider("Volume", options=[
        "Low (<1k/day)", "Medium (1k–100k/day)",
        "High (100k–1M/day)", "Very High (>1M/day)"
    ])

guarantee      = st.checkbox("Delivery guarantee required (no data loss)?", value=True)
multi_consumer = st.checkbox("Same data goes to multiple consumers?")

st.markdown("**Additional context for LLD generation**")
col5, col6 = st.columns(2)
with col5:
    interface_id = st.text_input(
        "Interface ID (optional)",
        placeholder="e.g. INT-POS-ADLS-BATCH-001"
    )
with col6:
    delivery_mode = st.radio("Delivery Mode", ["Async", "Sync", "Both"])

business_context = st.text_area(
    "Business Context / Requirement Summary",
    placeholder=(
        "e.g. Daily POS sales file from SFTP needs to be loaded into Azure Data Lake "
        "for analytics. Finance requires guaranteed delivery with no data loss."
    ),
    height=80,
)

st.divider()

# ══════════════════════════════════════════════════════════════════════════
# SECTION 3 — RECOMMEND
# ══════════════════════════════════════════════════════════════════════════
if st.button("🔍 Recommend Pattern", type="primary", use_container_width=True):

    if not targets:
        st.warning("Please select at least one target system.")
        st.stop()

    if not os.environ.get("AZURE_OPENAI_ENDPOINT"):
        st.error("AZURE_OPENAI_ENDPOINT missing in .env file.")
        st.stop()

    if not st.session_state.get("kb_indexed"):
        st.warning("No knowledge base indexed yet. Upload and index your CIS pattern documents in Section 1 first.")

    query = (
        f"Source: {source}. "
        f"Targets: {', '.join(targets)}. "
        f"Frequency: {frequency}. "
        f"Volume: {volume}. "
        f"Delivery guarantee needed: {guarantee}. "
        f"Multiple consumers: {multi_consumer}."
    )

    with st.spinner("Retrieving patterns and generating recommendation..."):
        try:
            result  = recommend_pattern(query)
            answer  = result["result"]
            sources = result["source_documents"]
        except Exception as e:
            st.error(f"Error calling model: {e}")
            st.stop()

    # Store in session so doc gen button works independently
    st.session_state["answer"]         = answer
    st.session_state["sources"]        = sources
    st.session_state["source"]         = source
    st.session_state["targets"]        = targets
    st.session_state["frequency"]      = frequency
    st.session_state["volume"]         = volume
    st.session_state["delivery_mode"]  = delivery_mode
    st.session_state["business_context"] = business_context
    st.session_state["interface_id"]   = interface_id

# ══════════════════════════════════════════════════════════════════════════
# SECTION 4 — OUTPUT (shown after recommendation)
# ══════════════════════════════════════════════════════════════════════════
if "answer" in st.session_state:
    answer    = st.session_state["answer"]
    sources   = st.session_state["sources"]
    source    = st.session_state["source"]
    targets   = st.session_state["targets"]
    frequency = st.session_state["frequency"]

    st.subheader("3️⃣ Recommended Pattern")
    st.success(answer)

    with st.expander("📚 Patterns retrieved from knowledge base"):
        for doc in sources:
            fname = doc.get("source_file", "pattern file")
            st.markdown(f"**Source:** `{fname}`")
            st.text(doc.get("text", "")[:400] + "...")

    st.divider()

    # ── Generate .docx ──────────────────────────────────────────────────
    st.subheader("4️⃣ Generate Interface Architecture Document")

    tmpl_sections = st.session_state.get("template_sections")

    if not tmpl_sections:
        st.warning(
            "⚠️ No interface template uploaded. "
            "Please upload your standard .docx template in Section 1 so the "
            "output document mirrors your company's structure."
        )
    else:
        st.info(
            f"📄 Sonnet will generate content for each of the "
            f"**{len(tmpl_sections)} sections** in your uploaded template, "
            f"grounded strictly on your CIS patterns."
        )

        # Show which input variables will be passed
        with st.expander("🔎 Variables being passed to AI"):
            st.json({
                "source":        source,
                "targets":       targets,
                "delivery":      "Async" if "batch" in frequency.lower() else "Sync/Async",
                "frequency":     frequency,
                "volume":        st.session_state.get("volume", "N/A"),
                "guarantee":     guarantee,
                "multi_consumer": multi_consumer,
                "template_sections": [s["title"] for s in tmpl_sections],
            })

        if st.button("🤖 Generate with AI (.docx)", type="primary", use_container_width=True):
            with st.spinner(
                "Sonnet is reading your CIS patterns and writing each section... "
                "This takes 20–40 seconds."
            ):
                try:
                    # Step 1: AI generates content for every section
                    section_content = generate_document_content(
                        source=source,
                        targets=targets,
                        delivery=st.session_state.get("delivery_mode", "Async"),
                        frequency=frequency,
                        volume=st.session_state.get("volume", "Medium"),
                        guarantee=guarantee,
                        multi_consumer=multi_consumer,
                        template_sections=tmpl_sections,
                        business_context=st.session_state.get("business_context", ""),
                        interface_id=st.session_state.get("interface_id", ""),
                    )

                    # Step 2: Writer puts AI content into .docx template structure
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
                        path = generate_doc(
                            source=source,
                            targets=targets,
                            frequency=frequency,
                            section_content=section_content,
                            template_sections=tmpl_sections,
                            output_path=tmp.name,
                            interface_id=st.session_state.get("interface_id", ""),
                        )

                    # Preview what was generated
                    with st.expander("📋 Preview generated section content"):
                        for title, content in section_content.items():
                            st.markdown(f"**{title}**")
                            if isinstance(content, dict):
                                preview = "\n".join(f"{k}: {v}" for k, v in content.items())
                            elif isinstance(content, list):
                                preview = "\n".join(str(item) for item in content)
                            else:
                                preview = str(content)
                            st.caption(preview[:300] + ("..." if len(preview) > 300 else ""))

                    with open(path, "rb") as f:
                        st.download_button(
                            label="⬇️ Download Interface Architecture Document",
                            data=f,
                            file_name=(
                                f"INT-{source.replace(' ','-').upper()[:6]}-"
                                f"{__import__('datetime').datetime.now().strftime('%Y%m%d')}-001.docx"
                            ),
                            mime=(
                                "application/vnd.openxmlformats-officedocument"
                                ".wordprocessingml.document"
                            ),
                            use_container_width=True,
                        )

                except Exception as e:
                    st.error(f"Document generation failed: {e}")