FROM alpine/git
ADD ./.git/ /git
RUN git -C /git rev-parse HEAD > /tmp/commit-id

FROM d33tah/html2pdf as base

USER root

RUN apt-get update && apt-get install -y wget supervisor

USER chrome

WORKDIR /tmp

ADD ./requirements.txt .
RUN pip3 install -r requirements.txt

RUN wget -nv https://github.com/skishore/makemeahanzi/blob/master/graphics.txt?raw=true -Ographics.txt
RUN wget -nv https://github.com/skishore/makemeahanzi/blob/master/dictionary.txt?raw=true -Odictionary.txt

ADD ./strokes.py .
ADD ./wiktionary-data.json .

CMD FLASK_APP=strokes.py python3 -m flask run -h 0.0.0.0

ADD ./supervisord-single.conf /etc/supervisor/conf.d/supervisord.conf
COPY --from=0 /tmp/commit-id commit-id

USER root
ENTRYPOINT supervisord -n

EXPOSE 5000
