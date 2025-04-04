# ⚡️ zoom-recording-downloader ⚡️ 
## ☁️ Now with Sharepoint support ☁️

[![Python 3.11](https://img.shields.io/badge/python-3.11%20%2B-blue.svg)](https://www.python.org/) [![License](https://img.shields.io/badge/license-MIT-brown.svg)](https://raw.githubusercontent.com/rhults/zoom-recording-to-cloud-backup/master/LICENSE)

**Zoom Recording Cloud Backup** is a cross-platform Python app that utilizes Zoom's API (v2) to grab and organize all cloud recordings from a Zoom Business account and upload it to a sharepoint site

## Screenshot ##


## Installation ##

_Attention: You will need [Python 3.11](https://www.python.org/downloads/) or greater_

```sh
$ git clone https://github.com/RyantHults/zoom-recording-to-cloud-backup
$ cd zoom-recording-to-cloud-backup
$ pip3 install -r requirements.txt
```

## Usage ##

_Attention: You will need a [Zoom Developer account](https://marketplace.zoom.us/) in order to create a [Server-to-Server OAuth app](https://developers.zoom.us/docs/internal-apps/) with the required credentials_

1. Create an [Server-to-Server OAuth app](https://developers.zoom.us/docs/internal-apps/), set up your app and collect your credentials (`Account ID`, `Client ID`, `Client Secret`). For questions on this, [reference the docs](https://developers.zoom.us/docs/integrations/create/) on creating an OAuth app. Make sure you activate the app. Follow Zoom's [set up documentation](https://marketplace.zoom.us/docs/guides/build/server-to-server-oauth-app/) or [this video](https://www.youtube.com/watch?v=OkBE7CHVzho) for a more complete walk through.

2. Add the necessary scopes to your app. In your app's _Scopes_ tab, add the following scopes: 
    > `cloud_recording:read:list_user_recordings:admin`, `user:read:user:admin`, `user:read:list_users:admin`.

3. Copy **zoom-recording-downloader.conf.template** to a new file named **zoom-recording-downloader.conf** and fill in your Server-to-Server OAuth app credentials:
```
      {
	      "OAuth": {
		      "account_id": "<ACCOUNT_ID>",
		      "client_id": "<CLIENT_ID>",
		      "client_secret": "<CLIENT_SECRET>"
	      }
      }
```

4. You can optionally add other options to the configuration file:

- Specify the base **download_dir** under which the recordings will be downloaded (default is 'downloads')
- Specify the **completed_log** log file that will store the ID's of downloaded recordings (default is 'completed-downloads.log')

```
      {
              "Storage": {
                      "download_dir": "downloads",
                      "completed_log": "completed-downloads.log"
              }
      }
```

- Specify the **start_date** from which to start downloading meetings (default is Jan 1 of this year)
- Specify the **end_date** at which to stop downloading meetings (default is today)
- Dates are specified as YYYY-MM-DD

```
      {
              "Recordings": {
                      "start_date": "2024-01-01",
                      "end_date": "2024-12-31"
              }
      }
```

- Specify the timezone for the saved meeting times saved in the filenames (default is 'UTC')
- You can use any timezone supported by [ZoneInfo](https://docs.python.org/3/library/zoneinfo.html)
- Specify the time format for the saved meeting times in the filenames (default is '%Y.%m.%d - %I.%M %p UTC')
- You can use any of the [strftime format codes](https://docs.python.org/3/library/datetime.html#strftime-and-strptime-format-codes) supported by datetime

```
      {
              "Recordings": {
                      "timezone": "America/New_York",
                      "strftime": "%Y.%m.%d-%H.%M%z"
              }
      }
```

- Specify the format for the filenames of saved meetings (default is '{meeting_time} - {topic} - {rec_type} - {recording_id}.{file_extension}')
- Specify the format for the folder name (under the download folder) for saved meetings (default is '{topic} - {meeting_time}')

```
      {
              "Recordings": {
                      "filename": "{meeting_time}-{topic}-{rec_type}-{recording_id}.{file_extension}",
                      "folder": "{year}/{month}/{meeting_time}-{topic}"
              }
      }
```

For the previous formats you can use the following values
  - **{file_extension}** is the lowercase version of the file extension
  - **{meeting_time}** is the time in the format of **strftime** and **timezone**
  - **{day}** is the day from **meeting_time**
  - **{month}** is the month from **meeting_time**
  - **{year}** is the year from **meeting_time**
  - **{recording_id}** is the recording id from zoom
  - **{rec_type}** is the type of the recording
  - **{topic}** is the title of the zoom meeting

## Sharepoint Setup ##

To enable sharepoint upload support:

1. Update your config:
	```json
	{
                "Sharepoint": {
                        "tenant_id": "<ACCOUNT_ID>",
                        "client_id": "<CLIENT_ID>",
                        "drive_id": "<DRIVE_ID>",
                        "remote_folder_name": "<REMOTE_FOLDER_NAME>",
                        "site_url": "https://YOUR_SHAREPOINT_SITE_URL"
                },
	}
	```

Note: When you first run the script, it will open your default browser for authentication. 

## Run Command ##

if you have a large amount of accounts to backup, 
you can save them to a file and pass the file in with the userfile option (-f --userfile):
```sh
$ python zoom-recording-cloud-backup.py --userfile users.json
```

if you'd like to backup a single user's recordings, you can pass the user option (-u or --user)
```sh
python zoom-recording-cloud-backup.py --user user@domain.tld
```

if you'd like the program to print out what it's going to do without actually uploading or downloading
anything, you can run it with the --dry_run option
```sh
python zoom-recording-cloud-backup.py --dry-run
```

Note: files are temporarily downloaded to local storage before being uploaded, then automatically deleted after successful upload.