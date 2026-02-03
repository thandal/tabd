from mitmproxy import http
import os
import time
from dotenv import load_dotenv
from openai import OpenAI
from bs4 import BeautifulSoup, Comment
from readability_simplifier import ReadabilitySimplifier

load_dotenv()

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

# Initialize the simplifier
simplifier = ReadabilitySimplifier()

def simplify_html_readability(html_content, url=None):
    """Simplify HTML content using ReadabilitySimplifier."""
    try:
        result = simplifier.simplify(html_content, url=url)
        return result['content']
    except Exception as e:
        print(f"Readability simplification failed: {e}")
        return html_content

def simplify_html_ai(html_content):
    if not html_content:
        return "Error: No HTML content provided"
    
    # with open("debug_html_content.html", "w") as f:
    #     f.write(html_content)   

    # First, use rule-based simplification to reduce token count
    print(f"Original HTML content length: {len(html_content)}")
    # First, use readability simplification to reduce token count
    pre_simplified = simplify_html_rule_based(html_content)
    # pre_simplified = simplify_html_readability(html_content)
    # pre_simplified = html_content
    print(f"Pre-simplified HTML content length: {len(pre_simplified)}")

    # with open("debug_pre_simplified_html_content.html", "w") as f:
    #     f.write(pre_simplified)   

    prompt = f"""
    Below is the HTML content of a webpage. Your task is to rewrite it into a streamlined version.
    
    Rules:
    * Keep all meaningful text and links (hrefs).
    * Remove all ads, tracking scripts, and other non-content elements.
    * Include a <style> block with a simple, modern design (vibrant colors, clean typography, responsive layout).
    * Add links to wikipedia pages where applicable.
    * Return ONLY the complete HTML code starting with <!DOCTYPE html>.
    
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

    def response(self, flow: http.HTTPFlow):
        # We only want to simplify HTML responses
        content_type = flow.response.headers.get("Content-Type", "")
        
        if "text/html" in content_type:
            # Check if this is a request we should simplify 
            # (e.g., avoid modifying mitmproxy's own internal pages)
            if flow.request.pretty_host == "mitm.it":
                return

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
