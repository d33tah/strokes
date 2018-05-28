import json
import os
import threading
import random
import logging
import uuid
import subprocess


from pyppeteer import launch


PAGE_SIZE = (200, 300)
LOGGER = logging.getLogger(__name__)
TMPDIR = 'imagecache/'


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


class ImageGenerator:

    def __init__(self, image_cache, P):
        self.image_cache = image_cache
        self.P = P

    def get_image(self, C, strokes, img_num, skip_strokes, stop_at):

        fname = TMPDIR + C + '%d-%d-%d.svg' % (img_num, skip_strokes, stop_at)
        fname = os.path.abspath(fname)
        if fname in self.image_cache:
            return fname

        add_text = self.P[C]

        with open(fname, 'w', encoding='utf8') as f:
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
        self.image_cache.append(fname)
        return fname


def gen_images(input_characters, image_generator, strokes_db, num_repeats):
    for C in input_characters:
        strokes = strokes_db[C]
        num_strokes = len(strokes)
        for i in range(num_strokes):
            for _ in range(num_repeats):
                yield image_generator.get_image(C, strokes, i, 0, i+1)
            for _ in range(num_repeats):
                yield image_generator.get_image(C, strokes, 0, i + 1, 99)
    for i in range(10):
        C = random.choice(input_characters)
        yield image_generator.get_image(C, [], 0, 0, 0)


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
            f.write('<text x="0" y="7" font-size="5px">%s</text>' % header)
            for i in range(num_per_row * (num_rows - 1)):
                try:
                    fname = next(gen_images_iter)
                except StopIteration:
                    keep_going = False
                    break
                x = (i % num_per_row) * size
                y = ((i // num_per_row) + 1) * size
                if ((i // num_per_row) + 3) > num_rows:
                    break
                f.write(IMAGE_TPL % (x, y, size, size, fname))
            f.write(FOOTER_SINGLE)
    return fpaths


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


def join_pdfs(pdfs, outpath=None):
    outpath = outpath or os.path.join(TMPDIR, str(uuid.uuid4()) + '.pdf')
    subprocess.check_call(['pdfjoin', '--outfile', outpath] + pdfs)
    return outpath


class DrawStrokes:

    def __init__(self, graphics_txt_path, dictionary_txt_path):
        self.strokes_db = load_strokes_db(graphics_txt_path)
        self.P = load_dictionary(dictionary_txt_path)
        self.image_cache = []
        self.image_generator = ImageGenerator(self.image_cache, self.P)

    async def draw(self, input_characters, size, num_repeats, out_path):

        LOGGER.info('Generating SVG...')

        gen_images_iter = iter(gen_images(input_characters,
                                          self.image_generator,
                                          self.strokes_db, num_repeats))

        header = ', '.join('%s (%s)' % (c, self.P[c])
                           for c in input_characters)

        base_path = os.getcwd() + '/' + input_characters
        svg_paths = gen_svg(size, header, gen_images_iter)

        LOGGER.error('Generating pdfs...')
        browser = await start_browser()
        pdf_paths = []
        for n, svg_path in enumerate(svg_paths):
            pdf_path = base_path + str(n) + '.pdf'
            pdf_paths.append(pdf_path)
            await gen_pdf(browser, svg_path, pdf_path)
            os.unlink(svg_path)

        out_pdf_path = join_pdfs(pdf_paths, out_path)
        await browser.close()


        return out_pdf_path
