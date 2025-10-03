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

class ElementList:
    BLOCK_ELEMENTS = [
        'html', 'body', 'article', 'section', 'nav', 'aside',
        'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'hgroup', 'header',
        'footer', 'address', 'p', 'hr', 'pre', 'blockquote',
        'ol', 'ul', 'menu', 'li', 'dl', 'dt', 'dd', 'figure',
        'figcaption', 'main', 'div', 'table', 'form', 'fieldset',
        'legend', 'details', 'summary'
    ]

    SELF_CLOSING_TAGS = [
        'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input',
        'link', 'meta', 'param', 'source', 'track', 'wbr',
    ]

    HEAD_TAGS = [
        'base', 'basefont', 'bgsound', 'noscript',
        'link', 'meta', 'title', 'style', 'script',
    ]


class Browser:
    def __init__(self):
        self.window = tkinter.Tk()
        self.canvas = tkinter.Canvas(self.window, width=WIDTH, height=HEIGHT)
        self.canvas.pack()
        self.scroll = 0
        self.window.bind('<Down>', self.scrolldown) # self.scrolldown is an event handler

    def scrolldown(self, e):
        max_y = max(self.document.height + 2 * V_STEP - HEIGHT, 0)
        self.scroll = min(self.scroll + SCROLL_STEP, max_y)
        self.draw()

    def load(self, url):
        # make request, receive response - duh
        body = url.request()
        self.nodes = HtmlParser(body).parse()

        # load default styles
        rules = DEFAULT_STYLE_SHEET.copy()
        style(self.nodes, rules)

        # grab links to external stylesheets
        links = [node.attributes['href']
                 for node in tree_to_list(self.nodes, [])
                 if isinstance(node, Element)
                 and node.tag == 'link'
                 and node.attributes.get('rel') == 'stylesheet'
                 and 'href' in node.attributes]

        # add rules from linked stylesheets to rules list
        for link in links:
            style_url = url.resolve(link)
            try:
                body = style_url.request()
            except:
                continue
            rules.extend(CssParser(body).parse())

        self.document = DocumentLayout(self.nodes)
        self.document.layout()
        self.display_list = []

        paint_tree(self.document, self.display_list)
        self.draw()

    def draw(self):
        self.canvas.delete('all')

        for cmd in self.display_list:
            if cmd.top > self.scroll + HEIGHT:
                continue
            if cmd.bottom < self.scroll:
                continue
            cmd.execute(self.scroll, self.canvas)


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

    # convert different kinds of urls to full urls
    def resolve(self, url):
        if '://' in url: return Url(url)
        if not url.startswith('/'):
            dir, _ = self.path.rsplit('/', 1)

            while url.startswith('../'):
                _, url = url.split('/', 1)
                if '/' in dir:
                    dir, _ = dir.rsplit('/', 1)

            url = dir + '/' + url
        if url.startswith('//'):
            return Url(self.scheme + ':' + url)
        else:
            return Url(self.scheme + '://' + self.host + \
                       ':' + str(self.port) + url)

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
        elif tag in ElementList.SELF_CLOSING_TAGS:
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
                if len(value) > 2 and value[0] in ["'", '\"']:
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
                if tag in ElementList.HEAD_TAGS:
                    self.add_tag('head')
                else:
                    self.add_tag('body')
            elif open_tags == ['html', 'head'] and tag not in ['/head'] + ElementList.HEAD_TAGS:
                self.add_tag('/head')
            else:
                break

class Tag:
    def __init__(self, tag):
        self.tag = tag

class BlockLayout:
    def __init__(self, node, parent, previous):
        self.node = node
        self.parent = parent
        self.previous = previous
        self.children = []

        self.display_list = [] # idk if i still need this or nah

        self.x = None
        self.y = None
        self.width = None
        self.height = None

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
        if self.cursor_x + w > self.width:
            self.flush()
        self.line.append((self.cursor_x, word, font))
        self.cursor_x += w + font.measure(' ')

    def flush(self):
        if not self.line:
            return
        metrics = [font.metrics() for x, word, font in self.line]
        max_ascent = max([metric['ascent'] for metric in metrics])

        baseline = self.cursor_y + 1.25 * max_ascent

        for relative_x, word, font in self.line:
            x = self.x + relative_x
            y = self.y + baseline - font.metrics('ascent')
            self.display_list.append((x, y, word, font))

        max_descent = max([metric['descent'] for metric in metrics])
        self.cursor_y = baseline + 1.25 * max_descent

        self.cursor_x = 0
        self.line = []

    def layout(self):
        self.x = self.parent.x
        self.width = self.parent.width

        if self.previous:
            self.y = self.previous.y + self.previous.height
        else:
            self.y = self.parent.y

        mode = self.layout_mode()

        if mode == 'block':
            previous = None
            for child in self.node.children:
                next_el = BlockLayout(child, self, previous)
                self.children.append(next_el) # constructs layout tree
                previous = next_el
        else:
            self.cursor_x = 0
            self.cursor_y = 0
            self.weight = 'normal'
            self.style = 'roman'
            self.size = 12
            self.line = []

            self.recurse(self.node)
            self.flush()

        for child in self.children:
            child.layout()

        if mode == 'block':
            self.height = sum([child.height for child in self.children])
        else:
            self.height = self.cursor_y

    def layout_intermediate(self):
        previous = None
        for child in self.node.children: # reads from html tree
            next_el = BlockLayout(child, self, previous)
            self.children.append(next_el) # constructs layout tree
            previous = next_el

    def layout_mode(self):
        if isinstance(self.node, Text):
            return 'inline'
        elif any([isinstance(child, Element) and child.tag in ElementList.BLOCK_ELEMENTS for child in self.node.children]):
            return 'block'
        elif self.node.children:
            return 'inline'
        else:
            return 'block'

    def paint(self):
        cmds = []
        # if isinstance(self.node, Element) and self.node.tag == 'pre':
        #     x2, y2 = self.x + self.width, self.y + self.height
        #     rect = DrawRect(self.x, self.y, x2, y2, 'gray')
        #     cmds.append(rect)
        if self.layout_mode() == 'inline':
            for x, y, word, font in self.display_list:
                cmds.append(DrawText(x, y, word, font))

        bgcolor = self.node.style.get('background-color', 'transparent')
        if bgcolor != 'transparent':
            x2, y2 = self.x + self.width, self.y + self.height
            rect = DrawRect(self.x, self.y, x2, y2, bgcolor)
            cmds.append(rect)
        if bgcolor == 'background-color':
            print(True)
        return cmds

