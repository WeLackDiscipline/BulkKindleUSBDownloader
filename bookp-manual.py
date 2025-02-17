#!/usr/bin/env python3

import getpass
import json
import logging
import os
import re
import requests
import sys
import urllib.parse
import pickle
import time

from argparse import ArgumentParser
from selenium import webdriver

user_agent = {'User-Agent': 'krumpli'}
logger = logging.getLogger(__name__)

def create_session():
    logger.info("Starting browser")

    print("Starting Chrome window and activing. If already logged in you'll be brought back here in a minute, otherwise login and come back.")

    options = webdriver.ChromeOptions()
    browser = webdriver.Chrome()
    cookies = {}

    logger.info("Loading www.amazon.com")
    browser.get('https://www.amazon.com')

    logger.info("Checking if you're already logged in")

    if os.path.exists("script-cookies"):
        logger.info("Found some cookies, injecting them and refreshing the browser, this takes a moment.")
        print("Found credentials - logging you in, stand by!")
        with open("script-cookies", 'rb') as f:
            cookies = pickle.load(f)
        for cookie in cookies:
            browser.add_cookie(cookie)

        browser.get('https://www.amazon.com')
        time.sleep(5)

    logger.info("Waiting for login...")

    input("\nSwitch to browser window, login, and then return here and press enter to continue.")

    logger.info("Getting CSRF token")
    browser.get('https://www.amazon.com/hz/mycd/digital-console/contentlist/booksAll/dateDsc/')

    custid = None  # Initialize custid to a default value
    match = re.search('customerId: \"(.*)\"', browser.page_source)
    if match:
        custid = match.group(1)
    else:
        print("Failed to find your customer ID, appears browser was not logged in!")
        exit(1)

    csrf_token = None  # Initialize csrf_token to a default value
    match = re.search('var csrfToken = "(.*)";', browser.page_source)
    if match:
        csrf_token = match.group(1)
    else:
        print("Failed to get CSFR")
        exit(1)

    cookies = {}
    for cookie in browser.get_cookies():
        cookies[cookie['name']] = cookie['value']

    with open("script-cookies", 'wb') as f:
        pickle.dump(browser.get_cookies(), f)

    browser.quit()

    return cookies, csrf_token, custid

def check_if_logged_in(page_source):
    return re.search('customerId: \"(.*)\"', page_source)

"""
NOTE: This function is not used currently, because the download URL can be
constructed without this additional request. This might change in the future,
so I'm keeping this here just in case.

def get_download_url(user_agent, cookies, csrf_token, asin, device_id):
    logger.info("Getting download URL for " + asin)
    data_json = {
        'param':{
            'DownloadViaUSB':{
                'contentName':asin,
                'encryptedDeviceAccountId':device_id, # device['deviceAccountId']
                'originType':'Purchase'
            }
        }
    }    

    r = requests.post('https://www.amazon.com/hz/mycd/ajax',
        data={'data':json.dumps(data_json), 'csrfToken':csrf_token},
        headers=user_agent, cookies=cookies)
    rr = json.loads(r.text)["DownloadViaUSB"]
    return rr["URL"] if rr["success"] else None
"""


def get_devices(user_agent, cookies, csrf_token):
    logger.info("Getting device list")
    print("Loading device list, this may take a moment....")

    data_json = {'param': {'GetDevices': {}}}

    r = requests.post('https://www.amazon.com/hz/mycd/ajax',
                      data={'data': json.dumps(data_json), 'csrfToken': csrf_token},
                      headers=user_agent, cookies=cookies)
    devices = json.loads(r.text)["GetDevices"]["devices"]

    return [device for device in devices if 'deviceSerialNumber' in device and device['deviceClassification'] == 'KINDLE_DEVICES']


