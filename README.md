# Through a Browser, Darkly
A mitmproxy-based proxy that flexibly simplifies web pages using AI.

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
pip install dotenv mitmproxy openai lxml[html_clean] requests readability-lxml
```
* Create a .env file from .env.example and fill in your API keys as desired
* Start proxy app:
```
python3 app.py
```

### Chrome setup: Create a Darkly profile
* Create a new Chrome profile
* Install Proxy Switcher Chrome extension: https://chromewebstore.google.com/detail/onnfghpihccifgojkpnnncpagjcdbjod
* Set to manual proxy, address 127.0.0.1, port 8888, server type http. For example: ![proxy_switcher_configuration](proxy_switcher_configuration.png)

### Add the MITM certificate to Chrome
* Go to http://mitm.it/ in the Darkly browser profile
* Click on the "Get mitmproxy-ca-cert.pem" button
* Install the certificate for your browser: Settings > Privacy and Security > Security > Manage certificates > Custom > Trusted Certificates > Import

Browse the web -- and feel free to change the prompts in darkly_addon.py!
For example, try adding
* "Convert all proper nouns to bold text"
* "Add a link to the wikipedia page for each proper noun."

## Examples
![slashdot](examples/slashdot_side_by_side.png)

![yahoo](examples/yahoo_side_by_side.png)
