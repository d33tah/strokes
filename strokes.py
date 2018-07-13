#!/usr/bin/env python3

'''
Generates a file that can be used for learning how to write a specific
Chinese character, when printed.

For a description of the deployment, look at the Dockerfile.

Requires downloading the following files:

    https://raw.githubusercontent.com/skishore/makemeahanzi/master/graphics.txt
    https://raw.githubusercontent.com/skishore/makemeahanzi/master/dictionary.txt

TODO:

    * add print margins?
    * more options: how many repetitions of each stroke, how many characters
      does it take to switch to random mode?
    * repetition mode: show two strokes at once?
    * make frontend cuter
    * custom titles
    * move all initialization outside of the hot loop

------------------------------------------------------------------------------
'''

import base64
import collections
import io
import itertools
import json
import logging
import random
import requests


from PyPDF2 import PdfFileMerger
from flask import Flask, Response, request

app = Flask(__name__)


PAGE_SIZE = (200, 300)
LOGGER = logging.getLogger(__name__)
CURRENT_FILE = __file__ if '__file__' in globals() else ''
CHUNK_SIZE = 4


def load_strokes_db(graphics_txt_path):
    ret = {'X': []}
    with open(graphics_txt_path, 'r', encoding='utf8') as f:
        for line in f:
            x = json.loads(line)
            ret[x['character']] = x['strokes']
    return ret


def load_dictionary(dictionary_txt_path):
    d = {'X': ''}
    with open(dictionary_txt_path, 'r') as f:
        for line in f:
            j = json.loads(line)
            if j['pinyin']:
                d[j['character']] = j['pinyin'][0]
    return d


STROKES_DB = load_strokes_db('graphics.txt')
P = load_dictionary('dictionary.txt')


