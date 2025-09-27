import socket
import ssl
import tkinter
import tkinter.font

WIDTH, HEIGHT = 800, 600
H_STEP, V_STEP = 13, 18
SCROLL_STEP = 100

FONTS = {} # for caching

def get_font(size, weight, style):
    key = (size, weight, style)
    if key not in FONTS:
        font = tkinter.font.Font(size=size, weight=weight,
            slant=style)
        label = tkinter.Label(font=font)
        FONTS[key] = (font, label)
    return FONTS[key][0]

class Browser:
    def __init__(self):
        self.window = tkinter.Tk()
        self.canvas = tkinter.Canvas(self.window, width=WIDTH, height=HEIGHT)
        self.canvas.pack()
        self.scroll = 0
        self.window.bind('<Down>', self.scrolldown) # self.scrolldown is an event handler

    def scrolldown(self, e):
        self.scroll += SCROLL_STEP
        self.draw()

    def load(self, url):
        body = url.request()
        self.nodes = HtmlParser(body).parse()
        self.display_list = Layout(self.nodes).display_list
        self.draw()

    def draw(self):
        self.canvas.delete('all')

        for x, y, c, f in self.display_list:
            if y > self.scroll + HEIGHT:
                continue
            if y + V_STEP < self.scroll:
                continue
            self.canvas.create_text(x, y - self.scroll, text=c, font=f, anchor='nw')


class Url:
    def __init__(self, url):
        self.scheme, url = url.split('://', 1)
        assert self.scheme in ['http', 'https']

        if self.scheme == 'https':
            self.port = 443
        elif self.scheme == 'http':
            self.port = 80

        if '/' not in url:
            url += '/'
        self.host, url = url.split('/', 1)
        self.path = '/' + url

        if ':' in self.host:
            self.host, port = self.host.split(':', 1)
            self.port = int(port)

    def request(self):
        s = socket.socket(family=socket.AF_INET, type=socket.SOCK_STREAM, proto=socket.IPPROTO_TCP)
        s.connect((self.host, self.port))
        if self.scheme == 'https':
            ctx = ssl.create_default_context()
            s = ctx.wrap_socket(s, server_hostname=self.host)

        request = 'GET {} HTTP/1.0\r\n'.format(self.path)
        request += 'Host: {}\r\n'.format(self.host)
        request += '\r\n'
        s.send(request.encode('utf8'))

        response = s.makefile('r', encoding='utf8', newline='\r\n')

        status_line = response.readline()
        version, status, explanation = status_line.split(' ', 2)

        response_headers = {}
        while True:
            line = response.readline()
            if line == '\r\n':
                break
            header, value = line.split(':', 1)
            response_headers[header.casefold()] = value.strip()

        assert 'transfer-encoding' not in response_headers
        assert 'content-encoding' not in response_headers

        content = response.read()
        s.close()

        return content

class Text:
    def __init__(self, text, parent):
        self.text = text
        self.children = []
        self.parent = parent

    def __repr__(self):
        return repr(self.text)

class Element:
    def __init__(self, tag, attributes, parent):
        self.tag = tag
        self.children = []
        self.parent = parent
        self.attributes = attributes

    def __repr__(self):
        return '<' + self.tag + '>'

