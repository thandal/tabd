import ipaddress
import os
import socket
from urllib.parse import urljoin, urlsplit
from dotenv import load_dotenv
from flask import Flask, render_template, request, Response, jsonify
import requests
from darkly_addon import simplify_html_stream

load_dotenv()

app = Flask(__name__)

USER_AGENT = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
              '(KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36')
FETCH_TIMEOUT = 20
MAX_REDIRECTS = 5


class BlockedURL(Exception):
    """The requested URL is not one we are willing to fetch on a caller's behalf."""


def _check_url_allowed(url):
    """Reject anything but public http(s). Raises BlockedURL.

    This server is an open, unauthenticated fetcher, so without these checks
    /proxy?url=http://169.254.169.254/... turns it into an SSRF gadget against
    whatever the host can reach (cloud metadata, localhost, LAN).
    """
    parts = urlsplit(url)
    if parts.scheme not in ('http', 'https'):
        raise BlockedURL(f"Unsupported scheme: {parts.scheme or '(none)'}")

    host = parts.hostname
    if not host:
        raise BlockedURL("URL has no host")

    port = parts.port or (443 if parts.scheme == 'https' else 80)
    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as e:
        raise BlockedURL(f"Cannot resolve {host}: {e}")

    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global:
            raise BlockedURL(f"Refusing to fetch non-public address {ip} ({host})")


def fetch_page(url):
    """Fetch url, validating every hop. Returns (response, final_url).

    Redirects are followed manually because requests would otherwise happily
    follow a public URL's 302 into a private address, bypassing the check above.
    """
    for _ in range(MAX_REDIRECTS + 1):
        _check_url_allowed(url)
        response = requests.get(url, headers={'User-Agent': USER_AGENT},
                                timeout=FETCH_TIMEOUT, allow_redirects=False)
        if response.is_redirect or response.is_permanent_redirect:
            location = response.headers.get('Location')
            response.close()
            if not location:
                raise BlockedURL("Redirect without a Location header")
            url = urljoin(url, location)
            continue
        response.raise_for_status()
        return response, url
    raise BlockedURL(f"Exceeded {MAX_REDIRECTS} redirects")


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/proxy')
async def proxy():
    url = request.args.get('url')

    if not url:
        return "No URL provided", 400

    dest = request.headers.get('Sec-Fetch-Dest')
    purpose = request.headers.get('Sec-Purpose', request.headers.get('Purpose', ''))
    print(f"/proxy dest={dest or '-'} purpose={purpose or '-'} url={url}")

    if 'prefetch' in purpose.lower():
        # Speculative fetch: refuse before spending anything. Browsers discard
        # failed prefetches and re-request normally on a real navigation.
        return "Prefetch declined", 503

    # Bare input like "example.com" or "example.com:8080/x" gets a default scheme.
    # Anything that already names a scheme keeps it, so _check_url_allowed can reject it.
    if '://' not in url:
        url = 'https://' + url

    try:
        # Follow redirects ourselves so each hop is checked against the allowlist.
        response, url = fetch_page(url)

        content_type = response.headers.get('Content-Type', '')

        # If not HTML, return as is (binary content)
        if 'text/html' not in content_type:
            return Response(response.content, mimetype=content_type)

        # Browsers label what each request is for (Sec-Fetch-Dest). Only a
        # navigation earns a generation call: HTML requested as a subresource
        # (an <img> whose id mapped to a page, an extension scanning links)
        # would otherwise burn a full LLM run per request. Refusing outright
        # also avoids serving third-party HTML raw from our origin, where an
        # <object>/<embed> subresource would execute it same-origin.
        if dest not in (None, 'document', 'iframe', 'frame'):
            return "HTML is only simplified for navigations", 415

        html_content = response.text

        # Use AI to simplify the HTML and stream the response
        def generate():
            import asyncio
            import queue
            import threading
            
            q = queue.Queue()
            
            def run_loop():
                async def fetch():
                    try:
                        async for chunk in simplify_html_stream(html_content, url, "/proxy?url="):
                            q.put(chunk)
                    except Exception as e:
                        q.put(f"Error streaming: {str(e)}")
                    finally:
                        q.put(None)
                
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(fetch())
                finally:
                    loop.run_until_complete(loop.shutdown_asyncgens())
                    loop.close()
                
            threading.Thread(target=run_loop, daemon=True).start()
            
            while True:
                chunk = q.get()
                if chunk is None:
                    break
                yield chunk
                
        return Response(generate(), mimetype='text/html')
            
    except BlockedURL as e:
        return f"Blocked: {str(e)}", 403
    except requests.RequestException as e:
        return f"Error fetching page: {str(e)}", 502
    except Exception as e:
        return f"Error processing page: {str(e)}", 500

@app.route('/api/instructions', methods=['GET', 'POST'])
def handle_instructions():
    import darkly_addon
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        new_instructions = data.get('instructions')
        if not isinstance(new_instructions, str) or not new_instructions:
            return jsonify({"status": "error", "message": "No instructions provided"}), 400

        darkly_addon.save_instructions(new_instructions)
        darkly_addon.current_instructions = new_instructions
        return jsonify({"status": "success"})
            
    return jsonify({
        "instructions": darkly_addon.load_instructions(),
        "default": darkly_addon.DEFAULT_INSTRUCTIONS
    })

if __name__ == '__main__':
    # debug must stay off by default: the Werkzeug debugger exposes an interactive
    # console (and the API keys in os.environ) to anyone who can trigger a traceback.
    # Only enable it when bound to a trusted interface.
    debug = os.getenv("DARKLY_DEBUG", "").lower() in ("1", "true", "yes")
    host = os.getenv("DARKLY_HOST", "0.0.0.0")
    port = int(os.getenv("DARKLY_PORT", "5337"))
    app.run(host=host, debug=debug, port=port)
