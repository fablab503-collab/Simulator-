"""Gimmich gym practice room: small web pages with one job each, for training
and testing screen-using AIs. The page reports what the AI did to this server,
which writes it to <events-file>, so a task can be scored automatically.

Usage: python3 practice-app.py <port> <events-file>
Pages: /install  /type  /menu  /form
"""
import html
import json
import sys
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

STYLE = """<style>
body{margin:0;font:28px sans-serif;background:#1e283c;color:#222;height:100vh;display:flex;align-items:center;justify-content:center}
.card{background:#fff;border-radius:24px;padding:48px 56px;min-width:560px}
h1{font-size:40px;margin:0 0 12px} p{color:#555;margin:0 0 36px}
button{font:28px sans-serif;border:0;border-radius:14px;padding:18px 40px;margin-right:24px;background:#dcdce1;cursor:pointer}
button.main{background:#1e6ee6;color:#fff} input{font:28px sans-serif;padding:14px;width:420px;border:2px solid #999;border-radius:10px}
.menu{display:none;position:absolute;background:#fff;border:2px solid #999;border-radius:12px;margin-top:8px}
.menu div{padding:16px 40px;cursor:pointer} .menu div:hover{background:#eef}
</style>
<script>function report(what){fetch('/event?'+new URLSearchParams(what));document.title='done';}</script>"""

PAGES = {
    "install": """<div class=card><h1>Install Gimmich Notes?</h1><p>It needs 12 MB of space.</p>
<button onclick="report({page:'install',clicked:'Cancel'})">Cancel</button>
<button class=main onclick="report({page:'install',clicked:'Install'})">Install</button></div>""",
    "type": """<div class=card><h1>What is your name?</h1><p>Type it and press Enter.</p>
<input id=n autofocus onkeydown="if(event.key=='Enter')report({page:'type',typed:this.value})"></div>""",
    "menu": """<div class=card><h1>Welcome</h1><p>Open the File menu and choose Settings.</p>
<button onclick="document.getElementById('m').style.display='block'">File &#9662;</button>
<div class=menu id=m><div onclick="report({page:'menu',chose:'New'})">New</div>
<div onclick="report({page:'menu',chose:'Settings'})">Settings</div>
<div onclick="report({page:'menu',chose:'Quit'})">Quit</div></div></div>""",
    "form": """<div class=card><h1>Sign up</h1><p>Fill in the city, tick the box, then press Save.</p>
<input id=c placeholder="City"><p></p><label><input type=checkbox id=k style="width:32px;height:32px"> I agree</label><p></p>
<button class=main onclick="report({page:'form',city:c.value,agree:k.checked})">Save</button></div>""",
}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        name = url.path.strip("/")
        if name == "event":
            event = dict(urllib.parse.parse_qsl(url.query))
            event["time"] = time.time()
            with open(self.server.events, "a") as f:
                f.write(json.dumps(event) + "\n")
            self.send_response(204)
            self.end_headers()
            return
        body = PAGES.get(name)
        if body is None:
            body = "<div class=card><h1>Pages</h1>" + "".join(
                '<p><a href="/%s">%s</a></p>' % (p, html.escape(p)) for p in PAGES) + "</div>"
        page = "<!doctype html><title>%s</title>%s%s" % (name or "gym", STYLE, body)
        data = page.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", int(sys.argv[1])), Handler)
    server.events = sys.argv[2]
    server.serve_forever()
