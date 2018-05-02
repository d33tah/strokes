import json
import os
import threading
import random

from pyppeteer import launch


PAGE_SIZE = (200, 300)


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


def get_image(C, img_num, images, strokes, skip_strokes, stop_at, add_text=''):
    fname = C + '%d-%d-%d.svg' % (img_num, skip_strokes, stop_at)
    if fname in images:
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
        images.append(fname)
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


def gen_images(chars, strokes_db, images, P):
    while True:
        for C in chars:
            strokes = strokes_db[C]
            num_strokes = len(strokes)
            for i in range(num_strokes):
                for _ in range(3):
                    yield get_image(C, i, images, strokes, 0, i+1, P[C])
                for _ in range(3):
                    yield get_image(C, 0, images, strokes, i + 1, 99, P[C])
        for i in range(10):
            C = random.choice(chars)
            yield get_image(C, 0, images, [], 99, 99, P[C])


def gen_svg(C, strokes_db, size, fi):
    P = load_dictionary()
    num_per_row = PAGE_SIZE[0] // size
    num_rows = PAGE_SIZE[1] // size
    fi.write(HEADER_SINGLE)
    chars = C
    header = ', '.join('%s (%s)' % (c, P[c]) for c in chars)
    fi.write('<text x="0" y="7" font-size="5px">%s</text>' % header)
    images = []
    gen_images_iter = iter(gen_images(chars, strokes_db, images, P))
    for i in range(num_per_row * (num_rows - 1)):
        fname = next(gen_images_iter)
        x = (i % num_per_row) * size
        y = ((i // num_per_row) + 1) * size
        fi.write(IMAGE_TPL % (x, y, size, size, fname))
    fi.write(FOOTER_SINGLE)
    return images


async def gen_pdf(infile, outfile):
    # this lets us work without CAP_SYS_ADMIN:
    options = {'args': ['--no-sandbox']}
    # HACK: we're disabling signals because they fail in system tests
    if threading.currentThread() != threading._main_thread:
        options.update({'handleSIGINT': False, 'handleSIGHUP': False,
                        'handleSIGTERM': False})
    browser = await launch(**options)
    page = await browser.newPage()
    await page.goto('file://%s' % infile)
    await page.pdf({'path': outfile})
    await browser.close()


async def main(logger, C, size, no_delete, no_pdf, graphics_txt_path):

    logger.info('Loading strokes_db...')
    strokes_db = load_strokes_db(graphics_txt_path)

    logger.info('Generating SVG...')
    svg_path = C + '.svg'
    with open(svg_path, 'w') as fi:
        images = gen_svg(C, strokes_db, size, fi)

    if no_pdf:
        return

    base_path = os.getcwd() + '/' + C
    await gen_pdf(base_path + '.svg', base_path + '.pdf')

    if no_delete:
        return

    for fname in set(images):
        os.unlink(fname)

    os.unlink(svg_path)
