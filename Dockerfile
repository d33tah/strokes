FROM alpine:latest as base

RUN apk update && apk add python3

RUN wget -nv https://github.com/skishore/makemeahanzi/blob/master/graphics.txt?raw=true -O/tmp/graphics.txt
RUN wget -nv https://github.com/skishore/makemeahanzi/blob/master/dictionary.txt?raw=true -O/tmp/dictionary.txt

ADD ./requirements.txt /tmp
RUN pip3 install -r /tmp/requirements.txt && rm /tmp/requirements.txt
ADD ./strokes.py /tmp/
ADD ./wiktionary-data.json /tmp/
ADD ./alt_forms.json /tmp/
ADD ./all_definitions.json /tmp/

FROM base as test
ADD ./requirements-dev.txt /tmp
RUN coverage run --branch -m nose strokes.py
RUN coverage report

FROM base
RUN chmod +x /tmp/strokes.py

WORKDIR /tmp
RUN mkdir /tmp/imagecache
CMD FLASK_APP=/tmp/strokes.py flask run -h 0.0.0.0
