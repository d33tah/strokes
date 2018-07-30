Strokes v1.0
============

Strokes is a project meant to help you learn Chinese characters.

Currently it allows you to create a printable worksheet that will teach you
stroke order and Pinyin pronounciation of any of over 9000 supported
characters. Here's an example of what happens when you enter 一二三四 on
[the test page](https://strokes.ovh):

![Strokes - example output](docs/example_defaults_yi_to_si.png?raw=true)

To try it out, visit [strokes.ovh](https://strokes.ovh). Be gentle for the
website - it's running on a $5 webserver - if it crashes, please let me know ;)

Once you click "Generate PDF", you are expected to print out the PDF generated
by the project and fill in the blank space within the strokes marked in bold.

As you can see, each stroke is drawn four times: 1) alone, 2) with all strokes
introduced so far, 3) in context and 4) in context but with no aid, so that
you can practice the proportions on your own. At the end of each pair you are
supposed to rehearse by drawing complete characters, which should help you
memorize strokes for all characters introduced so far. The way it is set up
by default, you should actually not only train your short-term memory, but also
long-term, making you remember characters longer!

All HSK 1-6 characters all supported.

Usage
=====

Test page
---------

If you just want to try Strokes out, visit [strokes.ovh](https://strokes.ovh).
Be gentle for the website - it's running on a $5 webserver - if it crashes,
please let me know ;)

Generating the PDF
------------------

After visiting the project's URL, you should see a form with a few text
boxes, as well as buttons. To just use default settings, remove the current
contents of "Characters" box and enter any characters you want to learn.
Keep in mind that all whitespace characters (including just "space") will be
removed and all non-Chinese characters will cause an error.

Once you're done,
click "Generate PDF" and wait a while. It takes the program about two seconds
per page in order to prepare a printable file. If you don't want to be waiting
just to get the same file, press Ctrl+S and save it somewhere.

I suggest you just print first few pages if you're trying Strokes out - you
might want to fiddle with the following options:

* **Size** - decrease this if you want resulting document to be zoomed out or
increase if you want more room for your strokes. This really depends on your
drawing tool - I just an extra-fine Pilot Plumix fountain pen and size of 15
is optimal for me while practicing for HSK2,

* **Number of repetitions** - you might have different goals and preferred
styles when using Strokes. The default "1" means that you'll only do each phase
of learning once per stroke. If you increase it to 2, each phase will be
repeated, resulting in more practice. You might find it useful when practicing
one of the more difficult characters. If you set it to 0, you'll only see
"next stroke with context" phase used - this is what I'd use if I was to
quickly get familiar with lots of characters but didn't really care about
getting enough practice.

* **Sorting** - this lets you rearrange characters you entered in "Characters"
box. Right now there are two options - "None" which won't change the ordering
and "Pinyin" which will reorder them, sorting them by pronounciation. You can
also remove duplicates, which will mean that each character will only appear
once in the set (don't worry, it will still be repeated - just not more than
other characters).

