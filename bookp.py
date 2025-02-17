#!/usr/bin/env python3

import getpass
import json
import logging
import os
import re
import requests
import sys
import urllib.parse

from argparse import ArgumentParser
from pyvirtualdisplay import Display
from selenium import webdriver
from selenium.webdriver.common.by import By

user_agent = {'User-Agent': 'krumpli'}
logger = logging.getLogger(__name__)


def create_session(email, password, oath, browser_visible=True, proxy=None):
    if not browser_visible:
        display = Display(visible=0)
        display.start()

    logger.info("Starting browser")
    options = webdriver.ChromeOptions()
    if proxy:
        options.add_argument('--proxy-server=' + proxy)
    browser = webdriver.Chrome()

    logger.info("Loading www.amazon.com")
    browser.get('https://www.amazon.com')

    logger.info("Logging in")
    browser.find_element(By.CSS_SELECTOR,'#gw-sign-in-button > span > a').click()
    browser.find_element(By.ID,"ap_email").clear()
    browser.find_element(By.ID, "ap_email").send_keys(email)
    browser.find_element(By.CSS_SELECTOR, '.a-button-input').click()
    browser.find_element(By.ID,"ap_password").clear()
    browser.find_element(By.ID,"ap_password").send_keys(password)
    browser.find_element(By.ID,"signInSubmit").click()
    browser.find_element(By.ID, "auth-mfa-otpcode").clear()
    browser.find_element(By.ID, "auth-mfa-otpcode").send_keys(oath)
    browser.find_element(By.ID, "auth-signin-button").click()

    logger.info("Getting CSRF token")
    browser.get('https://www.amazon.com/hz/mycd/digital-console/contentlist/booksAll/dateDsc/')

    csrf_token = None  # Initialize csrf_token to a default value
    match = re.search('var csrfToken = "(.*)";', browser.page_source)
    if match:
        csrf_token = match.group(1)

    custid = None  # Initialize custid to a default value
    match = re.search('customerId: \"(.*)\"', browser.page_source)
    if match:
        custid = match.group(1)

    cookies = {}
    for cookie in browser.get_cookies():
        cookies[cookie['name']] = cookie['value']

    browser.quit()
    if not browser_visible:
        display.stop();

    return cookies, csrf_token, custid


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
    data_json = {'param': {'GetDevices': {}}}

    r = requests.post('https://www.amazon.com/hz/mycd/ajax',
                      data={'data': json.dumps(data_json), 'csrfToken': csrf_token},
                      headers=user_agent, cookies=cookies)
    devices = json.loads(r.text)["GetDevices"]["devices"]

    return [device for device in devices if 'deviceSerialNumber' in device]


def get_asins(user_agent, cookies, csrf_token):
    logger.info("Getting e-book list")
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

    return asins


def download_books(user_agent, cookies, device, asins, custid, directory):
    logger.info("Downloading {} books".format(len(asins)))
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
            logger.info('Downloaded ' + asin + ': ' + name)
        except Exception as e:
            logger.debug(e)
            logger.error('Failed to download ' + asin)


def main():
    parser = ArgumentParser(description="Amazon e-book downloader.")
    parser.add_argument("--verbose", help="show info messages", action="store_true")
    parser.add_argument("--showbrowser", help="display browser while creating session.", action="store_true")
    parser.add_argument("--email", help="Amazon account e-mail address", required=True)
    parser.add_argument("--password", help="Amazon account password", default=None)
    parser.add_argument("--oath", help="Amazon account oath code", default=None)
    parser.add_argument("--outputdir", help="download directory (default: books)", default="books")
    parser.add_argument("--proxy", help="HTTP proxy server", default=None)
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

    password = args.password
    if not password:
        password = getpass.getpass("Your Amazon password: ")

    oath = args.oath
    if not oath:
        oath = getpass.getpass("Your Amazon Oath: ")

    if os.path.isfile(args.outputdir):
        logger.error("Output directory is a file!")
        return -1
    elif not os.path.isdir(args.outputdir):
        os.mkdir(args.outputdir)

    cookies, csrf_token, custid = create_session(args.email, password, oath,
                                         browser_visible=args.showbrowser, proxy=args.proxy)
    if not args.asin:
        asins = get_asins(user_agent, cookies, csrf_token)
    else:
        asins = args.asin

    devices = get_devices(user_agent, cookies, csrf_token)
    print("Please choose which device you want to download your e-books to!")
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

    print("\n\nAll done!\nNow you can use nodrm's DeDRM tools " \
          "(https://github.com/nodrm/DeDRM_tools)\n" \
          "with the following serial number to remove DRM: " +
          devices[choice]['deviceSerialNumber'])
    logger.info('Download complete, open with Serial Number: ' + devices[choice]['deviceSerialNumber'])

if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        logger.info("Exiting...")

