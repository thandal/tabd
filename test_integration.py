import sys
import os
from unittest.mock import MagicMock

# Mock mitmproxy since it might not be installed in the environment where we run this test
sys.modules['mitmproxy'] = MagicMock()

import darkly_addon

def test_integration():
    html_content = """
    <html>
        <head><title>Test Article</title></head>
        <body>
            <nav>Menu</nav>
            <article>
                <h1>Article Title</h1>
                <p>This is the main content of the article.</p>
                <div class="ad">Advertisement</div>
            </article>
            <footer>Footer</footer>
        </body>
    </html>
    """
    
    # Test simplify_html_readability
    print("Testing simplify_html_readability...")
    simplified = darkly_addon.simplify_html_readability(html_content)
    print(f"Simplified content length: {len(simplified)}")
    assert "article" in simplified.lower()
    assert "Advertisement" not in simplified
    assert "Menu" not in simplified
    print("✅ simplify_html_readability passed")

    # Note: simplify_html_ai requires API keys, so we won't test it fully here
    # but we can check if it calls the right pre-simplification function
    print("Integration test complete.")

if __name__ == "__main__":
    try:
        test_integration()
    except Exception as e:
        print(f"❌ Test failed: {e}")
        sys.exit(1)
