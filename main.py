from selenium import webdriver
from selenium.webdriver.common.by import By
from icalendar import Calendar, Event
from datetime import datetime
import time
import argparse
import os
import sys
import json

# arguments
parser = argparse.ArgumentParser()
parser.add_argument("configjson", help="Location of the config file")
args = parser.parse_args()

# Set variables from config.json
f = open(args.configjson, "r")
config_file = f.read()
config_json = json.loads(config_file)
calendar_urls = config_json["cryptpad_urls"]
download_dir = os.path.abspath(config_json["download_directory"])
export_dir = os.path.abspath(config_json["export_directory"])

# Initial perm checks
if not os.access(download_dir, os.W_OK):
            sys.exit("Download directory not writeable or doesn't exist! Quitting...")
if not os.access(export_dir, os.W_OK):
            sys.exit("Export directory not writeable or doesn't exist! Quitting...")            


# Main function to download ICS file from cryptpad
def download_ics_selenium(calendar_url):
    # Download dialog options
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_experimental_option("prefs", {
        "download.default_directory": download_dir,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True
    })
    # Headless
    chrome_options.add_argument('--headless')
    # Launch chrome
    driver = webdriver.Chrome(options=chrome_options)
    # Navigate to CryptPad Calendar URL and sleep for appropiate time for UI to load
    driver.get(calendar_url)
    time.sleep(25)
    # Switch to iframe in CryptPad
    iframe = driver.find_element(By.ID, "sbox-iframe")
    driver.switch_to.frame(iframe)
    # Find and click the calendar options button
    search = driver.find_element(By.XPATH,'//*[@id="cp-sidebarlayout-leftside"]/div/div[2]/span[3]/button')
    search.click()
    time.sleep(5)
    # Find and click the Export button
    search = driver.find_element(By.XPATH,'//*[@id="cp-sidebarlayout-leftside"]/div/div[2]/span[3]/div/ul/li[3]/a')
    search.click()
    time.sleep(5)
    # Download calendar file
    search = driver.find_element(By.XPATH,'/html/body/div[5]/div/div/nav/button[2]')
    search.click()
    time.sleep(5)
    # sleep for a while for the download to go through
    time.sleep(10) 
    # Close browser
    driver.quit()

# Download the ICS files one by one
for calendar_url in calendar_urls:
    download_ics_selenium(calendar_url)

# Create the combined calendar object
combined_cal = Calendar()
combined_cal.add('prodid', '-//icalcombine//TODO//EN')
combined_cal.add('version', '2.0')

# Start parsing downloaded ICS files
for ics in os.listdir(download_dir):
    # Get the full filepath
    ics_filepath_temp = download_dir + "/" + ics
    ics_filepath = os.path.abspath(ics_filepath_temp)
    # Remove UTF-8 BOM
    # https://stackoverflow.com/questions/55588551/google-calendar-not-showing-events-from-icalendar-ics-file-hosted-on-s3
    # https://stackoverflow.com/questions/8898294/convert-utf-8-with-bom-to-utf-8-with-no-bom-in-python
    s = open(ics_filepath, mode='r', encoding='utf-8-sig').read()
    open(ics_filepath, mode='w', encoding='utf-8').write(s)
    # Open the ICS file and read every event, then add to combined calendar object
    with open(ics_filepath, "r") as f:
        ics_stream = Calendar.from_ical(f.read())
    for event in ics_stream.walk('VEVENT'):
        combined_cal.add_component(event)
    # Delete the downloaded ICS file
    os.remove(ics_filepath)

# Write the parsed events to a new ICS file in the export dir
combined_cal_file = export_dir + "/calendar.ics"
with open(combined_cal_file, "wb") as f:
    f.write(combined_cal.to_ical())

print(datetime.now() + " Calendar export file at " + combined_cal_file)

sys.exit()
