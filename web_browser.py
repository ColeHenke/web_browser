import socket
import ssl
import tkinter
import tkinter.font
import urllib.parse
import dukpy

WIDTH, HEIGHT = 800, 600
H_STEP, V_STEP = 13, 18
SCROLL_STEP = 100

# inputs are usually a fixed width
INPUT_WIDTH_PX = 200

FONTS = {} # for caching

# since these properties are inheirited, they need default vals in case they are not specified by children
INHERITED_PROPERTIES = {
    'font-size': '16px',
    'font-style': 'normal',
    'font-weight': 'normal',
    'color': 'black',
}

def get_font(size, weight, style):
    key = (size, weight, style)
    if key not in FONTS:
        font = tkinter.font.Font(size=size, weight=weight,slant=style)
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

RUNTIME_JS = open("test_webpage/runtime.js").read()

class Browser:
    def __init__(self):
        self.tabs = []
        self.active_tab = None
        self.window = tkinter.Tk()
        self.canvas = tkinter.Canvas(self.window, width=WIDTH, height=HEIGHT, bg='white')
        self.canvas.pack()
        self.window.bind('<Down>', self.handle_down) # self.scrolldown is an event handler
        self.window.bind('<Button-1>', self.handle_click) # left-click action
        self.chrome = Chrome(self)
        self.window.bind('<Key>', self.handle_key) # fires on every keypress
        self.window.bind('<Return>', self.handle_enter)

        self.focus = None

    def handle_down(self, e):
        self.active_tab.scrolldown()
        self.draw()

    def handle_click(self, e):
        if e.y < self.chrome.bottom:
            self.focus = None # focus no longer in page contents
            self.chrome.click(e.x, e.y)
        else:
            # user clicks on the webpage, transfer focus to it
            self.focus = "content"
            self.chrome.blur()

            tab_y = e.y - self.chrome.bottom
            self.active_tab.click(e.x, tab_y)
        self.draw()

    def handle_key(self, e):
        if len(e.char) == 0:
            return
        if not (0x20 <= ord(e.char) < 0x7f): # allow only ascii printable characters (32-127)
            return
        # send the keypress to the address bar or input (or nothing if neither) have focus
        if self.chrome.keypress(e.char):
            self.draw()
        elif self.focus == "content":
            self.active_tab.keypress(e.char)
            self.draw()

    def handle_enter(self, e):
        self.chrome.enter()
        self.draw()

    def draw(self):
        self.canvas.delete('all')
        self.active_tab.draw(self.canvas, self.chrome.bottom)

        for cmd in self.chrome.paint():
            cmd.execute(0, self.canvas)

    def new_tab(self, url):
        new_tab = Tab(HEIGHT - self.chrome.bottom)
        new_tab.load(url)
        self.active_tab = new_tab
        self.tabs.append(new_tab)
        self.draw()

