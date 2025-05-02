# CryptPad-Calendar-Downloader

Input a list of CryptPad calendar URLs and get a singular iCalendar file.

TODO better instructions

``` bash
# INIT
git clone https://github.com/lassidev/CryptPad-Calendar-Downloader
cd CryptPad-Calendar-Downloader
docker build -t ubuntu-cryptpad-downloader:latest .

# CHANGE SETTINGS AS NEEDED
vim docker-compose.yml
vim app/config.json

# RUN
docker compose up -d

# SEE LOGS
docker logs ubuntu-cryptpad-downloader-prod --follow
```


