import socket
import urllib.parse
import random

# store info about each user/client
SESSIONS = {}

def handle_connection(conx):
    # read the request line
    req = conx.makefile('b')
    reqline = req.readline().decode('utf8')
    method, url, version = reqline.split(' ', 2)
    assert method in ['GET', 'POST']

    # read and store headers until a blank line is reached
    headers = {}
    while True:
        line = req.readline().decode('utf8')
        if line == '\r\n':
            break
        header, value = line.split(':', 1)
        headers[header.casefold()] = value.strip()

    # grab cookie if it is available
    if "cookie" in headers:
        token = headers["cookie"][len("token="):]
    else:
        token = str(random.random())[2:]

    # read the body if it exists
    if 'content-length' in headers:
        length = int(headers['content-length'])
        body = req.read(length).decode('utf8')
    else:
        body = None

    session = SESSIONS.setdefault(token, {})
    status, body = do_request(session, method, url, headers, body)

    # send the page back to the browser
    response = 'HTTP/1.0 {}\r\n'.format(status)
    response += 'Content-Length: {}\r\n'.format(len(body.encode('utf8')))
    if "cookie" not in headers:
        template = "Set-Cookie: token={}\r\n"
        response += template.format(token)
    response += '\r\n' + body
    conx.send(response.encode('utf8'))
    conx.close()

# output html to show the entries
def show_comments(session):
    out = '<!doctype html>'
    out += '<head>'
    out += '<link rel=stylesheet href=/comment.css>'
    out += '</head>'
    for entry in ENTRIES:
        out += '<p>' + entry + '</p>'

    out += '<strong></strong>'

    out += '<br>'
    out += '<form action=add method=post>'
    out += '<p><input name=guest></p>'
    out += '<p><button>Sign the book!</button></p>'
    out += '</form>'
    out += '<script src=/comment.js></script>'
    return out

# decide how to respond based on the request type
def do_request(session, method, url, headers, body):
    if method == 'GET' and url == '/':
        return '200 OK', show_comments(session)
    elif method == 'GET' and url == '/comment.js':
        with open('comment.js') as f:
            return '200 OK', f.read()
    elif method == 'GET' and url == '/comment.css':
        with open('comment.css') as f:
            return '200 OK', f.read()
    elif method == 'POST' and url == '/add':
        params = form_decode(body)
        return '200 OK', add_entry(session, params)
    else:
        return '404 Not Found', not_found(url, method)

# decode the body
def form_decode(body):
    params = {}
    for field in body.split('&'):
        name, value = field.split('=', 1)
        # use `unquote_plus` instead of `unquote` because browsers may use a `+` to encode space
        name = urllib.parse.unquote_plus(name)
        value = urllib.parse.unquote_plus(value)
        params[name] = value
    return params

def add_entry(session, params):
    if 'guest' in params and len(params['guest']) <= 10:
        ENTRIES.append(params['guest'])
    return show_comments(session)

def not_found(url, method):
    out = '<!doctype html>'
    out += '<h1>{} {} not found!</h1>'.format(method, url)
    return out

ENTRIES = [ 'Pavel was here' ]

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