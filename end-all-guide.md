# End All Guide to Downloading and DeDRM'ing Your Kindle Books

The instructions across the internet are often vague, confusing, and downright misleading. So after managing to get it all to work myself I've written these instructions for those who come later.

## Today is 2/16/2025

If you're reading this in the far future it's likely non of this will work as Amazon is removing the download to USB ability that this guide depends on, specifcally that you can avoid all the mess with KFX encryption, which is much more invovled in bypassing. 

## Setup

1) [Install Python](https://www.python.org/downloads/)
2) Download this repo: https://github.com/WeLackDiscipline/BulkKindleUSBDownloader/archive/refs/heads/manual-login.zip
3) Uncompress the files
4) Install [Calibre](https://calibre-ebook.com)
5) Download [DeDRM](https://github.com/noDRM/DeDRM_tools/releases/tag/v10.0.3)

Pause here, no need to install the plugin until the download is complete.

## Download 

5) Run `python3 -m pip install -r requirements.txt` to install script requirements
6) Run `python3 bookp-manual.py`
7) This will open a Chrome window, pass the captcha if presented and then login to Amazon and leave the window open.
8) Press Return on the script to continue and follow the instructions.
9) Copy the serial number presented at the end of the script, you'll need this for DeDRM configuration.
10) Everything will be download into the same directory under `books`

## Setup Calibre

10) Open Calibre
11) Open Preferneces menu, select Preferences, open Plugins under Advanced, select Load Plugin From File, browse to where DeDRM was downloaded and select the `DeDRM_plugin.zip` from inside the downloaded DeDRM zip file. After it's done select Restart Calibre and give it a minute to come back, if it doesn't just open Calibre back up.
12) Go back into the Plugins as above, select "Show Only User Installed Plugins" and open "File Types", select DeDRM and click "Customize Plugin".
13) In the DeDRM configuration menu select "Kindle eink ebooks", then the "plus" button and paste in the serial number outputted in step 9. No go Close, OK, Apply, and restar Calibre again.

## Convert

14) In Calibre click on Add Books, navigate to the `books` directory in the script and select all the books.
15) DeDRM works on import, so if it was successful you are now able to double click any book and open the built in reader. If you get an error that the book is DRM protected it didn't work.
16) That's it! Now you can convert the Amazon `.azw3` formart to something else for your ereader, usually `epub`. 



