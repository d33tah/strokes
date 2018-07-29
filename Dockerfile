FROM alpine/git
ADD ./.git/ /git
RUN git -C /git rev-parse HEAD > /tmp/commit-id

FROM alpine:latest as base

RUN apk update && apk add python3

WORKDIR /tmp

RUN wget -nv https://github.com/skishore/makemeahanzi/blob/master/graphics.txt?raw=true -Ographics.txt
RUN wget -nv https://github.com/skishore/makemeahanzi/blob/master/dictionary.txt?raw=true -Odictionary.txt

ADD ./requirements.txt .
RUN pip3 install -r requirements.txt

# I could put it in a separate stage, but I couldn't get it to work w/caching.
ADD ./requirements-dev.txt .
RUN pip3 install -r requirements-dev.txt

ADD ./strokes.py .
ADD ./wiktionary-data.json .

RUN chmod +x strokes.py
CMD FLASK_APP=strokes.py flask run -h 0.0.0.0

RUN flake8 strokes.py
RUN coverage run --source=. --branch -m nose strokes.py
RUN coverage report

COPY --from=0 /tmp/commit-id commit-id

EXPOSE 5000
