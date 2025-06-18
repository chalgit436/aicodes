import chainlit as cl
import yaml
import json
import io
import aiohttp # Required for making async API calls

@cl.on_chat_start
async def start():
    """
    Initializes the Chainlit application with a welcome message.
    """
    await cl.Message(
        content=(
            "**Welcome to the multi-purpose chat!**\n\n"
            "1. **YAML to JSONL**: Upload a YAML file to convert it.\n"
            "2. **Chat with AI**: Type any message to get a response from the language model."
        )
    ).send()

@cl.on_message
async def main(message: cl.Message):
    """
    Handles incoming messages and file uploads. Routes to the appropriate function.
    """
    # Priority 1: Check for file uploads for conversion
    if message.elements:
        for element in message.elements:
            # Check if the uploaded file is a YAML or a plain text file
            if "yaml" in element.mime or "plain" in element.mime:
                await process_file(element)
                return # Stop further processing

    # Priority 2: If no files, check for a text prompt for the LLM
    if message.content:
        await call_llm(message.content)
        return # Stop further processing

    # Fallback: If message is empty and no file, ask for input
    await cl.Message(content="Please send a message or upload a YAML file.").send()


async def call_llm(prompt: str):
    """
    Sends a prompt to the Gemini LLM and streams the response back to the user.
    """
    msg = cl.Message(content="")
    await msg.send()

    # Gemini API details
    api_key = "" # This will be handled by the execution environment.
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
    
    payload = {
        "contents": [{
            "role": "user",
            "parts": [{"text": prompt}]
        }]
    }
    
    headers = {'Content-Type': 'application/json'}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    # Extract the text from the API response
                    text_response = data['candidates'][0]['content']['parts'][0]['text']
                    await msg.stream_token(text_response)
                else:
                    error_text = await response.text()
                    await cl.ErrorMessage(content=f"API Error: {response.status} - {error_text}").send()

    except Exception as e:
        await cl.ErrorMessage(content=f"An unexpected error occurred while contacting the LLM: {e}").send()
    
    await msg.update()


async def process_file(uploaded_file: cl.File):
    """
    Processes the uploaded YAML file and sends back the JSONL result.

    Args:
        uploaded_file: The file element uploaded by the user.
    """
    processing_msg = cl.Message(content=f"Processing `{uploaded_file.name}`...")
    await processing_msg.send()

    try:
        file_content = uploaded_file.content.decode("utf-8")
        jsonl_content, num_documents = convert_yaml_to_jsonl(file_content)
        jsonl_buffer = io.BytesIO(jsonl_content.encode('utf-8'))

        await processing_msg.update(
            content=f"Successfully converted `{uploaded_file.name}` to JSONL. It contains {num_documents} JSON objects."
        )

        elements = [
            cl.File(
                name=f"{uploaded_file.name.split('.')[0]}_converted.jsonl",
                content=jsonl_buffer.getvalue(),
                display="inline",
            )
        ]
        
        await cl.Message(
            content="You can now download the converted JSONL file.",
            elements=elements,
        ).send()

    except yaml.YAMLError as e:
        await cl.ErrorMessage(content=f"Error parsing the YAML file: {e}").send()
    except Exception as e:
        await cl.ErrorMessage(content=f"An unexpected error occurred: {e}").send()


def convert_yaml_to_jsonl(yaml_string: str) -> tuple[str, int]:
    """
    Converts a string containing YAML data to a JSONL formatted string.
    """
    try:
        documents = [doc for doc in yaml.safe_load_all(yaml_string) if doc is not None]
        jsonl_lines = [json.dumps(doc) for doc in documents]
        return "\n".join(jsonl_lines), len(documents)
    except yaml.YAMLError as e:
        raise e

# To run this application:
# 1. Make sure you have python installed.
# 2. Install the required libraries: pip install chainlit pyyaml aiohttp
# 3. Save this code as a Python file (e.g., `app.py`).
# 4. Run the app from your terminal: chainlit run app.py -w
