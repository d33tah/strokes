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
    * multi-page support: print title only for the current page
    * repetition mode: show two strokes at once?
    * make frontend cuter
    * custom titles
    * move all initialization outside of the hot loop

------------------------------------------------------------------------------
'''

import base64
import io
import json
import logging
import os
import random
import requests
import uuid


from PyPDF2 import PdfFileMerger


from quart import Quart, Response, request

app = Quart(__name__)


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


def generate_image(C, strokes, img_num, skip_strokes, stop_at):

    add_text = P[C]

    with io.StringIO() as f:

        f.write(''.join([HEADER, '<text x="50" y="200" font-size="150px">',
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


def gen_images(input_characters, num_repeats):
    for C in input_characters:
        strokes = STROKES_DB[C]
        num_strokes = len(strokes)
        for i in range(num_strokes):
            for _ in range(num_repeats):
                yield generate_image(C, strokes, i, 0, 99)
    for i in range(10):
        C = random.choice(input_characters)
        yield generate_image(C, [], 0, 0, 0)


def gen_svg(size, header, gen_images_iter):
    fpaths = []
    keep_going = True
    while keep_going:
        fpath = os.path.join(TMPDIR, str(uuid.uuid4()) + '.svg')
        fpaths.append(os.path.abspath(fpath))
        with open(fpath, 'w') as f:
            num_per_row = PAGE_SIZE[0] // size
            num_rows = PAGE_SIZE[1] // size
            f.write(HEADER_SINGLE)
            for i in range(num_per_row * (num_rows - 1)):
                try:
                    text = next(gen_images_iter)
                except StopIteration:
                    keep_going = False
                    break
                x = (i % num_per_row) * size
                y = ((i // num_per_row) + 1) * size
                if ((i // num_per_row) + 3) > num_rows:
                    break
                f.write(IMAGE_TPL % (x, y, size, size, text))
            f.write('<text x="0" y="7" font-size="5px">%s</text>' % header)
            f.write(FOOTER_SINGLE)
    return fpaths


async def gen_pdf(infile, outfile):
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


async def draw(input_characters, size, num_repeats):

    LOGGER.info('Generating SVG...')

    gen_images_iter = iter(gen_images(input_characters, num_repeats))

    header = ', '.join('%s (%s)' % (c, P[c])
                       for c in input_characters)

    base_path = os.getcwd() + '/' + str(abs(hash(input_characters)))
    out_path = base_path + '.pdf'
    svg_paths = gen_svg(size, header, gen_images_iter)

    LOGGER.error('Generating pdfs...')
    pdf_paths = []
    for n, svg_path in enumerate(svg_paths):
        pdf_path = base_path + str(n) + '.pdf'
        pdf_paths.append(pdf_path)
        await gen_pdf(svg_path, pdf_path)
        #os.unlink(svg_path)

    out_pdf_path = join_pdfs(pdf_paths, out_path)

    return out_pdf_path


@app.route('/gen_strokes', methods=['POST'])
async def gen_strokes():
    form = await request.form
    size = int(form.get('size') or 10)
    num_repetitions = int(form.get('nr') or 3)
    C = form.get('chars') or 'X'
    out_path = await draw(C, size, num_repetitions)
    with open(out_path, 'rb') as f:
        return Response(f.read(), mimetype='application/pdf')


@app.route('/')
def index():
    return '''<!DOCTYPE HTML><html><body>
        <form action="/gen_strokes" method="post">
        <p>Characters: <input type="text" name="chars" value="你好"/></p>
        <p>Size: <input type="text" name="size" value="10"/></p>
        <p>Number of repetitions: <input type="text" name="nr" value="3"/></p>
        <input type="submit" value="Generate strokes">
    </form>
    '''