class HtmlParser:
    SELF_CLOSING_TAGS = [
        "area", "base", "br", "col", "embed", "hr", "img", "input",
        "link", "meta", "param", "source", "track", "wbr",
    ]

    HEAD_TAGS = [
        "base", "basefont", "bgsound", "noscript",
        "link", "meta", "title", "style", "script",
    ]

    def __init__(self, body):
        self.body = body
        self.unfinished = []

    def add_text(self, text):
        if text.isspace():
            return

        self.implicit_tags(None)

        parent = self.unfinished[-1]
        node = Text(text, parent)
        parent.children.append(node)

    def add_tag(self, tag):
        tag, attributes = self.get_attributes(tag)
        if tag.startswith('!'):
            return

        self.implicit_tags(tag)

        if tag.startswith('/'):
            if len(self.unfinished) == 1:
                return
            node = self.unfinished.pop()
            parent = self.unfinished[-1]
            parent.children.append(node)
        elif tag in self.SELF_CLOSING_TAGS:
            parent = self.unfinished[-1]
            node = Element(tag, attributes, parent)
            parent.children.append(node)
        else:
            parent = self.unfinished[-1] if self.unfinished else None
            node = Element(tag, attributes, parent)
            self.unfinished.append(node)

    def get_attributes(self, text):
        parts = text.split()
        tag = parts[0].casefold()
        attributes = {}
        for attr_pair in parts[1:]:
            if '=' in attr_pair:
                key, value = attr_pair.split('=', 1)
                if len(value) > 2 and value[0] in ["'", "\""]:
                    value = value[1: -1]
                attributes[key.casefold()] = value
            else:
                attributes[attr_pair.casefold()] = ''
        return tag, attributes

    def finish(self):
        while len(self.unfinished) > 1:
            if not self.unfinished:
                self.implicit_tags(None)

            node = self.unfinished.pop()
            parent = self.unfinished[-1]
            parent.children.append(node)
        return self.unfinished.pop()

    def parse(self):
        text = ''
        in_tag = False
        for c in self.body:
            if c == '<':
                in_tag = True
                if text:
                    self.add_text(text)
                text = ''
            elif c == '>':
                in_tag = False
                self.add_tag(text)
                text = ''
            else:
                text += c
        if not in_tag and text:
            self.add_text(text)
        return self.finish()

    def implicit_tags(self, tag):
        while True:
            open_tags = [node.tag for node in self.unfinished]
            if open_tags == [] and tag != 'html':
                self.add_tag('html')
            elif open_tags == ['html'] and tag not in ['head', 'body', '/html']:
                if tag in self.HEAD_TAGS:
                    self.add_tag('head')
                else:
                    self.add_tag('body')
            elif open_tags == ['html', 'head'] and tag not in ['/head'] + self.HEAD_TAGS:
                self.add_tag('/head')
            else:
                break

class Tag:
    def __init__(self, tag):
        self.tag = tag

class Layout:
    def __init__(self, tree):
        self.display_list = []
        self.cursor_x = H_STEP
        self.cursor_y = V_STEP
        self.weight = "normal"
        self.style = "roman"
        self.size = 12
        self.line = []

        self.recurse(tree)

        self.flush()

    def open_tag(self, tag):
        if tag == 'i':
            self.style = 'italic'
        elif tag == 'b':
            self.weight = 'bold'
        elif tag == 'small':
            self.size -= 2
        elif tag == 'big':
            self.size += 4
        elif tag == 'br':
            self.flush()

    def close_tag(self, tag):
        if tag == 'i':
            self.style = 'roman'
        elif tag == 'b':
            self.weight = 'normal'
        elif tag == 'small':
            self.size += 2
        elif tag == 'big':
            self.size -= 4
        elif tag == 'p':
            self.flush()
            self.cursor_y += V_STEP

    def recurse(self, tree):
        if isinstance(tree, Text):
            for word in tree.text.split():
                self.word(word)
        else:
            self.open_tag(tree.tag)
            for child in tree.children:
                self.recurse(child)
            self.close_tag(tree.tag)

    def word(self, word):
        font = get_font(self.size, self.weight, self.style)
        w = font.measure(word)

        if self.cursor_x + w > WIDTH - H_STEP:
            self.flush()

        self.line.append((self.cursor_x, word, font))

        self.cursor_x += w + font.measure(' ')

    def flush(self):
        if not self.line:
            return
        metrics = [font.metrics() for x, word, font in self.line]
        max_ascent = max([metric['ascent'] for metric in metrics])

        baseline = self.cursor_y + 1.25 * max_ascent

        for x, word, font in self.line:
            y = baseline - font.metrics('ascent')
            self.display_list.append((x, y, word, font))

        max_descent = max([metric['descent'] for metric in metrics])
        self.cursor_y = baseline + 1.25 * max_descent

        self.cursor_x = H_STEP
        self.line = []

def print_tree(node, indent=0):
    print(' ' * indent, node)
    for child in node.children:
        print_tree(child, indent+2)

if __name__ == '__main__':
    import sys
    Browser().load(Url(sys.argv[1]))
    tkinter.mainloop()