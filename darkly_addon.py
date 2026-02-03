from mitmproxy import http
import os
import time
from dotenv import load_dotenv
from openai import OpenAI
from bs4 import BeautifulSoup, Comment

load_dotenv()

DEFAULT_INSTRUCTIONS = """* Keep all meaningful text and links (hrefs).
* Remove all ads, tracking scripts, and other non-content elements.
* Include a <style> block with a simple, modern design (vibrant colors, clean typography, responsive layout).
* Add links to wikipedia pages where applicable.
* Return ONLY the complete HTML code starting with <!DOCTYPE html>."""

# GLOBAL STATE for instructions (can be overridden by http://dark.ly)
INSTRUCTIONS_FILE = "ai_instructions.txt"

def load_instructions():
    if os.path.exists(INSTRUCTIONS_FILE):
        with open(INSTRUCTIONS_FILE, "r") as f:
            return f.read()
    return DEFAULT_INSTRUCTIONS

def save_instructions(instructions):
    with open(INSTRUCTIONS_FILE, "w") as f:
        f.write(instructions)

current_instructions = load_instructions()

def simplify_html_rule_based(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # List of tags to remove entirely
    strip_tags = [
        'script', 'style', 'noscript', 'iframe', 'svg', 'canvas', 
        'video', 'audio', 'picture', 'source', 'object', 'embed'
    ]
    for tag in soup(strip_tags):
        tag.decompose()
        
    # Simplify the structure
    for tag in soup.find_all(True):
        # Keep only basic attributes for a few tags
        if tag.name == 'a':
            href = tag.get('href')
            tag.attrs = {'href': href} if href else {}
        elif tag.name == 'img':
            src = tag.get('src')
            alt = tag.get('alt', '')
            tag.attrs = {'src': src, 'alt': alt} if src else {}
        else:
            # Strip all attributes from other tags
            tag.attrs = {}
            
    # Remove comments
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()

    return soup.prettify()

def simplify_html_ai(html_content, instructions=None):
    if not html_content:
        return "Error: No HTML content provided"
    
    # Use provided instructions or fallback to current global state
    ai_instructions = instructions or current_instructions
    
    print(f"Original HTML content length: {len(html_content)}")

    # First, use rule-based simplification to reduce token count
    pre_simplified = simplify_html_rule_based(html_content)
    print(f"Pre-simplified HTML content length: {len(pre_simplified)}")

    prompt = f"""
    Below is the HTML content of a webpage. Your task is to rewrite it into a streamlined version.
    
    Rules:
    {ai_instructions}
    
    Content to transform:
    {pre_simplified}
    """
    
    start_time = time.time()
    model_provider = os.getenv("AI_PROVIDER")
    if model_provider == "cerebras":
        api_key = os.getenv("CEREBRAS_API_KEY")
        base_url = "https://api.cerebras.ai/v1"
        model_name = os.getenv("CEREBRAS_MODEL")
    elif model_provider== "gemini":
        api_key = os.getenv("GEMINI_API_KEY")
        base_url = "https://generativelanguage.googleapis.com/v1beta/openai"
        model_name = os.getenv("GEMINI_MODEL")
    elif model_provider == "groq":
        api_key = os.getenv("GROQ_API_KEY")
        base_url="https://api.groq.com/openai/v1"
        model_name = os.getenv("GROQ_MODEL")
    elif model_provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        base_url = "https://api.openai.com/v1"
        model_name = os.getenv("OPENAI_MODEL")
    else:
        return "Error: Unsupported model type"

    client = OpenAI(api_key=api_key, base_url=base_url)
    response = client.chat.completions.create(
        model=model_name,
        messages=[{"role": "user", "content": prompt}]
    )
    text = response.choices[0].message.content
    
    duration = time.time() - start_time
    print(f"--- AI Generation ({model_name}) took {duration:.2f}s ---")
    
    if "```html" in text:
        text = text.split("```html")[1].split("```")[0]
    elif "```" in text:
        text = text.split("```")[1].split("```")[0]
    return text.strip()

class DarklyAddon:
    def __init__(self):
        print("Darkly Proxy Addon Loaded")
        print("Control Panel available at http://dark.ly")

    def request(self, flow: http.HTTPFlow):
        if flow.request.pretty_host == "dark.ly":
            if flow.request.method == "POST":
                # Save instructions
                try:
                    form_data = flow.request.multipart_form or flow.request.urlencoded_form
                    new_instructions = form_data.get("instructions")
                    action = form_data.get("action")
                    
                    global current_instructions
                    if action == "reset":
                        current_instructions = DEFAULT_INSTRUCTIONS
                    elif new_instructions:
                        current_instructions = new_instructions
                    
                    save_instructions(current_instructions)
                    print(f"Instructions updated/reset.")
                    
                    # Redirect back to home after saving
                    flow.response = http.Response.make(
                        302, 
                        b"", 
                        {
                            "Location": "/",
                            "Set-Cookie": f"darkly_instructions={current_instructions.encode('utf-8').hex()}; Path=/; Max-Age=31536000"
                        }
                    )
                except Exception as e:
                    flow.response = http.Response.make(500, f"Error saving: {str(e)}".encode(), {"Content-Type": "text/plain"})
                return

            # GET / - Show editor
            html_page = f"""
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Through a Browser, Darkly - Config</title>
                <link rel="preconnect" href="https://fonts.googleapis.com">
                <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
                <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600&family=JetBrains+Mono&display=swap" rel="stylesheet">
                <style>
                    :root {{
                        --primary: #737373;
                        --bg: #171717;
                        --card: #262626;
                        --text: #f5f5f5;
                        --text-dim: #a3a3a3;
                    }}
                    body {{
                        font-family: 'Outfit', sans-serif;
                        background-color: var(--bg);
                        color: var(--text);
                        margin: 0;
                        display: flex;
                        justify-content: center;
                        align-items: center;
                        min-height: 100vh;
                        overflow: hidden;
                    }}
                    .container {{
                        background: var(--card);
                        padding: 2.5rem;
                        border-radius: 1.5rem;
                        box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
                        width: 100%;
                        max-width: 700px;
                        border: 1px solid rgba(255, 255, 255, 0.05);
                        backdrop-filter: blur(10px);
                        animation: slideIn 0.6s ease-out;
                    }}
                    @keyframes slideIn {{
                        from {{ opacity: 0; transform: translateY(20px); }}
                        to {{ opacity: 1; transform: translateY(0); }}
                    }}
                    h1 {{
                        font-weight: 600;
                        margin-top: 0;
                        font-size: 1.875rem;
                        color: var(--text);
                        margin-bottom: 0.5rem;
                    }}
                    p {{ color: var(--text-dim); margin-bottom: 2rem; }}
                    textarea {{
                        width: 100%;
                        height: 300px;
                        background: #171717;
                        border: 2px solid #404040;
                        border-radius: 0.75rem;
                        color: #e5e5e5;
                        font-family: 'JetBrains Mono', monospace;
                        padding: 1rem;
                        font-size: 0.9rem;
                        resize: none;
                        box-sizing: border-box;
                        transition: border-color 0.2s;
                        margin-bottom: 1.5rem;
                    }}
                    textarea:focus {{
                        outline: none;
                        border-color: var(--primary);
                        box-shadow: 0 0 0 4px rgba(255, 255, 255, 0.05);
                    }}
                    .btn {{
                        background: #404040;
                        color: white;
                        border: none;
                        padding: 0.75rem 2rem;
                        border-radius: 0.75rem;
                        font-weight: 600;
                        cursor: pointer;
                        font-family: inherit;
                        transition: all 0.2s;
                        width: 100%;
                        font-size: 1rem;
                    }}
                    .btn:hover {{
                        transform: translateY(-2px);
                        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.3);
                        background: #525252;
                    }}
                    .btn:active {{ transform: translateY(0); }}
                    .btn-secondary {{
                        background: #262626;
                        border: 1px solid #404040;
                    }}
                    .btn-secondary:hover {{
                        background: #333333;
                        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.3);
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>Darkly Config</h1>
                    <p>Edit the instructions used by the AI to simplify web pages.</p>
                    <form action="/" method="POST">
                        <textarea name="instructions">{current_instructions}</textarea>
                        <div style="display: flex; gap: 1rem;">
                            <button type="submit" name="action" value="save" class="btn">Save Instructions</button>
                            <button type="submit" name="action" value="reset" class="btn btn-secondary">Reset to Defaults</button>
                        </div>
                    </form>
                </div>
            </body>
            </html>
            """
            flow.response = http.Response.make(200, html_page.encode(), {"Content-Type": "text/html"})
            return

    def response(self, flow: http.HTTPFlow):
        # We only want to simplify HTML responses
        content_type = flow.response.headers.get("Content-Type", "")
        
        # Check if this is a request we should simplify 
        # (e.g., avoid modifying mitmproxy's own internal pages)
        if "text/html" in content_type and flow.request.pretty_host != "dark.ly" and flow.request.pretty_host != "mitm.it":
            print(f"Simplifying: {flow.request.pretty_url}")
            try:
                # Decompress the response if needed
                flow.response.decode()
                
                html_content = flow.response.get_text()
                
                # Apply AI simplification
                simplified_html = simplify_html_ai(html_content)
                
                if simplified_html and not simplified_html.startswith("Error"):
                    flow.response.set_text(simplified_html)
                    # Update headers to reflect modification
                    flow.response.headers["Content-Length"] = str(len(flow.response.raw_content))
                    flow.response.headers["x-darkly"] = "true"
                else:
                    flow.response.set_text(f"Skipping simplification for {flow.request.pretty_url}: {simplified_html}...")
            except Exception as e:
                flow.response.set_text(f"Failed to simplify {flow.request.pretty_url}: {str(e)}")

addons = [
    DarklyAddon()
]
