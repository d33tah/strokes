#!/usr/bin/env python3

import base64
import collections
import io
import json
import random
import unicodedata
import unittest
import unittest.mock

import requests

from PyPDF2 import PdfFileMerger
from flask import Flask, Response, request

__doc__ = '''
Generates a file that can be used for learning how to write a specific
Chinese character, when printed.

For a description of the deployment, look at the Dockerfile.

Requires downloading the following files:

    https://raw.githubusercontent.com/skishore/makemeahanzi/master/graphics.txt
    https://raw.githubusercontent.com/skishore/makemeahanzi/master/dictionary.txt
'''

__TODO__ = '''
*** TODO ***

Bugs:

    * figure out zooming in previews, get rid of two preview modes

UX:

    * add print margins?
    * progress reporting?
    * more options: how many repetitions of each stroke, how many characters
      does it take to switch to random mode?
    * custom titles
    * make frontend cuter

Learning:

    * repetition mode: show two strokes at once?

Testing and refactoring:

    * make all html views validate
    * better error reporting
    * selenium tests
    * unit tests

------------------------------------------------------------------------------
'''

app = Flask(__name__)


PAGE_SIZE = (200, 300)
CHUNK_SIZE = 4
LINE_THICK = 30


def load_strokes_db(graphics_txt_path):
    ret = {}
    with open(graphics_txt_path, 'r', encoding='utf8') as f:
        for line in f:
            x = json.loads(line)
            ret[x['character']] = x
    return ret


def load_dictionary(dictionary_txt_path):
    d = {}
    with open(dictionary_txt_path, 'r') as f:
        for line in f:
            j = json.loads(line)
            if j['pinyin']:
                d[j['character']] = j
    return d


STROKES_DB = load_strokes_db('graphics.txt')
PINYIN_DB = load_dictionary('dictionary.txt')


class Tile:
    """Class responsible for preparing SVG code describing a single tine.

    It's used for storage of data related to rendering - i.e. group it belongs
    to. I could probably get away with dict + function but it'd be uglier.

    Also, set_dimensions had to be deferred because gen_images_iter can't know
    it."""

    SVG_HEADER = '''<svg x="%(x)d" y="%(y)d" width="%(size)d"
        height="%(size)d"><svg version="1.1" viewBox="0 0 1024 1024"
        xmlns="http://www.w3.org/2000/svg">'''

    PREAMBLE = '''
        <g stroke="black" stroke-width="2" transform="scale(4, 4)">
            <line x1="0" y1="0" x2="0" y2="256"
                stroke-width="%(leftline_width)d"></line>
            <line x1="0" y1="0" x2="256" y2="256"></line>
            <line x1="256" y1="0" x2="0" y2="256"></line>
            <line x1="256" y1="0" x2="0" y2="0"
                stroke-width="%(topline_width)d"></line>
            <line x1="256" y1="0" x2="256" y2="256"></line>
            <line x1="128" y1="0" x2="128" y2="256"></line>
            <line x1="0" y1="128" x2="256" y2="128"></line>
            <line x1="0" y1="256" x2="256" y2="256"></line>
        </g>
        <g transform="scale(1, -1) translate(0, -900)">
    '''

    PATH_TPL = '''<path d="%s" stroke="black" stroke-width="%d"
        fill="white"></path>'''

    FOOTER = '''</g></svg></svg>'''

    def __init__(self, C, chunk, strokes, highlight_until, skip_strokes,
                 stop_at, add_pinyin=True, skip_in_header=False,
                 add_radical=False):

        self.C = C
        self.chunk = chunk
        self.strokes = strokes
        self.highlight_until = highlight_until
        self.skip_strokes = skip_strokes
        self.stop_at = stop_at
        self.add_pinyin = add_pinyin
        self.add_radical = add_radical
        self.skip_in_header = skip_in_header
        self.x = None
        self.y = None
        self.size = None
        self.leftline_width = 10
        self.topline_width = 10

    def set_dimensions(self, x, y, size):
        self.x = x
        self.y = y
        self.size = size

    def render(self):

        if not all([self.size, self.y, self.size]):
            raise RuntimeError("Call set_dimensions first!")

        if not self.add_pinyin:
            add_text = ''
        else:
            db_entry = PINYIN_DB[self.C]
            add_text = db_entry['pinyin'][0]
            if self.add_radical:
                add_text += db_entry['radical']
        add_text_svg = ('''<text x="50" y="950"
            font-size="250px">%s</text>''' % add_text)
        header_args = {'x': self.x, 'y': self.y, 'size': self.size}
        preamble_args = {'leftline_width': self.leftline_width,
                         'topline_width': self.topline_width}

        with io.StringIO() as f:

            f.write(''.join([self.SVG_HEADER % header_args, add_text_svg,
                             self.PREAMBLE % preamble_args]))
            for n, stroke in enumerate(self.strokes):
                if n < self.skip_strokes or n >= self.stop_at:
                    continue
                # IMHO this can safely be hardcoded because it's relative
                # to this image
                line_size = (20 if n - 1 < self.highlight_until else 10)
                f.write(self.PATH_TPL % (stroke, line_size))
            f.write(self.FOOTER)
            return f.getvalue()


