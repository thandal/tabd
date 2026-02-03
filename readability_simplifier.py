import requests
from readability import Document
from lxml import html
from lxml.html.clean import Cleaner

class ReadabilitySimplifier:
    def __init__(self, sanitize=True):
        self.sanitize = sanitize
        if sanitize:
            # Configure a basic cleaner to remove scripts, styles, etc.
            self.cleaner = Cleaner(
                scripts=True,
                javascript=True,
                comments=True,
                style=True,
                links=False,  # Keep links
                meta=True,
                page_structure=False, # Keep body/div etc
                processing_instructions=True,
                embedded=True,
                frames=True,
                forms=True,
                annoying_tags=True,
                remove_tags=['header', 'footer', 'nav', 'aside']
            )
        else:
            self.cleaner = None

    def fetch(self, url, headers=None):
        """Fetch HTML content from a URL."""
        if headers is None:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.text

    def simplify(self, html_content, url=None):
        """
        Simplify HTML content into a clean article structure using readability-lxml.
        Returns a dictionary with 'title' and 'content'.
        """
        doc = Document(html_content, url=url)
        title = doc.title()
        summary = doc.summary()

        if self.sanitize:
            # Clean the extracted summary
            summary_root = html.fromstring(summary)
            cleaned_summary = self.cleaner.clean_html(summary_root)
            # lxml.html.tostring includes wrap tags (like <div>), we might want to keep them or just the inner
            summary = html.tostring(cleaned_summary, encoding='unicode')

        return {
            'title': title,
            'content': summary
        }

    def simplify_url(self, url):
        """Fetch and then simplify a URL."""
        html_content = self.fetch(url)
        return self.simplify(html_content, url=url)

# Example usage:
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        target_url = sys.argv[1]
        simplifier = ReadabilitySimplifier()
        try:
            result = simplifier.simplify_url(target_url)
            print(f"Title: {result['title']}")
            print("-" * 20)
            print(result['content'][:500] + "...")
        except Exception as e:
            print(f"Error simplifying {target_url}: {e}")
    else:
        print("Usage: python3 readability_simplifier.py <url>")
