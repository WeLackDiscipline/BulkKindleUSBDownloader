# Bulk Kindle USB Downloader Manual Login Mode

The `bookp-manual.py` method requires less setup, but will open a Chromium window for you to manually login into. If you're having issues with `bookp.py` getting running or logging in this is going to be the fastest solution.

Additionally this version only uses Selenium, without ChromeDriver as ChromeDriver may no be installable for you.

## Steps

### Setup

* *Install Python3*
* Run `python3 -m pip install -r requirements.txt` to install necesary packages

### Run

* Run `python3 bookp-manual.py`
* Wait for Chrome window to pop up, and login - DO NOT CLOSE THE WINDOW!
> Note: Every time you run this you will have to login, it doesn't store your Amazon session.
* Return to script and press Return
* Wait for downloads to complete!
* Move on to other things.