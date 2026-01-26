from mitmproxy import http
from core import simplify_html_ai
import os

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
                model_type = os.getenv("DEFAULT_AI_MODEL", "gemini")
                simplified_html = simplify_html_ai(html_content, model_type=model_type)
                
                if simplified_html and not simplified_html.startswith("Error"):
                    flow.response.set_text(simplified_html)
                    # Update headers to reflect modification
                    flow.response.headers["Content-Length"] = str(len(flow.response.raw_content))
                    flow.response.headers["X-Darkly-Simplified"] = "true"
                else:
                    flow.response.set_text(f"Skipping simplification for {flow.request.pretty_url}: {simplified_html}...")
            except Exception as e:
                flow.response.set_text(f"Failed to simplify {flow.request.pretty_url}: {str(e)}")

addons = [
    DarklyAddon()
]
