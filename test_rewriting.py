from darkly_addon import rewrite_links

def test_rewrite_links():
    html_content = """
    <html>
        <body>
            <a href="https://example.com/page1">Link 1</a>
            <img src="https://example.com/image1.jpg">
        </body>
    </html>
    """
    base_url = "https://example.com/"
    proxy_prefix = "/proxy?url="
    
    rewritten = rewrite_links(html_content, base_url, proxy_prefix)
    print(rewritten)
    
    assert "/proxy?url=https%3A//example.com/page1" in rewritten
    assert "/proxy?url=https%3A//example.com/image1.jpg" in rewritten
    print("Test passed!")

if __name__ == "__main__":
    test_rewrite_links()
