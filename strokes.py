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
import io
import itertools
import json
import logging
import os
import random
import requests
import uuid


from PyPDF2 import PdfFileMerger


from flask import Flask, Response, request

app = Flask(__name__)


PAGE_SIZE = (200, 300)
LOGGER = logging.getLogger(__name__)
CURRENT_FILE = __file__ if '__file__' in globals() else ''
TMPDIR = '%s/imagecache/' % os.path.dirname(os.path.abspath(CURRENT_FILE))


HEADER_SINGLE = '''
<svg width="100%%" height="100%%" viewBox="0 0 %d %d" version="1.1"
xmlns="http://www.w3.org/2000/svg"
xmlns:xlink="http://www.w3.org/1999/xlink">''' % PAGE_SIZE

PATH_TPL = '<path d="%s" stroke="black" stroke-width="%d" fill="white"></path>'

FOOTER_SINGLE = '</svg>'


HEADER = '''
<svg version="1.1" viewBox="0 0 1024 1024" xmlns="http://www.w3.org/2000/svg">
'''

HEADER2 = '''
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

IMAGE_TPL = '<svg x="%d" y="%d" width="%d" height="%d">%s</svg>'

FOOTER = '''
    </g>
</svg>
'''

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


def generate_image(C, strokes, img_num, skip_strokes, stop_at,
                   add_pinyin=True):

    add_text = P[C] if add_pinyin else ''

    with io.StringIO() as f:

        f.write(''.join([HEADER, '<text x="50" y="950" font-size="300px">',
                        add_text, '</text>', HEADER2]))
        for n, stroke in enumerate(strokes):
            if n < skip_strokes or n >= stop_at:
                continue
            # IMHO this can safely be hardcoded because it's relative
            # to this image
            line_size = (20 if n - 1 < img_num else 10)
            f.write(PATH_TPL % (stroke, line_size))
        f.write(FOOTER)
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
                    yield C, generate_image(C, strokes, n, 0, 99, False)
                    continue

                # draw n-th stroke alone
                for j in range(num_repeats):
                    # we only want to print pinyin on first repetition of first
                    # stroke - this is when it's most likely its text won't
                    # overlap at the bottom of the tile
                    add_text = n == 0 and j == 0
                    yield C, generate_image(C, strokes, n, 0, n + 1, add_text)

                # whole character, highlight n-th stroke
                for _ in range(num_repeats):
                    yield C, generate_image(C, strokes, n, 0, 99, False)

                # draw n-th stroke into context
                for _ in range(num_repeats):
                    yield C, generate_image(C, strokes, n, n + 1, 99, False)

        repeats = chunk * num_repeats * 2
        random.shuffle(repeats)
        for C in repeats:
            yield C, generate_image(C, [], 0, 0, 0)


class Header:

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
        return ret


def gen_svg(size, gen_images_iter):

    fpaths = []
    keep_going = True
    page_drawn = 0
    while keep_going:
        page_drawn += 1
        fpath = os.path.join(TMPDIR, str(uuid.uuid4()) + '.svg')
        fpaths.append(os.path.abspath(fpath))
        with open(fpath, 'w') as f:
            num_per_row = PAGE_SIZE[0] // size
            num_rows = PAGE_SIZE[1] // size
            f.write(HEADER_SINGLE)
            hdr = Header()
            for i in range(num_per_row * (num_rows - 1)):
                try:
                    C, text = next(gen_images_iter)
                    hdr.observe_char(C)
                except StopIteration:
                    keep_going = False
                    break
                x = (i % num_per_row) * size
                y = ((i // num_per_row) + 1) * size
                if ((i // num_per_row) + 3) > num_rows:
                    break
                f.write(IMAGE_TPL % (x, y, size, size, text))

            header = hdr.get_text(page_drawn)
            f.write('<text x="0" y="5" font-size="5px">%s</text>' % header)
            f.write(FOOTER_SINGLE)
    return fpaths


def gen_pdf(infile, outfile):
    with open(outfile, 'wb') as f:
        with open(infile, "rb") as f_read:
            data_b64 = base64.b64encode(f_read.read()).decode('ascii')
        datauri = 'data:image/svg+xml;base64,' + data_b64
        resp = requests.post('http://html2pdf:5000/html2pdf', {'url': datauri})
        f.write(resp.content)


def join_pdfs(pdfs, outpath=None):

    merger = PdfFileMerger()

    for pdf in pdfs:
        merger.append(open(pdf, 'rb'))

    outpath = outpath or os.path.join(TMPDIR, str(uuid.uuid4()) + '.pdf')
    with open(outpath, 'wb') as fout:
        merger.write(fout)
    return outpath


def draw(input_characters, size, num_repeats):

    LOGGER.info('Generating SVG...')

    gen_images_iter = iter(gen_images(input_characters, num_repeats))

    base_path = os.getcwd() + '/' + str(abs(hash(input_characters)))
    out_path = base_path + '.pdf'
    svg_paths = gen_svg(size, gen_images_iter)

    LOGGER.error('Generating pdfs...')
    pdf_paths = []
    for n, svg_path in enumerate(svg_paths):
        pdf_path = base_path + str(n) + '.pdf'
        pdf_paths.append(pdf_path)
        gen_pdf(svg_path, pdf_path)
        os.unlink(svg_path)

    out_pdf_path = join_pdfs(pdf_paths, out_path)

    return out_pdf_path


@app.route('/gen_strokes', methods=['POST'])
def gen_strokes():
    size = int(request.form.get('size') or 10)
    num_repetitions = int(request.form.get('nr') or 3)
    C = request.form.get('chars') or 'X'
    out_path = draw(C, size, num_repetitions)
    with open(out_path, 'rb') as f:
        return Response(f.read(), mimetype='application/pdf')


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
