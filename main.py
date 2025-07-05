import threading
import bot
from http.server import BaseHTTPRequestHandler, HTTPServer

def lancer_http():
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Bot Telegram actif.")
    server = HTTPServer(("0.0.0.0", 10000), Handler)
    server.serve_forever()

if __name__ == "__main__":
    bot_thread = threading.Thread(target=bot.main)
    http_thread = threading.Thread(target=lancer_http)
    bot_thread.start()
    http_thread.start()
