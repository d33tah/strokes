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
    * multi-page support
    * repetition mode: show two strokes at once?
    * make frontend cuter
    * custom titles
    * move all initialization outside of the hot loop

------------------------------------------------------------------------------
'''

import argparse
import logging
import asyncio
import subprocess
import io

from quart import Quart, Response, request
from strokes_backend import main
from strokes_composition import write_dot_to_file

# those imports are for testing purposes:
import unittest
import multiprocessing
import time
import hashlib
import requests

app = Quart(__name__)


def random_string():
    return hashlib.md5(str(time.time()).encode('utf8')).hexdigest()


SHUTDOWN_CODE = random_string()


def parse_argv():
    parser = argparse.ArgumentParser(
            description=__doc__,
            formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('character', nargs=1)

    parser.add_argument('--size', default=13)

    parser.add_argument('--graphics-txt-path', default='graphics.txt',
                        help='path to skisore\'s makemeahanzi/graphics.txt'
                        ' file')

    parser.add_argument('--no-delete', action='store_true', default=False,
                        help='don\'t delete temporary files')

    parser.add_argument('--no-pdf', action='store_true', default=False,
                        help='stop after creating the SVG file'
                        ' (implies --no-delete)')

    return parser.parse_args()


@app.route('/gen_strokes', methods=['POST'])
async def gen_strokes():
    form = await request.form
    logger = logging.getLogger('strokes')
    size = int(form.get('size') or 10)
    size = int(form.get('nr') or 3)
    C = form.get('chars') or 'X'
    await main(
        logger, C, size, False, False, 'graphics.txt'
    )
    with open(C + '.pdf', 'rb') as f:
        return Response(f.read(), mimetype='application/pdf')


@app.route('/gen_composition', methods=['POST'])
async def gen_composition():
    form = await request.form
    x = form.get('chars')
    f = io.StringIO()
    write_dot_to_file(f, x)
    s2 = subprocess.Popen(['dot', '-Tsvg'], stdout=subprocess.PIPE,
                          stdin=subprocess.PIPE)
    ret = s2.communicate(f.getvalue().encode('utf8'))
    return Response(ret, mimetype='image/svg+xml')


# this is for testing purposes only - we need a way to turn off the server
# once tests are done
@app.route('/' + SHUTDOWN_CODE, methods=['POST', 'GET'])
def shutdown():
    asyncio.get_event_loop().stop()
    return 'Server shutting down...'


@app.route('/')
def index():
    return '''<!DOCTYPE HTML><html><body>
        <form action="/gen_composition" method="post">
        <p>Characters: <input type="text" name="chars" value="齾"/></p>
        <input type="submit" value="Generate composition">
        </form>

        <form action="/gen_strokes" method="post">
        <p>Characters: <input type="text" name="chars" value="你好"/></p>
        <p>Size: <input type="text" name="size" value="10"/></p>
        <p>Number of repetitions: <input type="text" name="nr" value="10"/></p>
        <input type="submit" value="Generate strokes">
    </form>
    '''


class SystemTest(unittest.TestCase):

    def setUp(self):
        self.server_thread = multiprocessing.Process(target=lambda: app.run())
        self.server_thread.start()
        time.sleep(1.0)

    def tearDown(self):
        requests.post(self.get_server_url() + '/' + SHUTDOWN_CODE, {})
        self.server_thread.terminate()
        self.server_thread.join()

    def get_server_url(self):
        return 'http://localhost:5000'

    def test_server_is_up_and_running(self):
        response = requests.get(self.get_server_url())
        self.assertEqual(response.status_code, 200)

    def test_gen_strokes_nihao_200(self):
        response = requests.post(self.get_server_url() + '/gen_strokes',
                                 {'chars': '你好', 'size': '10'})
        self.assertEqual(response.status_code, 200)

    def test_gen_composition_nihao_200(self):
        response = requests.post(self.get_server_url() + '/gen_composition',
                                 {'chars': '你好', 'size': '10'})
        self.assertEqual(response.status_code, 200)


if __name__ == '__main__':

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger('strokes')
    args = parse_argv()
    asyncio.get_event_loop().run_until_complete(main(
        logger, args.character[0], args.size, args.no_delete, args.no_pdf,
        args.graphics_txt_path
    ))
    logger.info('Program done. goodbye!')
