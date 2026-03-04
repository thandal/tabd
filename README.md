# Through a Browser, Darkly
A proxy that flexibly munges web pages using AI.

Example proxying server: http://shen.timbrel.org:5000/

NOTE: We've found that Cerebras's gpt-oss-120b model is the fastest.

## Setup
* Create python virtual environment:
```
python3 -m venv python_env
```
* Activate python virtual environment:
```
source python_env/bin/activate
```
* Install dependencies
```
pip install dotenv mitmproxy openai beautifulsoup4
```
* Create a .env file from .env.example and fill in your API keys as desired

* Then you have two choices: a mitmproxy (transparently sits in between your browser and the internet), or a simple proxying server (gives you a web page from which you can enter a URL to process).

* Start mitmproxy:
```
python3 darkly_proxy.py
```
* Start proxying server:
```
python3 darkly_server.py
```

### For the mitmproxy: Chrome setup: Create a Darkly profile
* Create a new Chrome profile
* Install Proxy Switcher Chrome extension: https://chromewebstore.google.com/detail/onnfghpihccifgojkpnnncpagjcdbjod
* Set to manual proxy, address 127.0.0.1, port 8899, server type http. For example: ![proxy_switcher_configuration](proxy_switcher_configuration.png)
* Make sure to click the green check mark (see red arrow in the image) to save the changes!

### For the mitmproxy: Add the MITM certificate to Chrome
* Go to http://mitm.it/ in the Darkly browser profile
* Click on the "Get mitmproxy-ca-cert.pem" button
* Install the certificate for your browser: Settings > Privacy and Security > Security > Manage certificates > Custom > Trusted Certificates > Import

### For the mitmproxy: Browse the web, configure the AI behavior
You can customize the AI's behavior by visiting **http://dark.ly** in your browser (while the proxy is running).
* Edit the system instructions to change how pages are processed by the AI.
* Save instructions to `ai_instructions.txt`.
* Reset to default settings at any time.
* Example additions:
  * "Convert all proper nouns to bold text"
  * "Add a link to the wikipedia page for each proper noun."
  * "Write everything in pig latin."
  * "If text in the original html appears to be AI generated, put it in double square brackets."

### For the proxying server: Browse the web, configure the AI behavior
* Enter the url you would like to process, and then click "Load"
* You can customer the AI's behavior by clicking the settings button (gear).


## Examples
![slashdot](examples/slashdot_side_by_side.png)

![yahoo](examples/yahoo_side_by_side.png)