# this class will allow the user to navigate thru tabs
class Chrome:
    def __init__(self, browser):
        self.browser = browser
        self.font = get_font(20, 'normal', 'roman')
        self.font_height = self.font.metrics('linespace')

        # this is where the tab bar starts and ends
        self.padding = 5
        self.tabbar_top = 0
        self.tabbar_bottom = self.font_height + 2 * self.padding

        self.focus = None
        self.address_bar = ''

        # new tab button
        plus_width = self.font.measure('+') + 2 * self.padding
        self.newtab_rect = Rect(
            self.padding, self.padding,
            self.padding + plus_width,
            self.padding + self.font_height)

        # url bar
        self.urlbar_top = self.tabbar_bottom
        self.urlbar_bottom = self.urlbar_top + \
                             self.font_height + 2 * self.padding
        self.bottom = self.urlbar_bottom

        # back button
        back_width = self.font.measure('<') + 2 * self.padding
        self.back_rect = Rect(
            self.padding,
            self.urlbar_top + self.padding,
            self.padding + back_width,
            self.urlbar_bottom - self.padding)

        # address bar
        self.address_rect = Rect(
            self.back_rect.top + self.padding,
            self.urlbar_top + self.padding,
            WIDTH - self.padding,
            self.urlbar_bottom - self.padding)

    # since the number of tabs can change, just compute their bounds on the go
    def tab_rect(self, i):
        tabs_start = self.newtab_rect.right + self.padding
        tab_width = self.font.measure('Tab X') + 2 * self.padding
        return Rect(
            tabs_start + tab_width * i, self.tabbar_top,
            tabs_start + tab_width * (i + 1), self.tabbar_bottom)

    def paint(self):
        cmds = []

        # guarantee that the browser chrome is drawn on top of page contents
        cmds.append(DrawRect(
            Rect(0, 0, WIDTH, self.bottom),
            'white'))
        cmds.append(DrawLine(
            0, self.bottom, WIDTH,
            self.bottom, 'black', 1))

        # draw the new tab button
        cmds.append(DrawOutline(self.newtab_rect, 'black', 1))
        cmds.append(DrawText(
            self.newtab_rect.left + self.padding,
            self.newtab_rect.top,
            '+', self.font, 'black'))

        # draw the tabs themselves
        for i, tab in enumerate(self.browser.tabs):
            bounds = self.tab_rect(i)
            cmds.append(DrawLine(
                bounds.left, 0, bounds.left, bounds.bottom,
                'black', 1))
            cmds.append(DrawLine(
                bounds.right, 0, bounds.right, bounds.bottom,
                'black', 1))
            cmds.append(DrawText(
                bounds.left + self.padding, bounds.top + self.padding,
                'Tab {}'.format(i), self.font, 'black'))

            # make the active tab more prominent
            if tab == self.browser.active_tab:
                cmds.append(DrawLine(
                    0, bounds.bottom, bounds.left, bounds.bottom,
                    'black', 1))
                cmds.append(DrawLine(
                    bounds.right, bounds.bottom, WIDTH, bounds.bottom,
                    'black', 1))

        cmds.append(DrawOutline(self.back_rect, 'black', 1))
        cmds.append(DrawText(self.back_rect.left + self.padding, self.back_rect.top,'<', self.font, 'black'))

        cmds.append(DrawOutline(self.address_rect, 'black', 1))
        url = str(self.browser.active_tab.url)
        cmds.append(DrawText(self.address_rect.left + self.padding, self.address_rect.top, url, self.font, 'black'))

        # draw the currently typed text
        if self.focus == 'address bar':
            cmds.append(DrawText(self.address_rect.left + self.padding, self.address_rect.top, self.address_bar, self.font, 'black'))
            # add in a cursor
            w = self.font.measure(self.address_bar)
            cmds.append(DrawLine(self.address_rect.left + self.padding + w, self.address_rect.top, self.address_rect.left +
                                 self.padding + w,self.address_rect.bottom, 'red', 1))
        # draw the url
        else:
            url = str(self.browser.active_tab.url)
            cmds.append(DrawText(self.address_rect.left + self.padding, self.address_rect.top, url, self.font, 'black'))

        return cmds

    def click(self, x, y):
        self.focus = None

        # open new tab
        if self.newtab_rect.contains_point(x, y):
            self.browser.new_tab(Url('https://browser.engineering/'))

        # go back to url
        elif self.back_rect.contains_point(x, y):
            self.browser.active_tab.go_back()

         # focus on addres bar when clicked
        elif self.address_rect.contains_point(x, y):
            self.focus = 'address bar'
            self.address_bar = ''
            self.browser.active_tab.url = ''

        # switch the current active tab
        else:
            for i, tab in enumerate(self.browser.tabs):
                if self.tab_rect(i).contains_point(x, y):
                    self.browser.active_tab = tab
                    break

    def keypress(self, char):
        if self.focus == "address bar":
            self.address_bar += char
            return True # return true if the chrome consumes the key
        return False

    def enter(self):
        if self.focus == 'address bar':
            self.browser.active_tab.load(Url(self.address_bar))
            self.focus = None

    def blur(self):
        self.focus = None

