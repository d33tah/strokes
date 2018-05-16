FROM ubuntu:18.04

###########################################################################
#
# pyppeteer + Chrome installation
#
###########################################################################

RUN apt-get update && apt-get install -y python3-pip graphviz

RUN pip3 install pyppeteer

RUN apt update && apt install -y libasound2 libatk-bridge2.0-0 libatk1.0-0 \
    libc6 libcairo2 libcups2 libdbus-1-3 libexpat1 libgcc1 libgdk-pixbuf2.0-0 \
    libglib2.0-0 libgtk-3-0 libnspr4 libnss3 libpango-1.0-0 \
    libpangocairo-1.0-0 libx11-6 libx11-xcb1 libxcb1 libxcomposite1 \
    libxcursor1 libxdamage1 libxext6 libxfixes3 libxi6 libxrandr2 \
    libxrender1 libxss1 libxtst6 bash xdg-utils

RUN groupadd chrome && useradd -g chrome -s /bin/bash -G audio,video chrome \
    && mkdir -p /home/chrome && chown -R chrome:chrome /home/chrome

RUN apt-get update && apt-get install -y fonts-noto-cjk locales wget

USER chrome
RUN python3 -c '__import__("pyppeteer.chromium_downloader").chromium_downloader.download_chromium()'
USER root

###########################################################################
#
# End of pyppeteer + Chrome installation
#
###########################################################################

# we need to be able to read argv in UTF8 - in order to do that, we need
# utf8 locale
RUN locale-gen en_US.UTF-8
ENV LC_ALL=en_US.UTF-8

RUN wget -nv https://github.com/skishore/makemeahanzi/blob/master/graphics.txt?raw=true -O/tmp/graphics.txt
RUN wget -nv https://github.com/skishore/makemeahanzi/blob/master/dictionary.txt?raw=true -O/tmp/dictionary.txt

ADD ./requirements.txt /tmp
RUN pip3 install -r /tmp/requirements.txt && rm /tmp/requirements.txt
ADD ./strokes.py /tmp/
ADD ./strokes_backend.py /tmp/
ADD ./strokes_composition.py /tmp/
ADD ./wiktionary-data.json /tmp/
RUN chmod +x /tmp/strokes.py

USER chrome
WORKDIR /tmp
RUN nosetests strokes.py
CMD FLASK_APP=/tmp/strokes.py flask run -h 0.0.0.0
