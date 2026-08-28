import http.server
import socketserver
import threading
import os

PORT = 8000

class Handler(http.server.SimpleHTTPRequestHandler):
    pass

def start_server():
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print("Server started at port", PORT)
        httpd.serve_forever()

server_thread = threading.Thread(target=start_server)
server_thread.daemon = True
server_thread.start()
print("Web server running in background.")