class DocumentLayout:
    def __init__(self, node):
        self.node = node
        self.parent = None
        self.children = []

    def layout(self):
        child = BlockLayout(self.node, self, None)
        self.children.append(child)
        self.width = WIDTH - 2 * H_STEP
        self.x = H_STEP
        self.y = V_STEP
        child.layout()
        self.height = child.height

    def paint(self):
        return []


class DrawText:
    def __init__(self, x1, y1, text, font):
        self.top = y1
        self.left = x1
        self.text = text
        self.font = font
        self.bottom = y1 + font.metrics('linespace')

    def execute(self, scroll, canvas):
        canvas.create_text(self.left, self.top - scroll, text=self.text, font=self.font, anchor='nw')

class DrawRect:
    def __init__(self, x1, y1, x2, y2, color):
        self.top = y1
        self.left = x1
        self.bottom = y2
        self.right = x2
        self.color = color

    def execute(self, scroll, canvas):
        canvas.create_rectangle(self.left, self.top - scroll, self.right, self.bottom - scroll, width=0, fill=self.color)

class CssParser:
    def __init__(self, s):
        self.i = 0
        self.s = s

    def whitespace(self):
        while self.i < len(self.s) and self.s[self.i].isspace():
            self.i += 1

    def word(self):
        start = self.i
        while self.i < len(self.s):
            if self.s[self.i].isalnum() or self.s[self.i] in '#-.%':
                self.i += 1
            else:
                break
        if not (self.i > start):
            raise Exception('Parsing error')
        return self.s[start:self.i]

    def literal(self, literal):
        if not (self.i < len(self.s) and self.s[self.i] == literal):
            raise Exception('Parsing error')
        self.i += 1

    def pair(self):
        prop = self.word()
        self.whitespace()
        self.literal(':')
        self.whitespace()
        val = self.word()
        return prop.casefold(), val

    def body(self):
        pairs = {}
        while self.i < len(self.s) and self.s[self.i] != '}':
            try:
                prop, val = self.pair()
                pairs[prop] = val
                self.whitespace()
                self.literal(';')
                self.whitespace()
            except Exception:
                why = self.ignore_until([';', '}'])
                if why == ';':
                    self.literal(';')
                    self.whitespace()
                else:
                    break
        return pairs

    def ignore_until(self, chars):
        while self.i < len(self.s):
            if self.s[self.i] in chars:
                return self.s[self.i]
            else:
                self.i += 1
        return None

    def selector(self):
        out = TagSelector(self.word().casefold())
        self.whitespace()
        while self.i < len(self.s) and self.s[self.i] != '{':
            tag = self.word()
            descendant = TagSelector(tag.casefold())
            out = DescendantSelector(out, descendant)
            self.whitespace()
        return out

    def parse(self):
        rules = []
        while self.i < len(self.s):
            try:
                self.whitespace()
                selector = self.selector()
                self.literal('{')
                self.whitespace()
                body = self.body()
                self.literal('}')
                rules.append((selector, body))
            except Exception:
                why = self.ignore_until(['}']) # skip the entire rule if parse error in selector
                if why == '}':
                    self.literal('}')
                    self.whitespace()
                else:
                    break
        return rules

class TagSelector:
    def __init__(self, tag):
        self.tag = tag

    def matches(self, node):
        return isinstance(node, Element) and self.tag == node.tag

class DescendantSelector:
    def __init__(self, ancestor, descendant):
        self.ancestor = ancestor
        self.descendant = descendant

    def matches(self, node):
        if not self.descendant.matches(node): return False
        while node.parent:
            if self.ancestor.matches(node.parent): return True
            node = node.parent
        return False

def style(node, rules):
    node.style = {}
    if isinstance(node, Element) and 'style' in node.attributes:

        # stylesheet parsing
        for selector, body in rules:
            if not selector.matches(node): continue
            for property, value in body.items():
                node.style[property] = value

        #inline styles should come last because they override the styles in stylesheets
        pairs = CssParser(node.attributes['style']).body()
        for property, value in pairs.items():
            node.style[property] = value

    for child in node.children:
        style(child, rules)

def tree_to_list(tree, list):
    list.append(tree)
    for child in tree.children:
        tree_to_list(child, list)
    return list

def paint_tree(layout_object, display_list):
    display_list.extend(layout_object.paint())

    for child in layout_object.children:
        paint_tree(child, display_list)

def print_tree(node, indent=0):
    print(' ' * indent, node)
    for child in node.children:
        print_tree(child, indent+2)

DEFAULT_STYLE_SHEET = CssParser(open('browser.css').read()).parse() # browser style sheet - defines default styles


if __name__ == '__main__':
    import sys
    Browser().load(Url('https://browser.engineering/styles.html'))
    tkinter.mainloop()