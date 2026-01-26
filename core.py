import os
import time
from dotenv import load_dotenv
from google import genai
from openai import OpenAI
from bs4 import BeautifulSoup, Comment

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

def simplify_html_ai(html_content, model_type=None):
    if not model_type:
        model_type = os.getenv('DEFAULT_AI_MODEL', 'gemini')

    if not html_content:
        return "Error: No HTML content provided"
    
    with open("debug_html_content.html", "w") as f:
        f.write(html_content)   
        
    # First, use rule-based simplification to reduce token count
    pre_simplified = simplify_html_rule_based(html_content)
    print(f"Pre-simplified HTML content length: {len(pre_simplified)}")

    with open("debug_pre_simplified_html_content.html", "w") as f:
        f.write(pre_simplified)   

    
    prompt = f"""
    You are a web design expert. Below is the HTML content of a webpage.
    Your task is to rewrite it into a compact, modern, and aesthetically pleasing version.
    
    Rules:
    * Keep all meaningful text and links (hrefs).
    * Remove all ads, tracking scripts, and other non-content elements.
    * Include a <style> block with a simple, modern design (vibrant colors, clean typography, responsive layout).
    * Scale all images to be no more than 50% of the window size.
    * Use semantic HTML5.
    * Return ONLY the complete HTML code starting with <!DOCTYPE html>.
    
    Content to transform:
    {pre_simplified}
    """
    
    start_time = time.time()
    try:
        if model_type == "gemini":
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                return "Error: GEMINI_API_KEY not found in .env"
            
            # Use gemini-2.0-flash for speed unless thinking is explicitly required
            model_name = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
            client = genai.Client(api_key=api_key)
            
            # If using gemini-3, we can configure thinking to be minimal for speed
            config = None
            if "gemini-3" in model_name:
                config = {"thinking_config": {"include_thoughts": False}}
            
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=config
            )
            text = response.text
            
        elif model_type == "openai":
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                return "Error: OPENAI_API_KEY not found in .env"
            client = OpenAI(api_key=api_key)
            
            model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
            response = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}]
            )
            text = response.choices[0].message.content
            
        else:
            return "Error: Unsupported model type"
        
        duration = time.time() - start_time
        print(f"--- AI Generation ({model_name}) took {duration:.2f}s ---")
        
        if "```html" in text:
            text = text.split("```html")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        return text.strip()

    except Exception as e:
        return f"Error during AI processing: {str(e)}"
