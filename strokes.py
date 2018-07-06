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

import asyncio
import subprocess
import io

from quart import Quart, Response, request
from strokes_drawing import draw
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


@app.route('/gen_strokes', methods=['POST'])
async def gen_strokes():
    form = await request.form
    size = int(form.get('size') or 10)
    num_repetitions = int(form.get('nr') or 3)
    C = form.get('chars') or 'X'
    out_path = await draw('graphics.txt', 'dictionary.txt', C, size,
                          num_repetitions)
    with open(out_path, 'rb') as f:
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
        <p>Number of repetitions: <input type="text" name="nr" value="3"/></p>
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