* **Preview** - if you only want to get a preview of what the program will
generate, use this button. It will be faster and you will quickly get an idea
of whether you want to change anything. Keep in mind that this is not meant
for printing and sizing might be wrong (but number of pages won't).

If you're preparing for HSK, you can just copy a .txt list as program's
input and jump straight to learning. Example file you can just copy into the
"Characters" field is this one:

http://data.hskhsk.com/lists/HSK%20Official%202012%20L1.txt

(Change the L1 at the end of the document to L2 or L-some-other-number if
you're practicing for HSK2 or higher.)

Tricks and tips
---------------

Give the program a chance even if you find the number of pages it generated
overwhelming. They are conveniently split into regions, letting you stop
your practice session quite often.

Experiment. Not only with options, but also with your writing tools. Find some
way to make learning pleasant. If this means you need a more expensive pen, do
it. The program's for free, you're not paying for any teacher, you might as
well consider it an investment.

When choosing the value of "Size" option, keep in mind that things might get
cluttered once you start entering complex characters. That's why I introduced
first ("just this stroke") phase of writing a stroke - so that you will notice
that you're drawing a new one already. It's easy to drift off while practicing
and this phase is meant to help you go out of the rhythm so you can concentrate
again.

Consider using ink color other than black. So far I tried Pelikan's "brilliant
red" and it wasn't up to my expectations and right now I'm using their green.
Using anything other than black will mean you will see when you draw outside
of the borders.

Installation, self-hosting
--------------------------

Unfortunately, the project is not trivial to run on your own computer for
non-programmers. You will need to learn how to run Docker applications in order
to start it.

Assuming that your system already has both docker and docker-compose installed,
starting should be as easy as running `docker-compose up` as `root` (e.g. by
adding `sudo ` at the beginning of the command). After a few moments, you
should see the following text in your terminal:

`server_1    |  * Running on http://0.0.0.0:5000/ (Press CTRL+C to quit)`

Assuming that this happened, Strokes should be available using your browser.
Just visit the following URL: http://localhost:5000/

TO-DO list
==========

In other words, "what's not there and would fit the project's mission"?

First - user experience. I hacked up the form one can see on the index page
on the quick - it wasn't meant to be pretty. This doesn't mean I don't want it
to be - it just means that I didn't have time and energy to get there. Also,
it would be nice if the program reported which page it's currently rendering -
if you're supposed to wait a minute, you might as well get some progress
update. Pull Requests fixing this are definitely welcome for all things listed
in this section!

Other thing that's on my list is print setup customization - at the very least,
being able to set page size would be of help to folks living in the US where A4
is not as popular page format. To be honest, I have no idea how the thing would
work there right now. Being able to set margins would also be nice.

Speaking of customization, when you print enough of those you'll definitely
want to be able to add a custom header. It's not there yet. Headers can also
overflow, especially in "zero repeats" mode. Not sure what the solution should
be.

One should also be able to customize the learning experience mode. My current -
 possibly not best from UX perspective - solution that I have in mind is to
add "advanced" mode where user would be able to set number of repeats for each
phase and also maybe set how many strokes at once they want to learn - once
you know the patterns, I guess you can tell more or less which strokes stroke
goes after which, but rather need a general tip.

There's also some testing work - including automated testing. Right now I have
some system tests that are good at catching crashes and inflating test
coverage, but don't actually verify if output is OK. Making HTML output
validate would also be nice. And some selenium testing. This all could use some
love.

Why?
====

Because I don't like the general idea of "repeat it 1000 times to learn".

I don't really know much about the way human learns, but when I was exposed to
my regular Chinese practice books, I found them so boring I just decided I
wouldn't exercise at all. And starting from that point, as I realized I'm quite
a bit behind compared to other students, I started looking for effective ways
to learn.

I had a couple of goals in mind: first of all, the tool itself cannot be
boring. First iterations of Strokes only made me repeat all strokes for a given
character, but I found that A) I'm not really concentrating this way and B)
that even after repeating the strokes many times, I still can't write them from
memory and I'm getting proportions wrong. This is when I decided to introduce
"stroke with no aid" ("4") tiles and when I realized I'm still doing the thing
quite mechanically, I also added "just this stroke alone" ("1") tiles that are
supposed to confuse you for a bit so you re-focus on your task.

Most of the application is built around the way I imagine learning works - at
one point I realized that I'm not really remembering strokes for characters I
write and I decided to also add "random rehearsing" with only pinyin hints at
what is expected. Then, "backtracking" was added, where if you learn characters
ABCDEFGH, you'll first learn and rehearse A and B, then C and D, then A, B, C
and D, then - separately - E and F, as well as G and H and after that, E, F, G
and H. So we're learning in pairs, groups of four and once there are two groups
of four, they're ultimately merged in "ABCDEFGH" step when you rehearse
everything so far. This repeats even for large sets, so every few characters
you will get a chance to repeat everything that was already introduced.

I based this on the assumption that short-term and long-term memory need to be
trained separately - for short-term memory there's just the practice of
strokes, but in order to remember them after the few minutes, user is asked to
recall them, which - if done actively (instead of just cheating and looking at
the previous answers right away) - is done in the "rehearsing" step.

My ultimate goal is to make the tool as effective as possible, so even if you
don't have time to repeat hundreds of characters thousands times each, you
still can get a bit with the aid of this application. One of the ideas I hadn't
explored yet is to also practice fixed phrases, so that a single sentence would
for example be a whole group. I might fiddle with this in the future.

By the way, if you have an idea of how to improve this piece, let me know! As
I said, I have no cognitive sciences background so I might miss some seemingly
trivial changes that would make this project better. Just imagine all the
man-hours spent learning Chinese characters that we could just spare!

How does it work?
=================

Glad you asked! Most of the credit really should go Skishore for putting
together graphics.txt file, which contains SVG data for each stroke of
supported characters, with order retained. He then used it in
[his Inkstone Android
program](https://play.google.com/store/apps/details?id=com.id126c0rsxlvjwv18cf44u&hl=en)
(definitely worth its Google Play price!) which I found really cool, but not
perfect when learning chinese characters for the first time - at least not for
me. Instead of hacking Inkstone, I decided to write a Flask application that
reads graphics.txt and generates tiles with specific strokes hidden and others
highlighted.

The only problem was how to render SVG into a format that guarantees that
proportions are kept. I didn't either trust or want to learn how to interact
with reliable HTML printing, so I worked on SVG to PDF rendering solution.

I think I first experimented with Inkscape, but the output PDFs were too large.
I then went with Google Chrome in headless mode, which is what drives the
connected Docker container, d33tah/html2pdf. You can find its code here:

https://github.com/d33tah/html2pdf

Because of its size, I decided to put it in a separate container so this one
only contains programs related to running Flask apps.

Please file a Github issue if you want any more specific information here.

Bugs, problems
==============

I can't figure out why it's impossible to zoom in the SVG files generated by
my program, at least not in Firefox. Help would be welcome!

Author, license, acknowledgements
=================================

This application was written by Jacek Wielemborek <d33tah@gmail.com>. My blog
can be found here: http://d33tah.wordpress.com

If you're not a viagra vendor, feel free to write me an e-mail or file
a Github issue with feedback, I'll be more than happy to hear that you use
this program! I might even improve it for you if your needs align with my
vision of the project :)

This program is Free Software and is protected by GNU General Public License
version 3. Basically, it gives you four freedoms:

Freedom 0: The freedom to run the program for any purpose.

Freedom 1: The freedom to study how the program works, and change it to make
    it do what you wish.

Freedom 2: The freedom to redistribute copies so you can help your neighbor.

Freedom 3: The freedom to improve the program, and release your improvements
    (and modified versions in general) to the public, so that the whole
     community benefits.

In order to protect that freedom, you must share any changes you did to the
program with me, under the same license. For details, read the COPYING.txt
file attached to the program.

This application uses data from open-source Inkstone application by Skishore,
namely "graphics.txt" and "dictionary.txt" files. For licensing information,
consult the following repositories:

https://github.com/skishore/inkstone

https://github.com/skishore/makemeahanzi
