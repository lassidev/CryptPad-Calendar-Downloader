import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime

from icalendar import Calendar
from selenium import webdriver
from selenium.webdriver.common.by import By

# Arguments
parser = argparse.ArgumentParser()
parser.add_argument(
    "-c",
    "--configfile",
    default="./config.json",
    help="Location of the config file"
)
parser.add_argument(
    '-log',
    '--loglevel',
    default='INFO',
    help='Provide logging level. Example --loglevel DEBUG, default=INFO'
)
args = parser.parse_args()

# Logging
loglevel = args.loglevel.upper()
if loglevel not in logging._nameToLevel.keys():
    print(f"Incorrect loglevel {loglevel}. Setting loglevel to DEBUG")
    loglevel = "DEBUG"

logging.basicConfig(
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%y%m%d %H:%M:%S",
    level=loglevel
)

logging.info("Starting script!\n\n\n")

# Set variables from config.json
try:
    with open(args.configfile, "r") as f:
        config_file = f.read()
    config_json = json.loads(config_file)
    calendar_urls = config_json["cryptpad_urls"]
except Exception:
    logging.critical("Something went wrong reading the config file")
    sys.exit()

download_dir = os.path.abspath(config_json["download_directory"])
export_dir = os.path.abspath(config_json["export_directory"])

# Initial permission checks
if not os.access(download_dir, os.W_OK):
    logging.critical("Download directory not writable or doesn't exist! Quitting...")
    sys.exit()

if not os.access(export_dir, os.W_OK):
    logging.critical("Export directory not writable or doesn't exist! Quitting...")
    sys.exit()


# Main function to download ICS file from CryptPad
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

    # Clear browser cache
    driver.execute_cdp_cmd("Network.clearBrowserCache", {})
    driver.execute_cdp_cmd('Storage.clearDataForOrigin', {
        "origin": '*',
        "storageTypes": 'all',
    })
    driver.delete_all_cookies()

    # Navigate to CryptPad Calendar URL and sleep for appropriate time for UI to load
    driver.get(calendar_url)
    time.sleep(40)

    # Switch to iframe in CryptPad
    iframe = driver.find_element(By.ID, "sbox-iframe")
    driver.switch_to.frame(iframe)

    # Find and click the calendar options button
    search = driver.find_element(
        By.XPATH, '//*[@id="cp-sidebarlayout-leftside"]/div/div[2]/span[3]/button'
    )
    search.click()
    time.sleep(10)

    # Find and click the Export button
    search = driver.find_element(
        By.XPATH, '//*[@id="cp-sidebarlayout-leftside"]/div/div[2]/span[3]/div/ul/li[3]/a'
    )
    search.click()
    time.sleep(10)

    # Download calendar file
    search = driver.find_element(By.XPATH, '/html/body/div[5]/div/div/nav/button[2]')
    search.click()
    time.sleep(10)

    # Sleep for a while for the download to go through
    time.sleep(20)

    # Close browser
    driver.quit()


# Download the ICS files one by one
def download_calendars(calendar_urls):
    for calendar_url in calendar_urls:
        try:
            download_ics_selenium(calendar_url)
            logging.info("Downloaded .ics from %s", calendar_url)
            logging.debug('Files in download dir: \n%s', str(os.listdir(download_dir)))
        except Exception:
            logging.critical(
                "Something went wrong downloading the ics file from %s", calendar_url
            )
    logging.info('All files (Calendar-name.ics):\n%s', str(os.listdir(download_dir)))


# Create the combined calendar object
def combined_calendar():
    combined_cal = Calendar()
    combined_cal.add('prodid', '-//icalcombine//ORG//EN')
    combined_cal.add('version', '2.0')
    logging.debug("Created combined calendar object")

    ics_files = os.listdir(download_dir)
    if not ics_files:
        logging.critical(
            "No ics files seem to be in the download directory. quitting..."
        )
        return
    else:
        logging.debug("ics files in directory:")

    # Start parsing downloaded ICS files
    for ics in ics_files:
        try:
            logging.debug("Reading from ics file %s", ics)

            # Get the full filepath
            ics_filepath = os.path.abspath(os.path.join(download_dir, ics))

            # Remove UTF-8 BOM
            s = open(ics_filepath, mode='r', encoding='utf-8-sig').read()
            open(ics_filepath, mode='w', encoding='utf-8').write(s)

            # Open the ICS file and read every event, then add to combined calendar object
            with open(ics_filepath, "r") as f:
                ics_stream = Calendar.from_ical(f.read())

            for event in ics_stream.walk('VEVENT'):
                combined_cal.add_component(event)
                logging.debug("Event created: %s", str(event.get("summary")))

            # Delete the downloaded ICS file
            os.remove(ics_filepath)

        except Exception:
            logging.critical("Something went wrong reading from ics file %s", ics)

    # Write the parsed events to a new ICS file in the export dir
    combined_cal_file = os.path.join(export_dir, "calendar.ics")
    with open(combined_cal_file, "wb") as f:
        f.write(combined_cal.to_ical())

    logging.info("Calendar export file at %s", combined_cal_file)


# Main execution
download_calendars(calendar_urls)
combined_calendar()

sys.exit()