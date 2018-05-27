import json
import os
import threading
import random
import logging


from pyppeteer import launch


PAGE_SIZE = (200, 300)
LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)


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

IMAGE_TPL = '<image x="%d" y="%d" width="%d" height="%d" xlink:href="%s" />'

FOOTER = '''
    </g>
</svg>
'''


def load_strokes_db(graphics_txt_path):
    with open(graphics_txt_path, 'r', encoding='utf8') as f:
        t = f.read()
    ret = {
        x['character']: x['strokes']
        for l in t.split('\n')
        for x in ([json.loads(l)] if l else [])
    }
    ret['X'] = []
    return ret


def get_image(C, img_num, image_cache, strokes, skip_strokes, stop_at, add_text=''):
    fname = C + '%d-%d-%d.svg' % (img_num, skip_strokes, stop_at)
    if fname in image_cache:
        return fname
    with open(fname, 'w', encoding='utf8') as f:
        f.write(HEADER)
        f.write('<text x="50" y="200" font-size="150px">%s</text>' % add_text)
        f.write(HEADER2)
        for n, stroke in enumerate(strokes):
            if n < skip_strokes or n >= stop_at:
                continue
            # IMHO this can safely be hardcoded because it's relative to this
            # image
            line_size = (20 if n - 1 < img_num else 10)
            f.write(PATH_TPL % (stroke, line_size))
        f.write(FOOTER)
    image_cache.append(fname)
    return fname


def load_dictionary():
    d = {}
    with open('dictionary.txt', 'r') as f:
        for line in f:
            j = json.loads(line)
            if j['pinyin']:
                d[j['character']] = j['pinyin'][0]
    d['X'] = ''
    return d


def gen_image_cache(input_characters, strokes_db, image_cache, P, num_repeats):
    while True:
        for C in input_characters:
            strokes = strokes_db[C]
            num_strokes = len(strokes)
            for i in range(num_strokes):
                for _ in range(num_repeats):
                    yield get_image(C, i, image_cache, strokes, 0, i+1, P[C])
                for _ in range(num_repeats):
                    yield get_image(C, 0, image_cache, strokes, i + 1, 99, P[C])
        for i in range(10):
            C = random.choice(input_characters)
            yield get_image(C, 0, image_cache, [], 99, 99, P[C])


def gen_svg(f, input_characters, strokes_db, size, num_repeats):
    P = load_dictionary()
    num_per_row = PAGE_SIZE[0] // size
    num_rows = PAGE_SIZE[1] // size
    f.write(HEADER_SINGLE)
    header = ', '.join('%s (%s)' % (c, P[c]) for c in input_characters)
    f.write('<text x="0" y="7" font-size="5px">%s</text>' % header)
    image_cache = []
    gen_image_cache_iter = iter(gen_image_cache(input_characters, strokes_db, image_cache, P, num_repeats))
    for i in range(num_per_row * (num_rows - 1)):
        fname = next(gen_image_cache_iter)
        x = (i % num_per_row) * size
        y = ((i // num_per_row) + 1) * size
        f.write(IMAGE_TPL % (x, y, size, size, fname))
    f.write(FOOTER_SINGLE)
    return image_cache


async def start_browser():
    # this lets us work without CAP_SYS_ADMIN:
    options = {'args': ['--no-sandbox']}
    # HACK: we're disabling signals because they fail in system tests
    if threading.currentThread() != threading._main_thread:
        options.update({'handleSIGINT': False, 'handleSIGHUP': False,
                        'handleSIGTERM': False})
    return await launch(**options)


async def gen_pdf(browser, infile, outfile):
    page = await browser.newPage()
    await page.goto('file://%s' % infile)
    await page.pdf({'path': outfile})


class DrawStrokes:

    def __init__(self, graphics_txt_path):
        self.strokes_db = load_strokes_db(graphics_txt_path)

    async def draw(self, input_characters, size, num_repeats, out_path=None,
                   no_delete=False, no_pdf=False):

        LOGGER.info('Generating SVG...')

        image_cache = []

        base_path = os.getcwd() + '/' + input_characters
        svg_path = base_path + '.svg'
        with open(svg_path, 'w') as f:
            image_cache = gen_svg(f, input_characters, self.strokes_db, size, num_repeats)

        if no_pdf:
            return

        pdf_path = out_path or base_path + '.pdf'
        LOGGER.error('Generating %s...' % pdf_path)
        browser = await start_browser()
        await gen_pdf(browser, svg_path, pdf_path)

        if no_delete:
            return pdf_path

        for fname in set(image_cache):
            os.unlink(fname)

        os.unlink(svg_path)

        return pdf_path