class Tab:
    def __init__(self, tab_height):
        self.scroll = 0
        self.url = None # page's url
        self.tab_height = tab_height
        self.history = []

        # load default styles
        self.rules = DEFAULT_STYLE_SHEET.copy()
        self.nodes = []
        self.focus = None # this will remember which text input we clicked on

        self.js = None

    def scrolldown(self):
        max_y = max(self.document.height + 2 * V_STEP - self.tab_height, 0)
        self.scroll = min(self.scroll + SCROLL_STEP, max_y)

    def click(self, x, y):
        y += self.scroll # we want relative y position, so add the scroll height to y
        self.focus = None # clear focus

        # find out what the user clicked on
        objs = [obj for obj in tree_to_list(self.document, [])
                if obj.x <= x < obj.x + obj.width
                and obj.y <= y < obj.y + obj.height]
        if not objs: return
        elt = objs[-1].node # most specific node that was clicked

        if self.focus:
            self.focus.is_focused = False

        # climb up the tree to find the link element
        while elt:
            if isinstance(elt, Text):
                pass
            elif elt.tag == 'a' and 'href' in elt.attributes:
                url = self.url.resolve(elt.attributes['href'])
                return self.load(url)
            # if a button is clicked, walk the html tree to find the form that the button is in
            elif elt.tag == "button":
                while elt:
                    if elt.tag == "form" and "action" in elt.attributes:

                        return self.submit_form(elt)
                    elt = elt.parent
            elif elt.tag == 'input':
                elt.attributes['value'] = ''
                self.focus = elt
                elt.is_focused = True
                return self.render()
            elt = elt.parent
        self.render()

    # find all input elements, encode them, send post request
    def submit_form(self, elt):
        inputs = [node for node in tree_to_list(elt, [])
                  if isinstance(node, Element)
                  and node.tag == "input"
                  and "name" in node.attributes]

        # key value pairs to be sent
        body = ""
        for input in inputs:
            name = input.attributes["name"]
            value = input.attributes.get("value", "")

            # percent-encode the key and
            name = urllib.parse.quote(name)
            value = urllib.parse.quote(value)
            body += "&" + name + "=" + value
        body = body[1:]

        url = self.url.resolve(elt.attributes["action"])
        self.load(url, body)

    def load(self, url, payload=None):
        self.history.append(url)
        self.url = url # current url
        # make request, receive response - duh
        body = url.request(payload)
        self.nodes = HtmlParser(body).parse()
        self.js = JsContext(self)

        # grab links to js files
        scripts = [node.attributes["src"] for node
                   in tree_to_list(self.nodes, [])
                   if isinstance(node, Element)
                   and node.tag == "script"
                   and "src" in node.attributes]

        # run all the scripts
        for script in scripts:
            script_url = url.resolve(script)
            try:
                body = script_url.request()
            except:
                continue

            self.js.run(script, body)

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
            self.rules.extend(CssParser(body).parse())

        style(self.nodes, sorted(self.rules, key=cascade_priority))

        self.render()

    # seperate styling, layout, and paint from loading
    def render(self):
        style(self.nodes, sorted(self.rules, key=cascade_priority))
        self.document = DocumentLayout(self.nodes)
        self.document.layout()
        self.display_list = []
        paint_tree(self.document, self.display_list)

    def draw(self, canvas, offset):
        canvas.delete('all')

        # don't draw things that are not visible
        for cmd in self.display_list:
            if cmd.rect.top > self.scroll + self.tab_height:
                continue
            if cmd.rect.bottom < self.scroll:
                continue
            cmd.execute(self.scroll - offset, canvas)

    def go_back(self):
        if len(self.history) > 1:
            self.history.pop()
            back = self.history.pop()
            self.load(back)

    # add character to text entry field
    def keypress(self, char):
        if self.focus:
            self.focus.attributes["value"] += char
            self.render()

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

    def request(self, payload=None):
        s = socket.socket(family=socket.AF_INET, type=socket.SOCK_STREAM, proto=socket.IPPROTO_TCP)
        s.connect((self.host, self.port))
        if self.scheme == 'https':
            ctx = ssl.create_default_context()
            s = ctx.wrap_socket(s, server_hostname=self.host)

        method = 'POST' if payload else 'GET'

        request = '{} {} HTTP/1.0\r\n'.format(method, self.path)
        request += 'Host: {}\r\n'.format(self.host)
        if payload:
            length = len(payload.encode('utf8'))
            request += 'Content-Length: {}\r\n'.format(length)
        request += '\r\n'
        if payload:
            request += payload
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

    # this is used to correctly format url strings in the address bar
    # it hides the port numbers on the urls
    def __str__(self):
        port_part = ':' + str(self.port)
        if self.scheme == 'https' and self.port == 443:
            port_part = ''
        if self.scheme == 'http' and self.port == 80:
            port_part = ''
        return self.scheme + '://' + self.host + port_part + self.path

