"""
Code that generates compositions. TODO: clean up.
"""

import json
import unicodedata


def try_uniname(x):
    try:
        return unicodedata.name(x)
    except ValueError:
        return ''


def is_radical(d, x):
    return int(d.get(x, {}).get('as', -1)) == 0


def fillcolor(d, x):
    if is_radical(d, x):
        return 'color=black, penwidth=2'
    else:
        return 'color=black'


def get_first(back, x):
    while x in back:
        x = back[x]
    return x


def D(char):
    # TODO: add definitions here.
    return char


def write_dot_to_file(f, chars,
                      wiktionary_parsed_filename='wiktionary-data.json'):

    with open(wiktionary_parsed_filename) as wiktionary_parsed_file:
        d = json.loads(wiktionary_parsed_file.read())

    s = list(chars)
    back = {}
    f.write('strict graph { rankdir=LR; ')
    while s:
        to_decompose = s.pop(0)
        if not try_uniname(to_decompose).startswith('CJK '):
            continue

        f.write('"%s" [URL="http://en.wiktionary.org/wiki/%s", %s];'
                % (D(to_decompose), to_decompose, fillcolor(d, to_decompose)))

        for char in d.get(to_decompose, {}).get('ids', ''):
            back[char] = to_decompose
            if not try_uniname(char).startswith('CJK '):
                continue
            first = get_first(back, to_decompose)

            f.write('"%s" [URL="http://en.wiktionary.org/wiki/%s", %s];'
                    % (D(char), char, fillcolor(d, char)))

            same_radical = d[first]['rad'] == d.get(char, {}).get('rad')
            definitions = D(to_decompose), D(char)
            if same_radical and is_radical(d, char):
                f.write('"%s" -- "%s" [penwidth=2];' % definitions)
            else:
                f.write('"%s" -- "%s" [penwidth=1];' % definitions)
            s.append(char)
    f.write('}')
