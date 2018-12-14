FROM alpine/git
ADD ./.git/ /git
RUN git -C /git rev-parse HEAD > /tmp/commit-id

FROM alpine:latest as base

ENV HTML2PDF_URL=http://html2pdf:5000

RUN apk update && apk add python3

RUN adduser -D strokes && mkdir -p /home/strokes && chown -R strokes /home/strokes

WORKDIR /tmp

ADD ./requirements.txt .
RUN pip3 install -r requirements.txt

# I could put it in a separate stage, but I couldn't get it to work w/caching.
ADD ./requirements-dev.txt .
RUN pip3 install -r requirements-dev.txt

USER strokes
WORKDIR /home/strokes

RUN wget -nv https://github.com/skishore/makemeahanzi/blob/master/graphics.txt?raw=true -Ographics.txt
RUN wget -nv https://github.com/skishore/makemeahanzi/blob/master/dictionary.txt?raw=true -Odictionary.txt

ADD ./strokes.py .
ADD ./wiktionary-data.json .

CMD FLASK_APP=strokes.py flask run -h 0.0.0.0

RUN flake8 strokes.py
RUN coverage run --source=. --branch -m nose strokes.py
RUN coverage xml && grep '<coverage branch-rate="0.9' coverage.xml

COPY --from=0 /tmp/commit-id commit-id

EXPOSE 5000
