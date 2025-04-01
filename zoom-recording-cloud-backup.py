#!/usr/bin/env python3

# Program Name: zoom-recording-cloud-backup.py
# Description:  Zoom Recording Cloud Backup is a cross-platform Python script
#               that uses Zoom's API (v2) to download and organize all
#               cloud recordings from a Zoom account onto local storage,
#               or optionally to upload the files directly to sharepoint instead.
#               This Python script uses the OAuth method of accessing the Zoom API
# Created:      2025-02-21
# Author:       Ryan Hults
# Website:      https://github.com/RyantHults/zoom-recording-to-cloud-backup
# Forked from:  https://github.com/ricardorodrigues-ca/zoom-recording-downloader

# System modules
import base64
import datetime
import json
import os
import re as regex
import signal
import sys as system
from datetime import date, timezone
import math
import asyncio
from pathlib import Path
import argparse

# Installed modules
import dateutil.parser as parser
import pathvalidate as path_validate
import requests
import tqdm as progress_bar
from zoneinfo import ZoneInfo
from utils.zoom import ZoomClient, ZoomRecording
from utils.file_io import remove_empty_subfolders, update_meeting_json_file
from utils.msgraph_utils import get_graphql_client, upload_large_file


class Color:
    PURPLE = "\033[95m"
    CYAN = "\033[96m"
    DARK_CYAN = "\033[36m"
    BLUE = "\033[94m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    END = "\033[0m"


CONF_PATH = "zoom-recording-cloud-backup.conf"

# Load configuration file and check for proper JSON syntax
try:
    with open(CONF_PATH, encoding="utf-8-sig") as json_file:
        CONF = json.loads(json_file.read())
except json.JSONDecodeError as e:
    print(f"{Color.RED}### Error parsing JSON in {CONF_PATH}: {e}")
    system.exit(1)
except FileNotFoundError:
    print(f"{Color.RED}### Configuqration file {CONF_PATH} not found")
    system.exit(1)
except Exception as e:
    print(f"{Color.RED}### Unexpected error: {e}")
    system.exit(1)


def config(section, key, default=''):
    try:
        return CONF[section][key]
    except KeyError:
        if default == LookupError:
            print(f"{Color.RED}### No value provided for {section}:{key} in {CONF_PATH}")
            system.exit(1)
        else:
            return default


# Zoom API credentials
ZOOM_ACCOUNT_ID = config("Zoom", "account_id", LookupError)
ZOOM_CLIENT_ID = config("Zoom", "client_id", LookupError)
ZOOM_CLIENT_SECRET = config("Zoom", "client_secret", LookupError)
ZOOM_ACCESS_TOKEN = ""
ZOOM_AUTHORIZATION_HEADER = {
    "Authorization": f"Bearer {ZOOM_ACCESS_TOKEN}",
    "Content-Type": "application/json"
}

# Sharepoint App credentials
AZURE_TENANT_ID = config("Sharepoint", "tenant_id", LookupError)
AZURE_CLIENT_ID = config("Sharepoint", "client_id", LookupError)
AZURE_SITE_URL = config("Sharepoint", "site_url", LookupError)

# Sharepoint upload settings
SHAREPOINT_BASE_DIR_NAME = config("Sharepoint", "remote_folder_name", LookupError)
SHAREPOINT_BASE_DIR_PATH = f"root:/{SHAREPOINT_BASE_DIR_NAME}"
SHAREPOINT_DRIVE_ID = config("Sharepoint", "drive_id", LookupError)

APP_VERSION = "1.0"
LOAD_FROM_FILE = False

# Zoom API endpoints
ZOOM_API_ENDPOINT_USER_LIST = "https://api.zoom.us/v2/users"

RECORDING_START_DATE = parser.parse(config("Recordings", "start_date", str(
    datetime.datetime.now() - datetime.timedelta(30)))).replace(tzinfo=timezone.utc)
RECORDING_END_DATE = parser.parse(config("Recordings", "end_date", str(date.today()))).replace(tzinfo=timezone.utc)
DOWNLOAD_DIRECTORY = config("Storage", "download_dir", 'downloads')
COMPLETED_MEETING_RECORD = Path(config("Storage", "completed_log", 'completed-downloads.json'))
COMPLETED_MEETING_IDS = set()

MEETING_TIMEZONE = ZoneInfo(config("Recordings", "timezone", 'UTC'))
MEETING_STRFTIME = config("Recordings", "strftime", '%Y.%m.%d - UTC')
MEETING_FILENAME = config("Recordings", "filename",
                          '{meeting_time} - {topic} - {rec_type} - {recording_id}.{file_extension}')
MEETING_FOLDER = config("Recordings", "folder", '{topic} - {meeting_time}')


def get_zoom_access_token():
    """ OAuth function, thanks to https://github.com/freelimiter
    """
    url = f"https://zoom.us/oauth/token?grant_type=account_credentials&account_id={ZOOM_ACCOUNT_ID}"

    client_cred = f"{ZOOM_CLIENT_ID}:{ZOOM_CLIENT_SECRET}"
    client_cred_base64_string = base64.b64encode(client_cred.encode("utf-8")).decode("utf-8")

    headers = {
        "Authorization": f"Basic {client_cred_base64_string}",
        "Content-Type": "application/x-www-form-urlencoded"
    }

    response = json.loads(requests.request("POST", url, headers=headers).text)

    global ZOOM_ACCESS_TOKEN
    global ZOOM_AUTHORIZATION_HEADER

    try:
        ZOOM_ACCESS_TOKEN = response["access_token"]
        ZOOM_AUTHORIZATION_HEADER = {
            "Authorization": f"Bearer {ZOOM_ACCESS_TOKEN}",
            "Content-Type": "application/json"
        }

    except KeyError:
        print(f"{Color.RED}### The key 'access_token' wasn't found.{Color.END}")


# def get_zoom_users():
#     """ loop through pages and return all users """
#     response = requests.get(url=ZOOM_API_ENDPOINT_USER_LIST, headers=ZOOM_AUTHORIZATION_HEADER)
#
#     if not response.ok:
#         print(response)
#         print(
#             f"{Color.RED}### Could not retrieve users. Please make sure that your access "
#             f"token is still valid{Color.END}"
#         )
#
#         system.exit(1)
#
#     page_data = response.json()
#     total_pages = int(page_data["page_count"]) + 1
#
#     all_users = []
#
#     for page in range(1, total_pages):
#         url = f"{ZOOM_API_ENDPOINT_USER_LIST}?page_number={str(page)}"
#         user_data = requests.get(url=url, headers=ZOOM_AUTHORIZATION_HEADER).json()
#         users = ([
#             (
#                 user["email"],
#                 user["id"],
#                 user.get("first_name", ""),  # Use .get() with a default value
#                 user.get("last_name", "")  # Use .get() with a default value
#             )
#             for user in user_data["users"]
#         ])
#
#         all_users.extend(users)
#
#     return all_users


def format_filename(params):
    file_extension = params["file_extension"].lower()
    recording = params["recording"]
    recording_id = params["recording_id"]
    recording_type = params["recording_type"]

    invalid_chars_pattern = r'[<>:"/\\|?*\x00-\x1F]'
    topic = regex.sub(invalid_chars_pattern, '', recording.topic)
    topic = topic.replace(" ", "_")
    rec_type = recording_type.replace("_", " ").title()
    meeting_time_utc = parser.parse(recording.start_time).replace(tzinfo=timezone.utc)
    meeting_time_local = meeting_time_utc.astimezone(MEETING_TIMEZONE)
    year = meeting_time_local.strftime("%Y")
    month = meeting_time_local.strftime("%m")
    day = meeting_time_local.strftime("%d")
    meeting_time = f"{year}.{month}.{day}"

    filename = MEETING_FILENAME.format(**locals())
    folder = MEETING_FOLDER.format(**locals())
    return filename, folder


# def get_downloads(recording):
#     if not recording.get("recording_files"):
#         raise Exception
#
#     downloads = []
#     for download in recording["recording_files"]:
#         file_type = download["file_type"]
#         file_extension = download["file_extension"]
#         recording_id = download["id"]
#
#         if file_type == "":
#             recording_type = "incomplete"
#         elif file_type != "TIMELINE":
#             recording_type = download["recording_type"]
#         else:
#             recording_type = download["file_type"]
#
#         # must append access token to download_url
#         download_url = f"{download['download_url']}?access_token={ZOOM_ACCESS_TOKEN}"
#         downloads.append((file_type, file_extension, download_url, recording_type, recording_id))
#
#     return downloads


def get_recording_object(email, page_size, rec_start_date, rec_end_date):
    return {
        "userId": email,
        "page_size": page_size,
        "from": rec_start_date,
        "to": rec_end_date
    }


def per_delta(start, end, delta):
    """ Generator used to create deltas for recording start and end dates
    """
    curr = start
    while curr < end:
        yield curr, min(curr + delta, end)
        curr += delta


def download_recording(download_url, email, filename, folder_name):
    dl_dir = os.sep.join([DOWNLOAD_DIRECTORY, folder_name])
    sanitized_download_dir = path_validate.sanitize_filepath(dl_dir)
    sanitized_filename = path_validate.sanitize_filename(filename)
    full_filename = os.sep.join([sanitized_download_dir, sanitized_filename])

    os.makedirs(sanitized_download_dir, exist_ok=True)

    response = requests.get(download_url, stream=True)

    # total size in bytes.
    total_size = int(response.headers.get("content-length", 0))
    block_size = 32 * 1024  # 32 Kibibytes

    # create TQDM progress bar
    prog_bar = progress_bar.tqdm(dynamic_ncols=True, total=total_size, unit="iB", unit_scale=True)
    try:
        with open(full_filename, "wb") as fd:
            for chunk in response.iter_content(block_size):
                prog_bar.update(len(chunk))
                fd.write(chunk)  # write video chunk to disk
        prog_bar.close()

        return True

    except Exception as e:
        print(
            f"{Color.RED}### The video recording with filename '{filename}' for user with email "
            f"'{email}' could not be downloaded because {Color.END}'{e}'"
        )
        prog_bar.close()
        return False


def convert_size(size_bytes):
    if size_bytes == 0:
        return "0B"
    size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return "%s %s" % (s, size_name[i])


def get_users_from_file(filename):
    with open(filename, mode='r', newline='', encoding='utf-8') as userfile:
        return json.loads(userfile.read())


def get_recordings_for_users(users, zoom_client, load_from_file=False):
    recordings = []

    if load_from_file:
        print("getting data from file")
        with open('data.json', 'r') as file:
            data = json.load(file)
        for recording in data:
            recordings.append(ZoomRecording(recording, recording["user"]))
    else:
        for user in users:
            print(f"getting meeting recordings for {user}")
            recording_json = zoom_client.list_recordings(user, RECORDING_START_DATE, RECORDING_END_DATE)
            recording_count = len(recording_json)
            print(f"Retrieved {recording_count} recordings for user {user}")
            for meeting in recording_json:
                meeting_info = ZoomRecording(meeting, user)
                recordings.append(meeting_info)

                # save results to file
                # append_to_json_file(user, COMPLETED_MEETING_RECORD, meeting_info.to_json())

    return recordings


def handle_graceful_shutdown(signal_received, frame):
    print(f"\n{Color.DARK_CYAN}SIGINT or CTRL-C detected. system.exiting gracefully.{Color.END}")

    system.exit(0)


# ################################################################
# #                        MAIN                                  #
# ################################################################

async def main():
    # clear the screen buffer
    os.system('cls' if os.name == 'nt' else 'clear')

    # show the logo
    print(f"""
        {Color.DARK_CYAN}


                             ,*****************.
                          *************************
                        *****************************
                      *********************************
                     ******               ******* ******
                    *******                .**    ******
                    *******                       ******/
                    *******                       /******
                    ///////                 //    //////
                    ///////*              ./////.//////
                     ////////////////////////////////*
                       /////////////////////////////
                          /////////////////////////
                             ,/////////////////

                        Zoom Recording Cloud Backup

                        V{APP_VERSION}

        {Color.END}
    """)
    interactive = True
    users = []

    parser = argparse.ArgumentParser()
    parser.add_argument("-f", "--userfile", help="full filepath to json file containing emails of the users who's recordings you'd like to backup (ex. userlist.json)", default="")
    parser.add_argument("-u", "--user", help="email of the user who's recordings you'd like to backup", default="")
    parser.add_argument("--dry_run", help="run through the program without actually downloading or uploading anything", default=False)
    args = parser.parse_args()

    if args:
        interactive = False

    dry_run = args.dry_run
    userlist_file = args.userfile

    if interactive:
        # Storage choice prompt
        print("\nWho's recordings should be backed up?")
        print("1. All users in users.json")
        print("2. A specific user")
        choice = input("Enter choice [1]: ")

        if choice == "2":
            print("\nEnter the email of the user who's recordings you wish to backup")
            users = [input("Enter user's email: ")]
        else:
            print("unknown input. \nExiting...")
            return 1

        print("\nIs this a dry-run?")
        choice = input("Y/n: ")

        if choice.lower() == "n" or choice.lower == "no":
            dry_run = False

    if userlist_file:
        users = get_users_from_file(userlist_file)
        print(f"{len(users)} loaded")
    else:
        users = [args.user]

    # Zoom client auth and init
    zoom_client = ZoomClient(account_id=ZOOM_ACCOUNT_ID, client_id=ZOOM_CLIENT_ID, client_secret=ZOOM_CLIENT_SECRET)

    # sharepoint client
    graph_client = get_graphql_client(AZURE_CLIENT_ID, AZURE_TENANT_ID)

    # statistic variables
    total_recording_size = 0
    completed_recordings = 0
    failed_files = 0

    # Zoom Recording retrieval
    # -----------------------------------------------------------------
    print("requesting recordings for each user")
    # gather all zoom recordings
    recordings = get_recordings_for_users(users, zoom_client)

    # create meeting record file if it doesn't exist
    if not COMPLETED_MEETING_RECORD.exists():
        with open(COMPLETED_MEETING_RECORD, 'w') as json_file:
            json.dump({}, json_file, ensure_ascii=False, indent=4)

    # if we failed to retrieve any recordings and there aren't any
    # previously retrieved recordings, then there is nothing left to do
    if not recordings:
        if COMPLETED_MEETING_RECORD.is_file():
            print("no recordings retrieved from zoom API")
            print("checking for previously retrieved recordings")

            with open(COMPLETED_MEETING_RECORD, 'r') as file:
                data = json.load(file)

            if len(data) == 0:
                print("No previously retrieved recordings found")
                print("Exiting...")
                return 1

            for meeting in data:
                recordings.append(ZoomRecording(meeting))
        else:
            print("no recordings loaded, and upload list file found!")
            print("Exiting...")
            return 1

    # download from zoom and upload to Sharepoint upload
    # -----------------------------------------------------------------
    for recording in recordings:

        print("\n============== Processing Recording ================")

        if recording.user not in users:
            print(f"User {recording.user} not part of supplied userlist. skipping...")
            continue

        print(f"{len(recording.files)} files found for this recording")
        for file in recording.files:
            print(f"\nprocessing file {file.type}.{file.file_extension}")
            params = {
                "file_extension": file.file_extension,
                "recording": recording,
                "recording_id": file.id,
                "recording_type": file.type
            }
            filename, folder_name = format_filename(params)
            sanitized_download_dir = path_validate.sanitize_filepath(
                os.sep.join([DOWNLOAD_DIRECTORY, folder_name])
            )
            sanitized_filename = path_validate.sanitize_filename(filename)
            local_file_path = os.sep.join([sanitized_download_dir, sanitized_filename])

            # file needs to be downloaded from zoom
            if file.status == "pending":
                # download recording

                # add access code and password to download url
                download_url_with_auth = zoom_client.get_download_urls(file.download_url, recording.password)

                print(f"    > Downloading {filename}")
                try:
                    if dry_run:
                        print("file.download_url, recording.user, filename, folder_name")
                        print(f"{download_url_with_auth}, {recording.user}, {filename}, {folder_name}")
                    elif download_recording(download_url_with_auth, recording.user, filename, folder_name):
                        file.status = "downloaded"
                        update_meeting_json_file(COMPLETED_MEETING_RECORD, recording.id, file.to_json())

                except Exception as e:
                    print(
                        f"{Color.RED}### Failed to process file {file.type} "
                        f"for recording {file.id} of meeting {recording.id} due to error: "
                        f"{str(e)}{Color.END}"
                    )
                    file.status = "download failed"
                    update_meeting_json_file(COMPLETED_MEETING_RECORD, recording.id, file.to_json())
                    failed_files += 1
                    continue

            # file is ready to uploaded
            if file.status == "downloaded":
                # upload file to remote
                # note that if an object at remote_file_path already exists in remote,
                # it will be overwritten
                remote_file_path = f"{SHAREPOINT_BASE_DIR_PATH}/{recording.user}/{folder_name}/{os.path.basename(local_file_path)}:"
                try:
                    if dry_run:
                        print(f"remote file path is {remote_file_path}")
                    else:
                        print(f"    > Uploading to {folder_name}")
                        await upload_large_file(graph_client, SHAREPOINT_DRIVE_ID, local_file_path, remote_file_path)
                # catch any upload errors and log them, but continue
                except Exception as e:
                    print(f"Exception: {e}")
                    print(f"failed to upload file {file.type}.{file.file_extension}\nContinuing...")
                    file.status = "upload failed"
                    failed_files += 1
                    update_meeting_json_file(COMPLETED_MEETING_RECORD, recording.id, file.to_json())
                    continue
                else:
                    file.status = "uploaded"
                    completed_recordings += 1
                    total_recording_size += recording.size
                    update_meeting_json_file(COMPLETED_MEETING_RECORD, recording.id, file.to_json())
                    os.remove(local_file_path)

            print(f"Finished processing file {recording.topic}.{file.file_extension}")


    # print out summary of work done
    print(f"successfully uploaded: {completed_recordings} recordings")
    print(f"failed to upload: {failed_files} files")
    print(f"total size of uploaded files: {convert_size(total_recording_size)}")
    print("cleaning up empty folders...")
    remove_empty_subfolders(DOWNLOAD_DIRECTORY)



if __name__ == "__main__":
    # tell Python to shutdown gracefully when SIGINT is received
    signal.signal(signal.SIGINT, handle_graceful_shutdown)

    asyncio.run(main())
