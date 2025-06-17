# rag_jira_chainlit/app.py
import chainlit as cl
import requests
import json
import io
import yaml

BACKEND_BASE = "https://your-server.com"           # Change this
LLM_API = "https://your-apigee-llm.com/generate"   # Change this
JIRA_API = "https://your-jira.com/api/create"      # Change this

def convert_to_jsonl(file_bytes, filename):
    ext = filename.split(".")[-1].lower()
    data = yaml.safe_load(file_bytes.decode("utf-8")) if ext in ["yaml", "yml"] else json.loads(file_bytes.decode("utf-8"))
    if isinstance(data, dict):
        data = [data]
    jsonl_str = "\n".join(json.dumps(row) for row in data)
    return io.BytesIO(jsonl_str.encode("utf-8"))

@cl.on_chat_start
async def start():
    cl.user_session.set("use_case_id", "")
    await cl.Message("📂 Please upload a file to begin.").send()

    file_msg = await cl.AskFileMessage("Upload Swagger or Figma JSON/YAML file.", accept=["application/json", ".yaml", ".yml"]).send()
    file = file_msg.files[0]

    jsonl_file = convert_to_jsonl(file.content, file.name)

    upload_resp = requests.post(
        f"{BACKEND_BASE}/upload",
        files={"file": (file.name.replace(".yaml", ".jsonl"), jsonl_file)}
    )
    file_id = upload_resp.json().get("file_id")

    ingest_resp = requests.post(f"{BACKEND_BASE}/ingest", json={"file_id": file_id})
    use_case_id = ingest_resp.json().get("use_case_id")

    cl.user_session.set("use_case_id", use_case_id)
    await cl.Message(f"✅ File uploaded and ingested! Use-case ID: {use_case_id}. Now enter your prompt.").send()

@cl.on_message
async def prompt_llm(message: cl.Message):
    content = message.content.strip()
    use_case_id = cl.user_session.get("use_case_id")

    if content.lower() == "submit":
        story = cl.user_session.get("pending_story")
        if not story:
            await cl.Message("No story to submit. Please generate one first.").send()
            return

        jira_resp = requests.post(
            JIRA_API,
            json={"story": story},
            headers={"use-case-id": use_case_id} if use_case_id else {}
        )
        if jira_resp.status_code == 201:
            await cl.Message("Jira story created successfully!").send()
        else:
            await cl.Message(f"❌ Failed to create Jira story.\n{jira_resp.text}").send()
        return

    if not use_case_id:
        await cl.Message("⚠️ No file uploaded and no use-case ID provided. Please upload or configure a use-case ID.").send()
        return

    search_resp = requests.post(
        f"{BACKEND_BASE}/search",
        json={"query": content},
        headers={"use-case-id": use_case_id}
    )
    context = search_resp.json().get("context", "")

    final_prompt = f"""
You are a product owner writing Jira stories in Gherkin format.

Context:
{context}

Prompt:
{content}

Write:
- Title
- Description
- Epic
- Labels
- Priority
- Subtasks
- Gherkin-formatted Acceptance Criteria
"""

    llm_resp = requests.post(
        LLM_API,
        json={"prompt": final_prompt},
        headers={"use-case-id": use_case_id}
    )
    story = llm_resp.json().get("output", "⚠️ No story generated.")
    cl.user_session.set("pending_story", story)

    await cl.Message(f"📝 **Preview Jira Story:**\n\n{story}\n\n✅ Type `submit` to create the Jira ticket or enter a new prompt.").send()
