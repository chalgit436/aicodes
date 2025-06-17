import chainlit as cl
import requests

# Config - replace with your actual values
USE_CASE_ID = "your-use-case-id"
SEARCH_API_URL = "https://your-server/search"
LLM_API_URL = "https://your-apigee-endpoint/llm"
HEADERS = {
    "use-case-id": USE_CASE_ID,
    "Content-Type": "application/json",
    # Add auth headers here if needed, e.g.
    # "Authorization": "Bearer your_token",
}

def search_context(user_prompt: str) -> str:
    payload = {"query": user_prompt}
    resp = requests.post(SEARCH_API_URL, json=payload, headers=HEADERS)
    resp.raise_for_status()
    results = resp.json()
    contexts = [doc.get("text", "") for doc in results.get("documents", [])]
    return "\n".join(contexts)

def generate_jira_story(context: str, user_prompt: str) -> str:
    prompt = (
        f"Based on the following API specification context:\n{context}\n\n"
        f"Write a detailed Jira user story in Gherkin format for the request:\n{user_prompt}\n"
        "Include acceptance criteria, priority, and subtasks."
    )
    payload = {"prompt": prompt}
    resp = requests.post(LLM_API_URL, json=payload, headers=HEADERS)
    resp.raise_for_status()
    llm_response = resp.json()
    jira_story = llm_response.get("generated_text") or llm_response.get("text") or ""
    return jira_story.strip()

@cl.on_message
async def main(message: str):
    await cl.Message("🔎 Searching context...").send()
    try:
        context = search_context(message)
        if not context:
            await cl.Message("⚠️ No relevant context found for your prompt.").send()
            return

        await cl.Message("🤖 Generating Jira story...").send()
        jira_story = generate_jira_story(context, message)

        await cl.Message(f"📝 Here is your generated Jira story:\n\n{jira_story}").send()
    except requests.HTTPError as e:
        await cl.Message(f"❌ API request failed: {e}").send()
    except Exception as e:
        await cl.Message(f"❌ Unexpected error: {e}").send()