class Text:
    def __init__(self, text, parent):
        self.text = text
        self.children = []
        self.parent = parent
        self.is_focused = False

    def __repr__(self):
        return repr(self.text)

class Element:
    def __init__(self, tag, attributes, parent):
        self.tag = tag
        self.children = []
        self.parent = parent
        self.attributes = attributes
        self.is_focused = False

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
        self.cursor_x = None

    def recurse(self, node):
        if isinstance(node, Text):
            for word in node.text.split():
                # noinspection PyTypeChecker
                self.word(node, word)
        else:
            if node.tag == 'br':
                self.new_line()
            elif node.tag == 'input' or node.tag == 'button':
                self.input(node)
            else:
                for child in node.children:
                    self.recurse(child)

    def word(self, node, word):
        # get the property values of for the font
        weight = node.style['font-weight']
        style = node.style['font-style']
        if style == 'normal':
            style = 'roman'
        size = int(float(node.style['font-size'][:-2]) * .75) # converts css pixels to tk points
        font = get_font(size, weight, style)
        color = node.style['color']

        w = font.measure(word)
        if self.cursor_x + w > self.width:
            self.new_line()

        line = self.children[-1]
        previous_word = line.children[-1] if line.children else None
        text = TextLayout(node, word, line, previous_word)
        line.children.append(text)

    def new_line(self):
        self.cursor_x = 0
        last_line = self.children[-1] if self.children else None
        new_line = LineLayout(self.node, self, last_line)
        self.children.append(new_line)

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
            self.new_line()
            self.recurse(self.node)

        for child in self.children:
            child.layout()

        self.height = sum([child.height for child in self.children])

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
        elif self.node.children or self.node.tag == 'input':
            return 'inline'
        else:
            return 'block'

    def input(self, node):
        w = INPUT_WIDTH_PX
        if self.cursor_x + w > self.width:
            self.new_line()
        line = self.children[-1]
        previous_word = line.children[-1] if line.children else None
        input = InputLayout(node, line, previous_word)
        line.children.append(input)

        weight = node.style['font-weight']
        style = node.style['font-style']
        if style == 'normal': style = 'roman'
        size = int(float(node.style['font-size'][:-2]) * .75)
        font = get_font(size, weight, style)

        self.cursor_x += w + font.measure(' ')

    '''
    <input> and <button> creates a BlockLayout which then creates an InputLayout inside it which paints the background
     twice.
     To avoid, we use this method to conditionally skip painting inside a BlockLayout.
    '''
    def should_paint(self):
        return isinstance(self.node, Text) or \
            (self.node.tag != "input" and self.node.tag != "button")

    def paint(self):
        cmds = []
        if self.layout_mode() == 'inline':
            for x, y, word, font, color in self.display_list:
                cmds.append(DrawText(x, y, word, font, color))

        bgcolor = self.node.style.get('background-color', 'transparent')
        if bgcolor != 'transparent':
            rect = DrawRect(self.self_rect(), bgcolor)
            cmds.append(rect)
        return cmds

    def self_rect(self):
        return Rect(self.x, self.y, self.x + self.width, self.y + self.height)

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

    def should_paint(self):
        return True

# this will be held within BlockLayout objects and will hold TextLayout objects
class LineLayout:
    def __init__(self, node, parent, previous):
        self.node = node
        self.parent = parent
        self.previous = previous
        self.children = []
        self.x = None
        self.y = None
        self.width = None
        self.height = None

    def layout(self):
        self.width = self.parent.width
        self.x = self.parent.x

        if self.previous:
            self.y = self.previous.y + self.previous.height
        else:
            self.y = self.parent.y

        for word in self.children:
            word.layout()

        if not self.children:
            self.height = 0
            return

        max_ascent = max([word.font.metrics('ascent')
                          for word in self.children])
        baseline = self.y + 1.25 * max_ascent
        for word in self.children:
            word.y = baseline - word.font.metrics('ascent')
        max_descent = max([word.font.metrics('descent')
                           for word in self.children])

        self.height = 1.25 * (max_ascent + max_descent)

    def paint(self):
        return []

    def should_paint(self):
        return True