def grouper(l):
    """
    Generate an iterator that works like this:

    ['A', 'B', 'AB', 'C', 'D', 'CD', 'ABCD', 'E', …]

    Solved thanks to this solution to my codegolf puzzle:

    https://codegolf.stackexchange.com/a/168978/17159
    """
    (u, v) = (1, 1)
    while True:
        to_yield = ''.join(l[u-v:u])
        if not to_yield:
            break
        yield to_yield
        v = u // v % 2 or 2 * v
        u += 1 // v


def gen_images(input_characters, num_repeats):
    """This is where the learning logic sits.

    We iterate over input_characters grouped in groups and by each stroke of
    each character, generating num_repeats of titles of various types. At
    the end, we optionally randomly ask the user to write those based on
    pinyin."""

    for chunk_iter in grouper(input_characters):
        chunk = list(chunk_iter)
        if len(chunk) > 1:

            pinyins = [PINYIN_DB[C]['pinyin'][0] for C in chunk]
            pinyins_repeating = {p for p in pinyins if pinyins.count(p) > 1}

            random.shuffle(chunk)
            for C in chunk:
                pinyin = PINYIN_DB[C]['pinyin'][0]
                yield Tile(C, chunk, [], 0, 0, 0, skip_in_header=True,
                           add_radical=pinyin in pinyins_repeating)
            continue

        # else
        for C in chunk:
            strokes = STROKES_DB[C]['strokes']
            for n in range(len(strokes)):

                if num_repeats == 0:
                    yield Tile(C, chunk, strokes, n, 0, 99, False)
                    continue

                # draw n-th stroke alone
                for j in range(num_repeats):
                    # we only want to print pinyin on first repetition of first
                    # stroke - this is when it's most likely its text won't
                    # overlap at the bottom of the tile
                    add_text = n == 0 and j == 0
                    yield Tile(C, chunk, strokes, n, n, n + 1, add_text)

                # draw n-th stroke and all previous ones
                for _ in range(num_repeats):
                    yield Tile(C, chunk, strokes, n, 0, n + 1, False)

                # whole character, highlight n-th stroke
                for _ in range(num_repeats):
                    yield Tile(C, chunk, strokes, n, 0, 99, False)

                # draw n-th stroke into context
                for _ in range(num_repeats):
                    yield Tile(C, chunk, strokes, n, n + 1, 99, False)


class Header:
    """The responsibility of this class is to manage the header - i.e. make
    sure it's split into two lines."""

    def __init__(self):
        self.header = ''
        self.chars_drawn = []

    def observe_char(self, C):
        if C in self.chars_drawn:
            return
        self.chars_drawn.append(C)
        if self.header:
            self.header += ', '
        # header[1:] was chosen so that we don't catch first
        # tspan.
        if len(self.header) > 75 and '<tspan' not in self.header[1:]:
            self.header += '</tspan><tspan x="0" dy="1.2em">'
        self.header += '%s (%s' % (C, PINYIN_DB[C]['pinyin'][0])
        self.header += PINYIN_DB[C]['radical']
        self.header += ')'

    def get_text(self, page_drawn):
        return '''<text x="0" y="5" font-size="5px"><tspan x="0" dy="0em"
            >%d: %s</tspan></text>''' % (page_drawn, self.header)