class Tile:
    """Class responsible for preparing SVG code describing a single tine.

    The reason it exists right now is because otherwise I would have to
    additionally hold 'C' variable and I plan to keep more data here."""

    SVG_HEADER = '''<svg x="%(x)d" y="%(y)d" width="%(size)d"
        height="%(size)d"><svg version="1.1" viewBox="0 0 1024 1024"
        xmlns="http://www.w3.org/2000/svg">'''

    PREAMBLE = '''
        <g stroke="black" stroke-width="2" transform="scale(4, 4)">
            <line x1="0" y1="0" x2="0" y2="256" stroke-width="10"></line>
            <line x1="0" y1="0" x2="256" y2="256"></line>
            <line x1="256" y1="0" x2="0" y2="256"></line>
            <line x1="256" y1="0" x2="0" y2="0" stroke-width="10"></line>
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

    def __init__(self, C, chunk, strokes, img_num, skip_strokes, stop_at,
                 add_pinyin=True, skip_in_header=False):

        self.C = C
        self.chunk = chunk
        self.strokes = strokes
        self.img_num = img_num
        self.skip_strokes = skip_strokes
        self.stop_at = stop_at
        self.add_pinyin = add_pinyin
        self.skip_in_header = skip_in_header
        self.x = None
        self.y = None
        self.size = None

    def set_dimensions(self, x, y, size):
        self.x = x
        self.y = y
        self.size = size

    def render(self):

        if not all([self.size, self.y, self.size]):
            raise RuntimeError("Call set_dimensions first!")

        add_text = P[self.C] if self.add_pinyin else ''
        add_text_svg = ('''<text x="50" y="950"
            font-size="300px">%s</text>''' % add_text)

        with io.StringIO() as f:

            header_args = {'x': self.x, 'y': self.y, 'size': self.size}
            f.write(''.join([self.SVG_HEADER % header_args, add_text_svg,
                             self.PREAMBLE]))
            for n, stroke in enumerate(self.strokes):
                if n < self.skip_strokes or n >= self.stop_at:
                    continue
                # IMHO this can safely be hardcoded because it's relative
                # to this image
                line_size = (20 if n - 1 < self.img_num else 10)
                f.write(self.PATH_TPL % (stroke, line_size))
            f.write(self.FOOTER)
            return f.getvalue()


def grouper(iterable, n):
    while True:
        yield itertools.chain([next(iterable)],
                              itertools.islice(iterable, n-1))


def gen_images(input_characters, num_repeats):
    for chunk_iter in grouper(iter(input_characters), CHUNK_SIZE):
        chunk = list(chunk_iter)
        for C in chunk:
            strokes = STROKES_DB[C]
            num_strokes = len(strokes)
            for n in range(num_strokes):

                if num_repeats == 0:
                    yield Tile(C, chunk, strokes, n, 0, 99, False)
                    continue

                # draw n-th stroke alone
                for j in range(num_repeats):
                    # we only want to print pinyin on first repetition of first
                    # stroke - this is when it's most likely its text won't
                    # overlap at the bottom of the tile
                    add_text = n == 0 and j == 0
                    yield Tile(C, chunk, strokes, n, 0, n + 1, add_text)

                # whole character, highlight n-th stroke
                for _ in range(num_repeats):
                    yield Tile(C, chunk, strokes, n, 0, 99, False)

                # draw n-th stroke into context
                for _ in range(num_repeats):
                    yield Tile(C, chunk, strokes, n, n + 1, 99, False)

        repeats = chunk * num_repeats * 2
        random.shuffle(repeats)
        for C in repeats:
            yield Tile(C, chunk, [], 0, 0, 0, skip_in_header=True)


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
        self.header += '%s (%s)' % (C, P[C])

    def get_text(self, page_drawn):
        ret = '<tspan x="0" dy="0em">%d: %s</tspan>' % (page_drawn,
                                                        self.header)
        if '<tspan>' in self.header[1:]:
            self.header += '</tspan>'
        return '<text x="0" y="5" font-size="5px">%s</text>' % ret


class Page:

    HEADER_SINGLE = '''<svg width="100%%" height="100%%" viewBox="0 0 %d %d"
    version="1.1" xmlns="http://www.w3.org/2000/svg"
    xmlns:xlink="http://www.w3.org/1999/xlink">''' % PAGE_SIZE

    FOOTER_SINGLE = '</svg>'

    def __init__(self, page_drawn, tile_size, gen_images_iter):
        self.page_drawn = page_drawn
        self.tiles = collections.defaultdict(dict)
        self.num_per_row = PAGE_SIZE[0] // tile_size
        self.num_rows = PAGE_SIZE[1] // tile_size
        self.hdr = Header()
        self.tile_size = tile_size
        self.gen_images_iter = gen_images_iter
        self.f = io.StringIO()
        self.rendered = ''

    def write_tiles(self, f):
        for i in range(self.num_per_row * (self.num_rows - 1)):
            try:
                tile = next(self.gen_images_iter)
                if not tile.skip_in_header:
                    self.hdr.observe_char(tile.C)
            except StopIteration:
                return False
            row_num = (i % self.num_per_row)
            x = row_num * self.tile_size
            col_num = ((i // self.num_per_row) + 1)
            y = col_num * self.tile_size
            if ((i // self.num_per_row) + 3) > self.num_rows:
                break
            tile.set_dimensions(x, y, self.tile_size)
            self.tiles[row_num][col_num] = tile
            f.write(tile.render())
        return True

    def prepare(self):

        self.f.write(self.HEADER_SINGLE)
        try:
            if not self.write_tiles(self.f):
                return False
        finally:
            self.f.write(self.hdr.get_text(self.page_drawn))
            self.f.write(self.FOOTER_SINGLE)
            self.f.seek(0)
        return True


def gen_svg(size, gen_images_iter):

    pages = []
    page_drawn = 0
    while True:
        page_drawn += 1
        page = Page(page_drawn, size, gen_images_iter)
        pages.append(page)
        if not page.prepare():
            break
    return pages


def gen_pdf(svg_code):
    data_b64 = base64.b64encode(svg_code.encode('utf8')).decode('ascii')
    datauri = 'data:image/svg+xml;base64,' + data_b64
    resp = requests.post('http://html2pdf:5000/html2pdf', {'url': datauri})
    return resp.content


def join_pages(pdfs, outpath=None):

    merger = PdfFileMerger()
    pdf_files = []
    try:
        for pdf in pdfs:
            pdf_f = io.BytesIO(pdf)
            pdf_files.append(pdf_f)
            merger.append(pdf_f)

        with io.BytesIO() as fout:
            merger.write(fout)
            return fout.getvalue()
    finally:
        for pdf_f in pdf_files:
            pdf_f.close()


def draw(input_characters, size, num_repeats):

    LOGGER.info('Generating SVG...')

    gen_images_iter = iter(gen_images(input_characters, num_repeats))

    pages = gen_svg(size, gen_images_iter)

    LOGGER.error('Generating pdfs...')
    pdfs = []
    for n, page in enumerate(pages):
        pdfs.append(gen_pdf(page.f.getvalue()))

    return join_pages(pdfs)


@app.route('/gen_strokes', methods=['POST'])
def gen_strokes():
    size = int(request.form.get('size') or 10)
    num_repetitions = int(request.form.get('nr') or 3)
    C = request.form.get('chars') or 'X'
    return Response(draw(C, size, num_repetitions), mimetype='application/pdf')


@app.route('/')
def index():
    return '''<!DOCTYPE HTML><html><body>
        <form action="/gen_strokes" method="post">
        <p>Characters: <input type="text" name="chars" value="你好"/></p>
        <p>Size: <input type="text" name="size" value="15"/></p>
        <p>Number of repetitions (0 means "no repetitions", try it out):
            <input type="text" name="nr" value="3"/></p>
        <input type="submit" value="Generate strokes">
    </form>
    '''
