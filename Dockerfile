FROM python:3.12-slim-bookworm
LABEL org.opencontainers.image.source https://github.com/openzim/ted

# Install necessary packages
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      locales-all wget unzip ffmpeg curl libmagic1 \
 && rm -rf /var/lib/apt/lists/* \
 && python -m pip install --no-cache-dir -U \
      pip

# Custom entrypoint
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
ENTRYPOINT ["entrypoint.sh"]

# Copy pyproject.toml and its dependencies
COPY pyproject.toml openzim.toml README.md /src/
COPY src/ted2zim/__about__.py /src/src/ted2zim/__about__.py

# Install Python dependencies
RUN pip install --no-cache-dir /src

# Copy code + associated artifacts
COPY src /src/src
COPY *.md /src/

# Install + remove argparse + cleanup
# argparse is a pif dependency but it is an old version ; we do not need it in recent
# Python versions (it even break ted2zim-multi since allow_abbrev is not supported)
RUN pip install --no-cache-dir /src  \
 && pip uninstall -y argparse \
 && rm -rf /src

RUN mkdir -p /output
WORKDIR /output
CMD ["ted2zim", "--help"]