def get_asins(user_agent, cookies, csrf_token):
    logger.info("Getting e-book list")
    print("Loading book list, this may take a moment...")

    startIndex = 0
    batchSize = 100
    data_json = {
        'param': {
            'OwnershipData': {
                'sortOrder': 'DESCENDING',
                'sortIndex': 'DATE',
                'startIndex': startIndex,
                'batchSize': batchSize,
                'contentType': 'Ebook',
                'itemStatus': ['Active'],
                'originType': ['Purchase'],
            }
        }
    }

    # NOTE: This loop could be replaced with only one request, since the
    # response tells us how many items are there ('numberOfItems'). I guess that
    # number will never be high enough to cause problems, but I want to be on
    # the safe side, hence the download in batches approach.
    asins = []
    while True:
        r = requests.post('https://www.amazon.com/hz/mycd/ajax',
                          data={'data': json.dumps(data_json), 'csrfToken': csrf_token},
                          headers=user_agent, cookies=cookies)
        rr = json.loads(r.text)
        asins += [book['asin'] for book in rr['OwnershipData']['items']]

        if rr['OwnershipData']['hasMoreItems']:
            startIndex += batchSize
            data_json['param']['OwnershipData']['startIndex'] = startIndex
        else:
            break

    print("Found " + str(len(asins)) + " books!")
    return asins


def download_books(user_agent, cookies, device, asins, custid, directory):
    logger.info("Downloading {} books".format(len(asins)))
    print("Starting downloads of {} books, this is slow...".format(len(asins)))

    cdn_url = 'https://cde-ta-g7g.amazon.com/FionaCDEServiceEngine/FSDownloadContent'
    cdn_params = 'type=EBOK&key={}&fsn={}&device_type={}&customerId={}&authPool=Amazon'

    for asin in asins:
        try:
            params = cdn_params.format(asin, device['deviceSerialNumber'], device['deviceType'], custid)
            r = requests.get(cdn_url, params=params, headers=user_agent, cookies=cookies, stream=True)
            name = re.findall("filename\\*=UTF-8''(.+)", r.headers['Content-Disposition'])[0]
            name = urllib.parse.unquote(name)
            name = name.replace('/', '_')
            with open(os.path.join(directory, name), 'wb') as f:
                for chunk in r.iter_content(chunk_size=512):
                    f.write(chunk)
            print('Downloaded ' + asin + ': ' + name)
            logger.info('Downloaded ' + asin + ': ' + name)
        except Exception as e:
            print('Warning: Failed to download ' + asin + ' check logs for additional details.')
            print(e)
            logger.debug(e)
            logger.error('Failed to download ' + asin)


def main():
    parser = ArgumentParser(description="Amazon e-book downloader.")
    parser.add_argument("--verbose", help="show info messages", action="store_true")
    parser.add_argument("--outputdir", help="download directory (default: books)", default="books")
    parser.add_argument("--asin", help="list of ASINs to download", nargs='*')
    parser.add_argument("--logfile", help="name of file to write log to", default=None)
    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.INFO)
    else:
        logger.setLevel(logging.WARNING)
    formatter = logging.Formatter('[%(levelname)s]\t%(asctime)s %(message)s')
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    logfilename = args.logfile
    if logfilename:
        handlerLog = logging.FileHandler(logfilename)
        logger.addHandler(handlerLog)

    if os.path.isfile(args.outputdir):
        logger.error("Output directory is a file!")
        return -1
    elif not os.path.isdir(args.outputdir):
        os.mkdir(args.outputdir)

    cookies, csrf_token, custid = create_session()
    if not args.asin:
        asins = get_asins(user_agent, cookies, csrf_token)
    else:
        asins = args.asin

    devices = get_devices(user_agent, cookies, csrf_token)
    print("\n\nChoose a Kindle ereader device:")
    for i in range(len(devices)):
        print(" " + str(i) + ". " + devices[i]['deviceAccountName'])
    while True:
        try:
            choice = int(input("Device #: "))
        except:
            logger.error("Not a number!")
        if choice in range(len(devices)):
            break

    download_books(user_agent, cookies, devices[choice], asins, custid, args.outputdir)

    logger.info('Download complete, open with Serial Number: ' + devices[choice]['deviceSerialNumber'] + ' Name: ' + devices[choice]['deviceAccountName'])
    
    print("\n\nAll done!\nNow you can use nodrm's DeDRM tools " \
          "(https://github.com/nodrm/DeDRM_tools)\n" \
          "with the following serial number to remove DRM: " +
          devices[choice]['deviceSerialNumber'])

    if os.path.exists("script-cookies"):
        print("\n\nWARNING: If you're all done be sure to delete script-cookies")
        if input("Type delete to clean up cookies, or anything else to exit.").lower() == "delete" :
            os.remove("script-cookies")
        else:
            print("Leaving cookies alone, please delete them when you're done!")

if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        logger.info("Exiting...")