class TextLayout:
    def __init__(self, node, word, parent, previous):
        self.node = node
        self.word = word
        self.children = []
        self.parent = parent
        self.previous = previous
        self.x = None
        self.y = None
        self.width = None
        self.height = None
        self.font = None

    def layout(self):
        weight = self.node.style['font-weight']
        style = self.node.style['font-style']
        if style == 'normal':
            style = 'roman'
        size = int(float(self.node.style['font-size'][:-2]) * .75)
        self.font = get_font(size, weight, style)

        self.width = self.font.measure(self.word)

        if self.previous:
            space = self.previous.font.measure(' ')
            self.x = self.previous.x + space + self.previous.width
        else:
            self.x = self.parent.x

        self.height = self.font.metrics('linespace')

    def paint(self):
        color = self.node.style['color']
        return [DrawText(self.x, self.y, self.word, self.font, color)]

    def should_paint(self):
        return True

# handle form inputs
class InputLayout:
    def __init__(self, node, parent, previous):
        self.node = node
        self.children = []
        self.parent = parent
        self.previous = previous
        self.width = INPUT_WIDTH_PX # width is usually fixed
        self.x = None
        self.y = None
        self.height = None
        self.font = None

    def layout(self):
        weight = self.node.style['font-weight']
        style = self.node.style['font-style']
        if style == 'normal':
            style = 'roman'
        size = int(float(self.node.style['font-size'][:-2]) * .75)
        self.font = get_font(size, weight, style)

        if self.previous:
            space = self.previous.font.measure(' ')
            self.x = self.previous.x + space + self.previous.width
        else:
            self.x = self.parent.x

        self.height = self.font.metrics('linespace')


    def paint(self):
        cmds = []
        bgcolor = self.node.style.get('background-color',
                                      'transparent')
        if bgcolor != 'transparent':
            rect = DrawRect(self.self_rect(), bgcolor)
            cmds.append(rect)

        if self.node.tag == 'input':
            text = self.node.attributes.get('value', '')
        elif self.node.tag == 'button':
            if len(self.node.children) == 1 and \
                    isinstance(self.node.children[0], Text):
                text = self.node.children[0].text
            else:
                print('Ignoring HTML contents inside button')
                text = ''
        color = self.node.style['color']
        cmds.append(DrawText(self.x, self.y, text, self.font, color))

        # draw cursor if input is focused
        if self.node.is_focused:
            cx = self.x + self.font.measure(text)
            cmds.append(DrawLine(
                cx, self.y, cx, self.y + self.height, "black", 1))
        return cmds

    def should_paint(self):
        return True

    def self_rect(self):
        return Rect(self.x, self.y, self.x + self.width, self.y + self.height)

class Rect:
    def __init__(self, left, top, right, bottom):
        self.left = left
        self.top = top
        self.right = right
        self.bottom = bottom

    def contains_point(self, x, y):
        return x >= self.left and x < self.right and y >= self.top and y < self.bottom

class DrawText:
    def __init__(self, x1, y1, text, font, color):
        self.text = text
        self.font = font
        self.bottom = y1 + font.metrics('linespace')
        self.color = color
        self.rect = Rect(x1, y1, x1 + font.measure(text), y1 + font.metrics('linespace'))

    def execute(self, scroll, canvas):
        canvas.create_text(self.rect.left, self.rect.top - scroll, text=self.text, font=self.font, anchor='nw',
                           fill=self.color)

class DrawRect:
    def __init__(self, rect, color):
        self.color = color
        self.rect = rect

    def execute(self, scroll, canvas):
        canvas.create_rectangle(self.rect.left, self.rect.top - scroll, self.rect.right, self.rect.bottom - scroll,
            width=0, fill=self.color)

