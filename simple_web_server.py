import socket

def handle_connection(conx):
    # read the request line
    req = conx.makefile("b")
    reqline = req.readline().decode('utf8')
    method, url, version = reqline.split(" ", 2)
    assert method in ["GET", "POST"]

    # read and store headers until a blank line is reached
    headers = {}
    while True:
        line = req.readline().decode('utf8')
        if line == '\r\n': break
        header, value = line.split(":", 1)
        headers[header.casefold()] = value.strip()

    # read the body if it exists
    if 'content-length' in headers:
        length = int(headers['content-length'])
        body = req.read(length).decode('utf8')
    else:
        body = None

    status, body = do_request(method, url, headers, body)

    # send the page back to the browser
    response = "HTTP/1.0 {}\r\n".format(status)
    response += "Content-Length: {}\r\n".format(
        len(body.encode("utf8")))
    response += "\r\n" + body
    conx.send(response.encode('utf8'))
    conx.close()

s = socket.socket(family=socket.AF_INET, type=socket.SOCK_STREAM, proto=socket.IPPROTO_TCP)

# prevent os from blocking temporarily this port if a crash occurs
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

# wait for computer to connect
s.bind(('', 8000)) # anyone can connect to the server on port 8000
s.listen()

# runs once per connection
while True:
    conx, addr = s.accept()
    handle_connection(conx)