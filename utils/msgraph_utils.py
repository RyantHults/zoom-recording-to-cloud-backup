import asyncio
from datetime import datetime, timedelta, timezone
import tqdm as progress_bar
import os
from azure.identity import InteractiveBrowserCredential
from msgraph import GraphServiceClient
from msgraph_core.tasks.large_file_upload import LargeFileUploadTask, LargeFileUploadSession
from msgraph.generated.drives.item.items.item.create_upload_session.create_upload_session_post_request_body import \
    CreateUploadSessionPostRequestBody
from msgraph.generated.models.drive_item_uploadable_properties import DriveItemUploadableProperties
from kiota_abstractions.api_error import APIError

def get_graphql_client(client_id, tenant_id):
    credential = InteractiveBrowserCredential(
        client_id=client_id,
        tenant_id=tenant_id,
    )
    scopes = ['https://graph.microsoft.com/.default']
    # credential.authenticate(scopes=scopes)
    client = GraphServiceClient(credential, scopes)
    return client


async def get_drives(client):
    drives = await client.drives.get()
    drive_list = []

    if drives and drives.value:
        for drive in drives.value:
            drive_dict = {
                "id": drive.id,
                "drive_type": drive.drive_type,
                "name": drive.name,
                "description": drive.description,
                "web_url": drive.web_url
            }
            drive_list.append(drive)

    return drive_list


async def get_drive(client, drive_id):
    drive = await client.drives.by_drive_id(drive_id).get()
    if drive:
        print(drive.id, drive.drive_type, drive.name, drive.description, drive.web_url)
        return drive


async def get_drive_items(client, drive_id):
    items = await client.drives.by_drive_id(drive_id).items.get()
    item_list = []
    if items and items.value:
        for item in items.value:
            print(item.id, item.name, item.size, item.folder, item.file)
            item_list.append(item)
    return item_list


async def get_drive_item(client, drive_id, item_id):
    item = await client.drives.by_drive_id(drive_id).items.by_drive_item_id(item_id).get()
    if item:
        print(item.id, item.name, item.size, item.folder, item.file)
        return item


async def get_drive_root(client, drive_id):
    root = await client.drives.by_drive_id(drive_id).root.get()
    if root:
        print(root.id, root.name, root.folder.child_count, root.root, root.size)
        return root


async def get_drive_root_items(client, drive_id):
    items = await client.drives.by_drive_id(drive_id).items.by_drive_item_id('root').children.get()
    items_list = []
    if items and items.value:
        for item in items.value:
            print(item.id, item.name, item.size, item.folder, item.file)
            items_list.append(item)
    return items_list


async def upload_large_file(client, drive_id, local_file_path, remote_file_path):
    try:
        file = open(local_file_path, 'rb')
        uploadable_properties = DriveItemUploadableProperties(
            additional_data={'@microsoft.graph.conflictBehavior': 'replace'}
        )
        upload_session_request_body = CreateUploadSessionPostRequestBody(item=uploadable_properties)
        # can be used for normal drive uploads
        try:
            upload_session = await client.drives.by_drive_id(
                drive_id).items.by_drive_item_id(remote_file_path).create_upload_session.post(
                upload_session_request_body)

        except APIError as ex:
            print(f"Error creating upload session: {ex}")

        max_chunk_size = 5 * 1024 * 1024
        total_length = os.path.getsize(local_file_path)

        # if filesize is smaller than default max chunk size,
        # LargeFileUploadTask returns a 400
        if total_length < max_chunk_size:
            max_chunk_size = (total_length - 1)

        # to be used for large file uploads
        large_file_upload_session = LargeFileUploadSession(
            upload_url=upload_session.upload_url,
            expiration_date_time=datetime.now(timezone.utc) + timedelta(days=1),
            additional_data=upload_session.additional_data,
            is_cancelled=False,
            next_expected_ranges=upload_session.next_expected_ranges,
        )

        task = LargeFileUploadTask(
            large_file_upload_session,
            client.request_adapter,
            file,
            max_chunk_size=max_chunk_size
        )

        # Upload the file
        # The callback
        def progress_callback(uploaded_byte_range: tuple[int, int]):
            prog_bar.update(int(uploaded_byte_range[1]) - int(uploaded_byte_range[0]))

        prog_bar = progress_bar.tqdm(dynamic_ncols=True, total=total_length, unit="iB", unit_scale=True)

        try:
            upload_result = await task.upload(progress_callback)
            prog_bar.close()
            print(f"Upload complete")
        except APIError as ex:
            prog_bar.close()
            print(f"Error uploading: {ex.message} - {ex.response_status_code}")
    except APIError as e:
        print(f"Error: {e}")