class Page:

    HEADER_SINGLE = '''<svg width="100%%" height="100%%" viewBox="0 0 %d %d"
    version="1.1" xmlns="http://www.w3.org/2000/svg"
    xmlns:xlink="http://www.w3.org/1999/xlink">''' % PAGE_SIZE

    FOOTER_SINGLE = '</svg>'

    def __init__(self, page_drawn, tile_size, gen_images_iter):
        self.page_drawn = page_drawn
        self.tiles_by_pos = collections.defaultdict(dict)
        self.hdr = Header()
        self.tile_size = tile_size
        self.gen_images_iter = gen_images_iter
        self.f = io.StringIO()
        self.rendered = ''

    def gen_positions(self):

        num_per_row = PAGE_SIZE[0] // self.tile_size
        num_rows = PAGE_SIZE[1] // self.tile_size

        for i in range(num_per_row * (num_rows - 1)):

            row_num = i % num_per_row
            col_num = i // num_per_row

            if ((i // num_per_row) + 3) > num_rows:
                # this page is full, move on to generating another
                break

            yield row_num, col_num

    def maybe_draw_border(self, tile, row_num, col_num):
        if row_num > 0 and (self.tiles_by_pos[row_num - 1][col_num].chunk
                            != tile.chunk):
            tile.leftline_width = LINE_THICK
        if col_num > 0 and (self.tiles_by_pos[row_num][col_num - 1].chunk
                            != tile.chunk):
            tile.topline_width = LINE_THICK

    def write_tiles(self, f):

        for row_num, col_num in self.gen_positions():

            x = row_num * self.tile_size
            y = (col_num + 1) * self.tile_size

            tile = next(self.gen_images_iter)
            self.tiles_by_pos[row_num][col_num] = tile
            tile.set_dimensions(x, y, self.tile_size)

            if not tile.skip_in_header:
                self.hdr.observe_char(tile.C)

            self.maybe_draw_border(tile, row_num, col_num)

            f.write(tile.render())

        return True

    def prepare(self):
        """Renders the page and returns a boolean that tells whether it was
        the last one."""

        self.f.write(self.HEADER_SINGLE)
        try:
            self.write_tiles(self.f)
        finally:
            # in the last page, we will get StopIteration. Regardless of it,
            # We need to finalize rendering.
            self.f.write(self.hdr.get_text(self.page_drawn))
            self.f.write(self.FOOTER_SINGLE)


def gen_svgs(size, gen_images_iter):

    pages = []
    page_drawn = 0
    while True:
        page_drawn += 1
        page = Page(page_drawn, size, gen_images_iter)
        pages.append(page)
        try:
            page.prepare()
        except StopIteration:
            break
    return pages


def gen_pdf(svg_code):
    data_b64 = base64.b64encode(svg_code.encode('utf8')).decode('ascii')
    datauri = 'data:image/svg+xml;base64,' + data_b64
    resp = requests.post('http://html2pdf:5000/html2pdf', {'url': datauri})
    return resp.content


def gen_pdfs(pages):

    merger = PdfFileMerger()
    pdf_files = []
    try:
        for page in pages:
            pdf = gen_pdf(page.f.getvalue())
            pdf_f = io.BytesIO(pdf)
            pdf_files.append(pdf_f)
            merger.append(pdf_f)

        with io.BytesIO() as fout:
            merger.write(fout)
            return fout.getvalue()
    finally:
        for pdf_f in pdf_files:
            pdf_f.close()


def gen_html(pages, small=True):
    # just put together the stream of SVG images
    body = ['<body>']
    for page in pages:
        svg_code = page.f.getvalue()
        if small:
            body.append(svg_code)
            continue
        # The following zooms the images in, but doesn't allow zooming out
        data_b64 = base64.b64encode(svg_code.encode('utf8')).decode('ascii')
        datauri = 'data:image/svg+xml;base64,%s' % data_b64
        body.append('<img src="%s" />' % datauri)
    return ''.join(body)


def pinyin_sortable(chinese_character):
    # FIXME: this is ugly because I was bugfixing it without refactoring
    pinyin = PINYIN_DB[chinese_character]['pinyin'][0]
    accent_to_number = {
        ' WITH MACRON': '1',
        ' WITH ACUTE': '2',
        ' WITH CARON': '3',
        ' WITH GRAVE': '4',
    }
    ret = []
    tones = []
    for c in pinyin:
        n = unicodedata.name(c)
        for k, v in accent_to_number.items():
            if k in n:
                n = n.replace(k, '')
                tones.append(v)
        ret.append(unicodedata.lookup(n))
    return ''.join(ret) + ''.join(tones)


class PinyinSortableTest(unittest.TestCase):

    def test_hao3(self):
        self.assertEqual(pinyin_sortable('好'), 'hao3')

    def test_hao4(self):
        self.assertEqual(pinyin_sortable('号'), 'hao4')


def sort_input(input_characters, sorting, nodupes):
    if nodupes:
        ordereddict = collections.OrderedDict.fromkeys(input_characters)
        input_characters = ''.join(ordereddict)
    if sorting == 'none':
        return input_characters
    elif sorting == 'pinyin':
        return sorted(input_characters, key=pinyin_sortable)
    else:
        raise ValueError('Unknown sort mode: %r' % sorting)


def draw(input_characters, size, num_repeats, action):

    gen_images_iter = iter(gen_images(input_characters, num_repeats))
    pages = gen_svgs(size, gen_images_iter)

    if action == 'generate':
        return [gen_pdfs(pages)], {'mimetype': 'application/pdf'}
    if action == 'preview_small':
        return [gen_html(pages)], {'mimetype': 'text/html'}
    if action == 'preview_large':
        return [gen_html(pages, False)], {'mimetype': 'text/html'}
    body = '<h1>Invalid action: %r</h1>' % action
    return [body], {'mimetype': 'text/html', 'status': 400}


def ret_error(err):
        kwargs = {'status': 400, 'mimetype': 'text/html'}
        return Response('<h1>%s</h1>' % err, **kwargs)


@app.route('/gen_strokes')
def gen_strokes():

    form_d = dict(request.args)

    scale_s = form_d.pop('scale', ['100'])[0] or '100'
    try:
        scale = int(scale_s)
    except ValueError:
        err = 'Invalid tile scale: %r (should be a number)' % scale_s
        return ret_error(err)
    size = int(15 * scale / 100.0)

    num_repetitions_s = form_d.pop('nr', ['1'])[0] or '1'
    try:
        num_repetitions = int(num_repetitions_s)
    except ValueError:
        return ret_error(('Invalid number of repetitions: %r '
                          '(should be a number)') % num_repetitions_s)

    if 'chars' not in form_d:
        resp_kwargs = {'status': 400, 'mimetype': 'text/html'}
        return Response('No input characters specified.', **resp_kwargs)
    C = form_d.pop('chars')[0]
    C = ''.join(C.split())  # strip all whitespace

    action = form_d.pop('action', ['preview'])[0]
    sort_mode = form_d.pop('sorting', ['none'])[0]
    nodupes = form_d.pop('nodupes', [False])[0]

    if form_d:
        return ret_error('Unexpected form data: %r' % form_d)

    try:
        C = sort_input(C, sort_mode, nodupes)
    except ValueError:
        return ret_error('Unexpected sorting: %r' % sort_mode)

    try:
        resp_args, resp_kwargs = draw(C, size, num_repetitions, action)
    except KeyError as e:
        resp_args = ['<h1>Unknown character: %r</h1>' % e.args[0]]
        resp_kwargs = {'status': 400, 'mimetype': 'text/html'}
    return Response(*resp_args, **resp_kwargs)


@app.route('/')
def index():
    git_version = ''
    try:
        with open('commit-id') as f:
            ver_str = f.read().strip()
            git_version = '<!-- Current program version: %s -->' % ver_str
    except FileNotFoundError:
        pass
    return '''<!doctype html><html lang="en"><head>%s
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1,
        shrink-to-fit=no">

    <link rel="stylesheet"
href="https://stackpath.bootstrapcdn.com/bootswatch/4.1.2/cerulean/bootstrap.min.css"
        crossorigin="anonymous">

    <title>Strokes - home page</title>
  </head>
  <body>
    <div class="container bs-component">
    <h1>Strokes</h1>

        <p><em>This is a test website of Strokes project. Keep in mind that
        it's running on the cheapest $5 server, so please be gentle ;) For more
        information, click
        <a href="https://github.com/d33tah/strokes/blob/master/README.md"
            >HERE</a>.</em></p>

        <form action="/gen_strokes" method="get">
        <p>Characters: <input type="text" name="chars"
            value="一二三四五六七八"/></p>
        <p>Scale (%%): <input type="text" name="scale" value="100"/></p>
        <p>Number of repetitions. 0 means "no repetitions"; useful if you're
            just trying to quickly get familiar with many characters:
            <input type="text" name="nr" value="1"/></p>
        <h2>Sorting</h2>


            <fieldset class="form-group">
            <div class="custom-control custom-radio">
            <input id="sorting_none"
                class="custom-control-input" type="radio" name="sorting"
                value="none" checked>
            <label class="custom-control-label" for="sorting_none">
            None</label>
            </div>

            <div class="custom-control custom-radio">
            <input class="custom-control-input" type="radio" name="sorting"
                value="pinyin" id="sorting_pinyin">
            <label class="custom-control-label" for="sorting_pinyin">
             Pinyin</label>
            </div>

            <div class="custom-control custom-radio">
            <input class="custom-control-input" type="radio" name="sorting"
                value="random" id="sorting_random">
            <label class="custom-control-label" for="sorting_random">
             Pinyin</label>
            </div>

            <div class="custom-control custom-checkbox">
            <input class="custom-control-input" type="checkbox"
                name="nodupes" value="true" id="sorting_nodupes">
            <label class="custom-control-label" for="sorting_nodupes">
            Remove duplicates</label>
            </div>
            </fieldset>

        <button class="btn btn-primary" type="submit" value="generate"
            name="action">Generate (PDF, slow)</button>
        <button class="btn btn-primary" type="submit" value="preview_small"
            name="action">Preview (SVG, zoomed out)</button>
        <button class="btn btn-primary" type="submit" value="preview_large"
            name="action">Preview (SVG, zoomed in)</button>
    </form>
    </div>

  </body>
</html>''' % git_version


def MINIMAL_PDF_MOCK(*_, **__):
    return base64.b64decode(b'''
        JVBERi0xLjEKJcKlwrHDqwoKMSAwIG9iagogIDw8IC9UeXBlIC9DYXRhbG9n
        CiAgICAgL1BhZ2VzIDIgMCBSCiAgPj4KZW5kb2JqCgoyIDAgb2JqCiAgPDwg
        L1R5cGUgL1BhZ2VzCiAgICAgL0tpZHMgWzMgMCBSXQogICAgIC9Db3VudCAx
        CiAgICAgL01lZGlhQm94IFswIDAgMzAwIDE0NF0KICA+PgplbmRvYmoKCjMg
        MCBvYmoKICA8PCAgL1R5cGUgL1BhZ2UKICAgICAgL1BhcmVudCAyIDAgUgog
        ICAgICAvUmVzb3VyY2VzCiAgICAgICA8PCAvRm9udAogICAgICAgICAgIDw8
        IC9GMQogICAgICAgICAgICAgICA8PCAvVHlwZSAvRm9udAogICAgICAgICAg
        ICAgICAgICAvU3VidHlwZSAvVHlwZTEKICAgICAgICAgICAgICAgICAgL0Jh
        c2VGb250IC9UaW1lcy1Sb21hbgogICAgICAgICAgICAgICA+PgogICAgICAg
        ICAgID4+CiAgICAgICA+PgogICAgICAvQ29udGVudHMgNCAwIFIKICA+Pgpl
        bmRvYmoKCjQgMCBvYmoKICA8PCAvTGVuZ3RoIDU1ID4+CnN0cmVhbQogIEJU
        CiAgICAvRjEgMTggVGYKICAgIDAgMCBUZAogICAgKEhlbGxvIFdvcmxkKSBU
        agogIEVUCmVuZHN0cmVhbQplbmRvYmoKCnhyZWYKMCA1CjAwMDAwMDAwMDAg
        NjU1MzUgZiAKMDAwMDAwMDAxOCAwMDAwMCBuIAowMDAwMDAwMDc3IDAwMDAw
        IG4gCjAwMDAwMDAxNzggMDAwMDAgbiAKMDAwMDAwMDQ1NyAwMDAwMCBuIAp0
        cmFpbGVyCiAgPDwgIC9Sb290IDEgMCBSCiAgICAgIC9TaXplIDUKICA+Pgpz
        dGFydHhyZWYKNTY1CiUlRU9GCg==''')


# I was too lazy to write regular unit tests and this is already pretty fast
# and gives decent coverage, so some red flags will be caught:
class SystemTests(unittest.TestCase):

    def setUp(self):
        app.testing = True
        self.app = app.test_client()

    def test_get_index(self):
        rv = self.app.get('/')
        self.assertEqual(rv.status, '200 OK')

    def test_fivedigits_smallpreview(self):
        data = {'scale': 12, 'nr': 1, 'action': 'preview_small',
                'chars': '一二三四五'}
        rv = self.app.get('/gen_strokes', query_string=data)
        self.assertEqual(rv.status, '200 OK')

    def test_fivedigits_smallpreview_norepeats(self):
        data = {'scale': 12, 'nr': 0, 'action': 'preview_small',
                'chars': '一二三四五'}
        rv = self.app.get('/gen_strokes', query_string=data)
        self.assertEqual(rv.status, '200 OK')

    def test_fivedigits_bigpreview(self):
        data = {'scale': 12, 'nr': 1, 'action': 'preview_large',
                'chars': '一二三四五'}
        rv = self.app.get('/gen_strokes', query_string=data)
        self.assertEqual(rv.status, '200 OK')

    def test_xiexie_multipage(self):
        data = {'scale': 30, 'nr': 10, 'action': 'preview_small',
                'chars': '谢'}
        rv = self.app.get('/gen_strokes', query_string=data)
        self.assertEqual(rv.status, '200 OK')

    def test_invalid_action_signals_error(self):
        data = {'scale': 12, 'nr': 1, 'action': 'invalid',
                'chars': '一二三四五'}
        rv = self.app.get('/gen_strokes', query_string=data)
        self.assertNotEqual(rv.status, '200 OK')

    def test_multiline_header(self):
        data = {'scale': 12, 'nr': 1, 'action': 'preview_small',
                'chars': '一七三上下不东个中么九习书买了二五些京亮人什'}
        rv = self.app.get('/gen_strokes', query_string=data)
        self.assertEqual(rv.status, '200 OK')

    @unittest.mock.patch.dict(globals(), {'gen_pdf': MINIMAL_PDF_MOCK})
    def test_gen_pdf(self):
        data = {'scale': 12, 'nr': 1, 'action': 'generate',
                'chars': '一二三四五'}
        rv = self.app.get('/gen_strokes', query_string=data)
        self.assertEqual(rv.status, '200 OK')

    def test_sorting_pinyin_ok(self):
        data = {'scale': 12, 'nr': 1, 'action': 'preview_small',
                'chars': '一二三四五', 'sorting': 'pinyin'}
        rv = self.app.get('/gen_strokes', query_string=data)
        self.assertEqual(rv.status, '200 OK')

    def test_sorting_random_ok(self):
        data = {'scale': 12, 'nr': 1, 'action': 'preview_small',
                'chars': '一二三四五', 'sorting': 'random'}
        rv = self.app.get('/gen_strokes', query_string=data)
        self.assertEqual(rv.status, '200 OK')

    def test_nodupes(self):
        data = {'scale': 12, 'nr': 1, 'action': 'preview_small',
                'chars': '一二三四五', 'nodupes': 'true'}
        rv = self.app.get('/gen_strokes', query_string=data)
        self.assertEqual(rv.status, '200 OK')

    def test_nochars(self):
        data = {'scale': 12, 'nr': 1, 'action': 'preview_small'}
        rv = self.app.get('/gen_strokes', query_string=data)
        self.assertNotEqual(rv.status, '200 OK')

    def test_unexpected_post(self):
        data = {'scale': 12, 'nr': 1, 'chars': '一',
                'action': 'preview_small', 'wtf': 'yes'}
        rv = self.app.get('/gen_strokes', query_string=data)
        self.assertNotEqual(rv.status, '200 OK')

    def test_unexpected_sorting(self):
        data = {'scale': 12, 'nr': 1, 'chars': '一',
                'action': 'preview_small', 'sorting': '?'}
        rv = self.app.get('/gen_strokes', query_string=data)
        self.assertNotEqual(rv.status, '200 OK')

    def test_unexpected_character(self):
        data = {'scale': 12, 'nr': 1, 'chars': 'A',
                'action': 'preview_small'}
        rv = self.app.get('/gen_strokes', query_string=data)
        self.assertNotEqual(rv.status, '200 OK')
