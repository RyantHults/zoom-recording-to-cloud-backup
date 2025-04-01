import json
import os


def save_to_json_file(file_path, json_dict):
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(json_dict, f, ensure_ascii=False, indent=4)


def append_to_json_file(field_name, file_path, json_dict):
    with open(file_path, 'r') as file:
        data = json.load(file)

    data[field_name].append(json_dict)

    with open(file_path, 'w') as file:
        json.dump(data, file, ensure_ascii=False, indent=4)


def update_meeting_json_file(file_path, meeting_id, meeting_json):
    try:
        with open(file_path, 'r') as file:
            data = json.load(file)

    except (FileNotFoundError, json.JSONDecodeError):
        # If file doesn't exist or is empty/invalid, start with empty dict
        data = {}

    if meeting_id in data:
        data[meeting_id].update(meeting_json)
    else:
        data[meeting_id] = meeting_json

    with open(file_path, 'w') as file:
        json.dump(data, file, ensure_ascii=False, indent=4)


def remove_empty_subfolders(path_abs):
    walk = list(os.walk(path_abs))
    for path, _, _ in walk[::-1]:
        if len(os.listdir(path)) == 0:
            os.rmdir(path)




