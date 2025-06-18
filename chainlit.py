You are a product owner creating Jira stories based on product specifications and requirements.

Your task is to write a complete Jira story in Gherkin format that includes:

1. **Title**: A short and descriptive summary of the feature or enhancement.
2. **Summary / Description**: A clear explanation of the goal and context.
3. **Epic**: The higher-level category or initiative this story belongs to.
4. **Priority**: Choose from: Highest, High, Medium, Low.
5. **Labels**: Relevant tags or modules.
6. **Subtasks**: List any smaller steps or engineering tasks.
7. **Acceptance Criteria**: Written in Gherkin format using `Given`, `When`, and `Then`.

Use any provided documentation context and the user prompt to ensure the story is relevant, scoped, and implementation-ready.





import chainlit as cl
import requests
import json
import yaml
import io

# --- Helpers ---
def convert_to_jsonl(file_bytes, filename):
    ext = filename.split(".")[-1].lower()
    if ext in ("yaml", "yml"):
        data = yaml.safe_load(file_bytes.decode("utf-8"))
    else:
        data = json.loads(file_bytes.decode("utf-8"))
    if isinstance(data, dict):
        data = [data]
    jsonl_data = "\n".join(json.dumps(record) for record in data)
    return io.BytesIO(jsonl_data.encode("utf-8"))

def upload_file(jsonl_file, original_filename):
    response = requests.post(
        "https://your-server/upload",
        files={"file": (original_filename.rsplit(".", 1)[0] + ".jsonl", jsonl_file)},
    )
    response.raise_for_status()
    return response.json().get("file_id")

def trigger_ingest(file_id):
    response = requests.post("https://your-server/ingest", json={"file_id": file_id})
    response.raise_for_status()
    return response.json().get("use_case_id")

def search_context(prompt, headers):
    response = requests.post("https://your-server/search", json={"query": prompt}, headers=headers)
    response.raise_for_status()
    return response.json().get("context", "")

def query_llm(final_prompt, headers):
    response = requests.post("https://your-apigee-llm-endpoint", json={"prompt": final_prompt}, headers=headers)
    response.raise_for_status()
    return response.json().get("output", "")

def create_jira_story(story_text, headers):
    response = requests.post("https://your-jira-api/create", json={"story": story_text}, headers=headers)
    return response.status_code == 201

# --- Chainlit App Start ---
@cl.on_chat_start
async def start():
    # Step 1: Ask for file
    files = await cl.AskFileMessage(
        content="📎 Upload Swagger or Figma file (JSON/YAML) to begin.",
        accept={"application/json": [".json"], "application/x-yaml": [".yaml", ".yml"]},
    ).send()

    file = files[0]
    jsonl_file = convert_to_jsonl(file.content, file.name)

    # Step 2: Upload and Ingest
    file_id = upload_file(jsonl_file, file.name)
    use_case_id = trigger_ingest(file_id)
    headers = {"use-case-id": use_case_id}
    cl.user_session.set("headers", headers)

    await cl.Message(f"✅ File `{file.name}` uploaded and ingested.").send()

    # Step 3: Ask for user prompt
    prompt = await cl.AskUserMessage("💬 What kind of Jira story do you want to generate? (e.g., 'checkout API for merchants')").send()

    await generate_story(prompt.content, headers)

# --- Handle user messages ---
@cl.on_message
async def on_message(message: cl.Message):
    headers = cl.user_session.get("headers")
    if not headers:
        await cl.Message("⚠️ Please upload a file first.").send()
        return

    if message.content.strip().lower() == "submit":
        story = cl.user_session.get("pending_story", "")
        success = create_jira_story(story, headers)
        await cl.Message("✅ Jira story created!" if success else "❌ Failed to create Jira story.").send()
    else:
        await generate_story(message.content, headers)

# --- Generate story using prompt + RAG ---
async def generate_story(user_prompt, headers):
    context = search_context(user_prompt, headers)

    final_prompt = f"""
You are a product owner writing Jira stories in Gherkin format.

Context:
{context}

Feature: <feature name>

As a <type of user>
I want to <perform some action>
So that <I can achieve some goal>

Scenario: <scenario name>
Given <some context>
When <some action is carried out>
Then <this is the expected outcome>

Acceptance Criteria:
- <list of conditions to be met>

Also include:
- Epic
- Labels
- Priority
- Any subtasks (if applicable)

User Prompt:
{user_prompt}
"""

    story = query_llm(final_prompt, headers)
    cl.user_session.set("pending_story", story)

    await cl.Message(
        f"📝 **Preview Jira Story:**\n\n{story}\n\n✅ Type `submit` to create the Jira ticket or modify your prompt."
    ).send()
