import argparse
import json
import logging
import os
import sys
from datetime import datetime

from icalendar import Calendar
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def init():
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

    # Setup logging
    setup_logging(args.loglevel)

    logging.info("Starting script!\n\n\n")

    # Load and validate config
    try:
        with open(args.configfile, "r") as f:
            config_file = f.read()
        config_json = json.loads(config_file)
        validate_config(config_json)
    except ValueError as e:
        logging.critical(e)
        sys.exit()
    except Exception:
        logging.critical("Something went wrong reading the config file")
        sys.exit()

    # Ensure directories are writable and exist
    download_dir = os.path.abspath(config_json["download_directory"])
    export_dir = os.path.abspath(config_json["export_directory"])
    ensure_directory_exists(download_dir)
    ensure_directory_exists(export_dir)

    if not is_directory_writable(download_dir) or not is_directory_writable(export_dir):
        sys.exit()

    return config_json, download_dir, export_dir


# Logging setup with color formatter
# ANSI color codes
RESET = "\x1b[0m"
BOLD = "\x1b[1m"
RED = "\x1b[31m"
YELLOW = "\x1b[33m"
GREEN = "\x1b[32m"
BLUE = "\x1b[34m"


class ColorFormatter(logging.Formatter):
    LEVEL_COLORS = {
        logging.CRITICAL: f"{BOLD}{RED}",
        logging.ERROR: f"{BOLD}{RED}",
        logging.WARNING: f"{BOLD}{YELLOW}",
        logging.INFO: f"{BOLD}{GREEN}",
        logging.DEBUG: f"{BOLD}{BLUE}",
    }

    def format(self, record):
        original_levelname = record.levelname
        color = self.LEVEL_COLORS.get(record.levelno, "")
        record.levelname = f"{color}{original_levelname}{RESET}"
        formatted_message = super().format(record)
        record.levelname = original_levelname  # Restore original levelname
        return formatted_message


def setup_logging(loglevel):
    loglevel = loglevel.upper()
    if loglevel not in logging._nameToLevel.keys():
        print(f"Incorrect loglevel {loglevel}. Setting loglevel to DEBUG")
        loglevel = "DEBUG"
    handler = logging.StreamHandler()
    handler.setFormatter(
        ColorFormatter("[%(asctime)s][%(levelname)s][%(funcName)s:%(lineno)d] %(message)s")
    )
    logging.basicConfig(
        handlers=[handler],
        datefmt="%y%m%d %H:%M:%S",
        format="[%(asctime)s][%(levelname)s][%(funcName)s:%(lineno)d] %(message)s",
        level=loglevel.upper()
    )


def validate_config(config):
    required_keys = ["cryptpad_urls", "download_directory", "export_directory"]
    for key in required_keys:
        if key not in config:
            raise ValueError(f"Missing required config key: {key}")


def ensure_directory_exists(directory):
    if not os.path.exists(directory):
        os.makedirs(directory)
        logging.info("Created missing directory: %s", directory)


def is_directory_writable(directory):
    if not os.access(directory, os.W_OK):
        logging.critical("Directory %s not writable or doesn't exist!", directory)
        return False
    return True


def setup_chrome_driver(download_dir):
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_experimental_option("prefs", {
        "download.default_directory": download_dir,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True
    })
    chrome_options.add_argument('--headless')
    driver = webdriver.Chrome(options=chrome_options)
    return driver


def clear_browser_cache(driver):
    driver.execute_cdp_cmd("Network.clearBrowserCache", {})
    driver.execute_cdp_cmd('Storage.clearDataForOrigin', {"origin": '*', "storageTypes": 'all'})
    driver.delete_all_cookies()


def wait_for_element(driver, by, value, timeout=30):
    return WebDriverWait(driver, timeout).until(EC.presence_of_element_located((by, value)))


def download_ics_selenium(calendar_url, download_dir):
    driver = setup_chrome_driver(download_dir)
    clear_browser_cache(driver)

    try:
        driver.get(calendar_url)
        wait_for_element(driver, By.ID, "sbox-iframe")

        # Switch to iframe in CryptPad
        iframe = driver.find_element(By.ID, "sbox-iframe")
        driver.switch_to.frame(iframe)

        # Find and click the calendar options button
        search = wait_for_element(driver, By.XPATH, '//*[@id="cp-sidebarlayout-leftside"]/div/div[2]/span[3]/button')
        search.click()

        # Find and click the Export button
        search = wait_for_element(driver, By.XPATH, '//*[@id="cp-sidebarlayout-leftside"]/div/div[2]/span[3]/div/ul/li[3]/a')
        search.click()

        # Download calendar file
        search = wait_for_element(driver, By.XPATH, '/html/body/div[5]/div/div/nav/button[2]')
        search.click()

        # Wait for download to complete (adjust timeout as needed)
        WebDriverWait(driver, 20).until(lambda d: len(os.listdir(download_dir)) > 0)

    except Exception as e:
        logging.error("Error during download: %s", e)

    finally:
        driver.quit()


def download_calendars(calendar_urls, download_dir):
    for calendar_url in calendar_urls:
        try:
            download_ics_selenium(calendar_url, download_dir)
            logging.info("Downloaded .ics from %s", calendar_url)
            logging.debug('Files in download dir: \n%s', str(os.listdir(download_dir)))
        except KeyboardInterrupt:
            logging.debug('Ctrl+C detected, skipping URL %s', calendar_url)
        except Exception as e:
            logging.critical("Something went wrong downloading the ics file from %s: %s", calendar_url, e)
    logging.info('All files (Calendar-name.ics):\n%s', str(os.listdir(download_dir)))


def combined_calendar(download_dir, export_dir):
    combined_cal = Calendar()
    combined_cal.add('prodid', '-//icalcombine//ORG//EN')
    combined_cal.add('version', '2.0')
    logging.debug("Created combined calendar object")

    ics_files = os.listdir(download_dir)
    if not ics_files:
        logging.critical("No ics files seem to be in the download directory. quitting...")
        return

    # Start parsing downloaded ICS files
    for ics in ics_files:
        try:
            logging.debug("Reading from ics file %s", ics)

            # Get the full filepath
            ics_filepath = os.path.abspath(os.path.join(download_dir, ics))

            # Remove UTF-8 BOM
            # Useful for fixing issues with Google Calendar not showing events:
            # https://stackoverflow.com/questions/55588551/google-calendar-not-showing-events-from-icalendar-ics-file-hosted-on-s3
            # Reference for removing BOM from UTF-8 files:
            # https://stackoverflow.com/questions/8898294/convert-utf-8-with-bom-to-utf-8-with-no-bom-in-python
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


if __name__ == "__main__":
    config, download_dir, export_dir = init()

    # Main execution
    download_calendars(config["cryptpad_urls"], download_dir)
    combined_calendar(download_dir, export_dir)

    sys.exit()