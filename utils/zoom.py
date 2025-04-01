import requests
import time
from datetime import timedelta


class ZoomClient:

    def __init__(self, account_id, client_id, client_secret) -> None:
        self.account_id = account_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = self.get_access_token()

    def get_access_token(self):
        data = {
            "grant_type": "account_credentials",
            "account_id": self.account_id,
            "client_id": self.client_id,
            "client_secret": self.client_secret
        }
        response = requests.post("https://zoom.us/oauth/token", data=data)
        token = response.json()["access_token"]
        return token

    def get_recordings(self, email="me", post_data=""):
        headers = {
            "Authorization": f"Bearer {self.access_token}"
        }

        url = f"https://api.zoom.us/v2/users/{email}/recordings"

        return requests.get(url, headers=headers, params=post_data).json()

    def get_download_urls(self, url, password):
        return f'{url}?access_token={self.access_token}&playback_access_token={password}'

    def get_recording_object(self, email, page_size, rec_start_date, rec_end_date):
        return {
            "userId": email,
            "page_size": page_size,
            "from": rec_start_date,
            "to": rec_end_date
        }

    def per_delta(self, start, end, delta):
        """ Generator used to create deltas for recording start and end dates
        """
        curr = start
        while curr < end:
            yield curr, min(curr + delta, end)
            curr += delta

    def list_recordings(self, email, start_date, end_date):
        """ Start date now split into YEAR, MONTH, and DAY variables (Within 6 month range)
            then get recordings within that range
        """

        recordings = []
        max_retries = 3
        for start, end in self.per_delta(start_date, end_date, timedelta(days=30)):
            post_data = self.get_recording_object(email, 300, start, end)
            for _ in range(max_retries):
                try:
                    recordings_data = self.get_recordings(email, post_data)
                    break
                except requests.exceptions.ConnectTimeout:
                    print("\nrequest timeout. retying...")
                    time.sleep(3)
                    pass
                except requests.exceptions.ReadTimeout:
                    print("\nrequest timeout. retying...")
                    time.sleep(3)
                    pass
            else:
                print(f"failed to retrieve recordings for {email}. skipping...")
                return []

            if "meetings" in recordings_data:
                recordings.extend(recordings_data["meetings"])
            else:
                print(f"No 'meetings' key found in response for {email} from {start} to {end}")
                print(f"recording data is: {recordings_data}")

        return recordings

    def get_users(self):
        headers = {
            "Authorization": f"Bearer {self.access_token}"
        }
        user_url = "https://api.zoom.us/v2/users"
        response = requests.get(url=user_url, headers=headers).json()
        print(response)
        total_pages = int(response["page_count"]) + 1

        all_users = []

        for page in range(1, total_pages):
            url = f"{user_url}?page_number={str(page)}"
            user_data = requests.get(url=url, headers=headers).json()
            users = ([
                (
                    user["email"],
                    user["id"],
                    user.get("first_name", ""),  # Use .get() with a default value
                    user.get("last_name", "")  # Use .get() with a default value
                )
                for user in user_data["users"]
            ])

            all_users.extend(users)

        return all_users

class RecordingFiles:
    # TODO: zoom files already have a status. need to refactor my status to ignore this
    def __init__(self, file_json) -> None:
        self.download_url = file_json.get("download_url", None)
        self.file_extension = file_json.get("file_extension", None).lower()
        self.id = file_json.get("id", None)
        self.status = file_json.get("_status", "pending")
        self.type = file_json.get("recording_type", None)

    def to_json(self):
        return {
            "download_url": self.download_url,
            "file_extension": self.file_extension,
            "id": self.id,
            "_status": self.status,
            "type": self.type
        }


class ZoomRecording:
    def __init__(self, meeting_json, user) -> None:
        self.account_id = meeting_json.get("account_id", None)
        self.files = []
        self.id = meeting_json.get("uuid", None)
        self.password = meeting_json.get("recording_play_passcode", None)
        self.size = meeting_json.get("total_size", None)
        self.start_time = meeting_json.get("start_time", None)
        self.topic = meeting_json.get("topic", None)
        self.user = user

        for file in meeting_json.get("recording_files", []):
            self.append_recording_file(file)

    def append_recording_file(self, file_json):
        recording_file = RecordingFiles(file_json)
        self.files.append(recording_file)

    def to_json(self):
        files = []
        for recording_file in self.files:
            files.append(recording_file.to_json())
        return {
            "account_id": self.account_id,
            "files": files,
            "id": self.id,
            "password": self.password,
            "size": self.size,
            "start_time": self.start_time,
            "topic": self.topic,
            "user": self.user
        }
