FROM python:3.6-slim

RUN apt-get update
RUN apt-get install -y --no-install-recommends git
RUN apt-get purge -y --auto-remove
RUN rm -rf /var/lib/apt/lists/*

WORKDIR /usr/local
RUN git clone https://github.com/visionspacetec/sle-common.git
WORKDIR /usr/local/sle-common
RUN pip install -e .

WORKDIR /usr/local/sle-provider
COPY . .
RUN pip install -e .

COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod 777 /usr/local/bin/docker-entrypoint.sh

EXPOSE 2048
EXPOSE 16887
EXPOSE 16888
EXPOSE 55529

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]