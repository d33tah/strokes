FROM ubuntu:18.04

RUN apt-get update && apt-get install -y fonts-noto-cjk locales wget python3-pip
RUN useradd strokes

# we need to be able to read argv in UTF8 - in order to do that, we need
# utf8 locale
RUN apt-get update && apt-get install -y locales && locale-gen en_US.UTF-8
ENV LC_ALL=en_US.UTF-8

RUN wget -nv https://github.com/skishore/makemeahanzi/blob/master/graphics.txt?raw=true -O/tmp/graphics.txt
RUN wget -nv https://github.com/skishore/makemeahanzi/blob/master/dictionary.txt?raw=true -O/tmp/dictionary.txt

ADD ./requirements.txt /tmp
RUN pip3 install -r /tmp/requirements.txt && rm /tmp/requirements.txt
ADD ./strokes.py /tmp/
ADD ./strokes_drawing.py /tmp/
ADD ./strokes_composition.py /tmp/
ADD ./wiktionary-data.json /tmp/
ADD ./alt_forms.json /tmp/
ADD ./all_definitions.json /tmp/
RUN chmod +x /tmp/strokes.py

USER strokes
WORKDIR /tmp
RUN mkdir /tmp/imagecache
CMD QUART_APP=/tmp/strokes.py quart run -h 0.0.0.0
