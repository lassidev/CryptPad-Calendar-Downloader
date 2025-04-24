# Use the official Ubuntu image as a base image
FROM ubuntu:latest

# Install python and chrome
RUN apt update -y
RUN apt install wget python3 python3-pip -y

RUN wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
RUN apt-get install -y ./google-chrome-stable_current_amd64.deb

# Install required packages
ENV PIP_BREAK_SYSTEM_PACKAGES 1
RUN pip3 install selenium
RUN pip3 install webdriver-manager
RUN pip3 install icalendar
