"""Compare LLM models on the Darkly HTML-munging task.

Usage:
    python_env/bin/python darkly_compare.py [URL ...]

Saves outputs to comparison/{slug}/{label}.html and prints a timing summary.
The "kept" column is the fraction of the condensed input text that survives into
the model's output -- the number to watch for models that silently drop content.
"""
import asyncio
import os
import re
import sys
import time
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

import darkly_addon

# Providers retire model ids without notice -- qwen-3-235b and llama-4-scout both
# 404'd as of 2026-07-24. Check /v1/models before assuming a failure is a bug.
CONFIGS = [
    ("cerebras_gpt-oss-120b", {
        "AI_PROVIDER": "cerebras",
        "CEREBRAS_MODEL": "gpt-oss-120b",
    }),
    ("cerebras_zai-glm-4.7", {
        "AI_PROVIDER": "cerebras",
        "CEREBRAS_MODEL": "zai-glm-4.7",
    }),
    ("groq_gpt-oss-120b", {
        "AI_PROVIDER": "groq",
        "GROQ_MODEL": "openai/gpt-oss-120b",
    }),
    ("groq_llama-3.3-70b", {
        "AI_PROVIDER": "groq",
        "GROQ_MODEL": "llama-3.3-70b-versatile",
    }),
]

DEFAULT_URLS = [
    "https://news.ycombinator.com",
    "https://slashdot.org",
    "https://www.bbc.com/news",
]

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36")


def slugify(url):
    p = urlparse(url)
    s = (p.netloc + p.path).replace("/", "_").strip("_")
    return s or "root"


def absolutize_urls(html, base_url):
    """Resolve relative href/src to absolute so the saved file works in a browser."""
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.find_all("a", href=True):
        a["href"] = urljoin(base_url, a["href"])
    for img in soup.find_all("img", src=True):
        img["src"] = urljoin(base_url, img["src"])
    return str(soup)


def visible_text(html):
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return re.sub(r"\s+", " ", soup.get_text(" ")).strip()


def fetch(url):
    r = requests.get(url, headers={"User-Agent": UA}, timeout=30)
    r.raise_for_status()
    return r.text


def apply_env(env):
    for k, v in env.items():
        os.environ[k] = v


async def _collect(html, base_url):
    """Drain simplify_html_stream into a single document."""
    parts = []
    async for chunk in darkly_addon.simplify_html_stream(html, base_url, ""):
        parts.append(chunk)
    return "".join(parts)


def run_one(label, env, html, base_url, out_dir):
    apply_env(env)
    t0 = time.time()
    try:
        # simplify_html_stream already absolutizes links when given a base_url.
        out = asyncio.run(_collect(html, base_url))
    except Exception as e:
        return None, time.time() - t0, 0, f"exception: {e}"
    elapsed = time.time() - t0
    if not out or out.startswith("Error"):
        return None, elapsed, 0, (out or "empty")
    path = os.path.join(out_dir, f"{label}.html")
    with open(path, "w") as f:
        f.write(out)
    return path, elapsed, len(visible_text(out)), None


def main():
    urls = sys.argv[1:] or DEFAULT_URLS
    os.makedirs("comparison", exist_ok=True)

    results = []
    for url in urls:
        slug = slugify(url)
        page_dir = os.path.join("comparison", slug)
        os.makedirs(page_dir, exist_ok=True)
        print(f"\n=== {url} ===")

        try:
            html = fetch(url)
        except Exception as e:
            print(f"  fetch failed: {e}")
            continue

        # The condensed text is what the model actually sees, so it is the fair
        # denominator for "how much content survived".
        condensed, mapping = darkly_addon.dom_to_condensed(html)
        baseline = len(visible_text(condensed))
        print(f"  fetched {len(html)} chars -> condensed {len(condensed)} chars, "
              f"{len(condensed.splitlines())} blocks, {len(mapping)} ids")

        with open(os.path.join(page_dir, "_original.html"), "w") as f:
            f.write(absolutize_urls(html, url))
        with open(os.path.join(page_dir, "_condensed.txt"), "w") as f:
            f.write(condensed)

        for label, env in CONFIGS:
            print(f"\n  --- {label} ---")
            path, elapsed, text_len, err = run_one(label, env, html, url, page_dir)
            kept = (text_len / baseline) if baseline else 0.0
            if err:
                print(f"    FAIL ({elapsed:.2f}s): {err[:200]}")
                results.append((url, label, elapsed, None, 0.0, err))
            else:
                size = os.path.getsize(path)
                print(f"    OK  {elapsed:.2f}s  {size} bytes  kept {kept:.0%}  -> {path}")
                results.append((url, label, elapsed, size, kept, None))

    print("\n\n=== SUMMARY ===")
    print(f"{'URL':<45} {'Model':<28} {'Time':>8} {'Bytes':>10} {'Kept':>6}")
    print("-" * 102)
    for url, label, elapsed, size, kept, err in results:
        t = f"{elapsed:.2f}s"
        b = str(size) if size else "FAIL"
        k = f"{kept:.0%}" if size else "-"
        print(f"{url[:45]:<45} {label:<28} {t:>8} {b:>10} {k:>6}")


if __name__ == "__main__":
    main()