class DrawOutline:
    def __init__(self, rect, color, thickness):
        self.rect = rect
        self.color = color
        self.thickness = thickness

    def execute(self, scroll, canvas):
        canvas.create_rectangle(self.rect.left, self.rect.top - scroll, self.rect.right, self.rect.bottom - scroll,
            width=self.thickness, outline=self.color)

class DrawLine:
    def __init__(self, x1, y1, x2, y2, color, thickness):
        self.rect = Rect(x1, y1, x2, y2)
        self.color = color
        self.thickness = thickness

    def execute(self, scroll, canvas):
        canvas.create_line(self.rect.left, self.rect.top - scroll, self.rect.right, self.rect.bottom - scroll,
            fill=self.color, width=self.thickness)

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
        self.priority = 1

    def matches(self, node):
        return isinstance(node, Element) and self.tag == node.tag

class DescendantSelector:
    def __init__(self, ancestor, descendant):
        self.ancestor = ancestor
        self.descendant = descendant
        self.priority = ancestor.priority + descendant.priority

    def matches(self, node):
        if not self.descendant.matches(node): return False
        while node.parent:
            if self.ancestor.matches(node.parent): return True
            node = node.parent
        return False

def style(node, rules):
    node.style = {}

    for property, default_value in INHERITED_PROPERTIES.items():
        if node.parent:
            node.style[property] = node.parent.style[property]
        else:
            node.style[property] = default_value

    # stylesheet parsing
    for selector, body in rules:
        if not selector.matches(node): continue
        for property, value in body.items():
            node.style[property] = value

    if isinstance(node, Element) and 'style' in node.attributes:
        # inline styles should come last because they override the styles in stylesheets
        pairs = CssParser(node.attributes['style']).body()
        for property, value in pairs.items():
            node.style[property] = value

        # resolve font-size
        # put this last so that all we work with the final font-size value
        if node.style['font-size'].endswith('%'):
            if node.parent:
                parent_font_size = node.parent.style['font-size']
            else:
                parent_font_size = INHERITED_PROPERTIES['font-size']
            node_pct = float(node.style['font-size'][:-1]) / 100
            parent_px = float(parent_font_size[:-2])
            node.style['font-size'] = str(node_pct * parent_px) + 'px'

    for child in node.children:
        style(child, rules)

class JsContext:
    def __init__(self, tab):
        self.tab = tab
        self.interp = dukpy.JSInterpreter()
        self.interp.export_function("log", print)
        self.interp.export_function("querySelectorAll", self.querySelectorAll)

        # handle-to-node map (js to python)
        self.node_to_handle = {}
        self.handle_to_node = {}

        self.interp.evaljs(RUNTIME_JS)

    def querySelectorAll(self, selector_text):
        selector = CssParser(selector_text).selector()

        nodes = [node for node in tree_to_list(self.tab.nodes, []) if selector.matches(node)]

        return [self.get_handle(node) for node in nodes]

    def get_handle(self, elt):
        if elt not in self.node_to_handle:
            handle = len(self.node_to_handle)
            self.node_to_handle[elt] = handle
            self.handle_to_node[handle] = elt
        else:
            handle = self.node_to_handle[elt]
        return handle

    # don't allow js crashes to take the browser with it
    def run(self, script, code):
        try:
            return self.interp.evaljs(code)
        except dukpy.JSRuntimeError as e:
            print("Script", script, "crashed", e)

def cascade_priority(rule):
    selector, body = rule
    return selector.priority

def tree_to_list(tree, list):
    list.append(tree)
    for child in tree.children:
        tree_to_list(child, list)
    return list

def paint_tree(layout_object, display_list):
    if layout_object.should_paint():
        display_list.extend(layout_object.paint())

    for child in layout_object.children:
        paint_tree(child, display_list)

def print_tree(node, indent=0):
    print(' ' * indent, node)
    for child in node.children:
        print_tree(child, indent+2)

DEFAULT_STYLE_SHEET = CssParser(open('browser.css').read()).parse() # browser style sheet - defines default styles

if __name__ == '__main__':
    # import sys
    Browser().new_tab(Url('http://localhost:8000/'))
    tkinter.mainloop()