FROM openzim/zimwriterfs:latest

# Install necessary packages
RUN apt-get update -y
RUN apt-get install -y python-pip
RUN apt-get install -y ffmpeg

# Install sotoki
RUN locale-gen "en_US.UTF-8"
RUN pip install ted2zim

# Boot commands
CMD ted2zim -h ; /bin/bash
