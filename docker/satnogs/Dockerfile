FROM python:3.7-slim

RUN apt-get clean all
RUN apt-get update
RUN apt-get autoremove
RUN apt-get install -y --no-install-recommends git
RUN apt-get purge -y --auto-remove
RUN rm -rf /var/lib/apt/lists/*

ENV TZ=Etc/UTC
RUN ln -snf /usr/share/zoneinfor/$TZ /etc/localtime && echo $TZ > /etc/timezone

WORKDIR /usr/local
RUN git clone https://github.com/visionspacetec/sle-common.git
WORKDIR /usr/local/sle-common
RUN pip install -e .

WORKDIR /usr/local/sle-provider
COPY . .
RUN pip install -e .

COPY docker/satnogs/docker-entrypoint.sh /usr/local/bin/
RUN chmod 777 /usr/local/bin/docker-entrypoint.sh

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
