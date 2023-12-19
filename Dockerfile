FROM python:3.11-slim-bookworm
LABEL org.opencontainers.image.source https://github.com/openzim/ted

# Install necessary packages
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      locales-all wget unzip ffmpeg curl libmagic1 \
 && rm -rf /var/lib/apt/lists/* \
 && python -m pip install --no-cache-dir -U \
      pip

# Copy pyproject.toml and its dependencies
COPY pyproject.toml README.md hatch_build.py get_js_deps.sh /src/
COPY src/ted2zim/__about__.py /src/src/ted2zim/__about__.py

# Install Python dependencies
RUN pip install --no-cache-dir /src

# Copy code + associated artifacts
COPY src /src/src
COPY *.md /src/

# Install + cleanup
RUN pip install --no-cache-dir /src \
 && rm -rf /src

RUN mkdir -p /output
WORKDIR /output
CMD ["ted2zim", "--help"]
