import requests
import json
import random


class TtnAccess():
    full_acc_key: str = None
    username: str = None

    def __init__(self, full_account_key: str, username: str):
        self.full_acc_key = full_account_key
        self.username = username

    def create_new_ttn_app(self, app_id, app_name, app_description=""):
        url = 'https://eu1.cloud.thethings.network/api/v3/users/{username}/applications'.format(
            username=self.username)
        headers = {
            'content-type': 'application/json',
            'Authorization': 'Bearer {auth_token}'.format(auth_token=self.full_acc_key)
        }
        body = {
            "application": {
                "ids": {
                    "application_id": app_id
                },
                "name": app_name,
                "description": app_description,
                "network_server_address": "eu1.cloud.thethings.network",
                "application_server_address": "eu1.cloud.thethings.network",
                "join_server_address": "eu1.cloud.thethings.network"
            }
        }

        status_code = requests.post(
            url=url, headers=headers, data=json.dumps(body)).status_code
        return status_code

    def create_new_ttn_enddevice(self, join_eui, dev_eui, dev_id, app_id):
        url = 'https://eu1.cloud.thethings.network/api/v3/applications/{app_id}/devices'.format(
            app_id=app_id)
        headers = {
            'content-type': 'application/json',
            'Authorization': 'Bearer {auth_token}'.format(auth_token=self.full_acc_key)
        }
        body = {
            "end_device": {
                "ids": {
                    "join_eui": join_eui,
                    "dev_eui": dev_eui,
                    "device_id": dev_id,
                    "application_ids": {
                        "application_id": app_id
                    }
                },
                "network_server_address": "eu1.cloud.thethings.network",
                "application_server_address": "eu1.cloud.thethings.network",
                "join_server_address": "eu1.cloud.thethings.network"
            },
            "field_mask": {
                "paths": [
                    "network_server_address",
                    "application_server_address",
                    "join_server_address"
                ]
            }
        }
        result = requests.post(
            url=url, headers=headers, data=json.dumps(body))
        status_code = result.status_code
        if status_code != 200:
            print(result.text)
        return status_code

    def create_new_ttn_enddevice_formatter(self, dev_id, payload_formatter_js, application_id):
        url = 'https://eu1.cloud.thethings.network/api/v3/as/applications/{application_id}/devices/{dev_id}'.format(
            application_id=application_id, dev_id=dev_id)

        body = {
            "end_device": {
                "formatters": {
                    "down_formatter": "FORMATTER_NONE",
                    "up_formatter": "FORMATTER_JAVASCRIPT",
                    "up_formatter_parameter": payload_formatter_js
                }
            },
            "field_mask": {
                "paths": [
                    "formatters.down_formatter",
                    "formatters.down_formatter_parameter",
                    "formatters.up_formatter",
                    "formatters.up_formatter_parameter"
                ]
            }
        }
        headers = {
            'content-type': 'application/json',
            'Authorization': 'Bearer {auth_token}'.format(auth_token=self.full_acc_key),
            'content-length': str(len(json.dumps(body))),
            'Host': 'eu1.cloud.thethings.network'
        }
        result = requests.put(url=url, headers=headers, data=json.dumps(body))
        status_code = result.status_code
        if status_code != 200:
            print(result.text)

        return status_code

    def delete_ttn_enddevice_from_app(self, app_id, dev_id):
        url = 'https://eu1.cloud.thethings.network/api/v3/applications/{app_id}/devices/{dev_id}'.format(
            app_id=app_id, dev_id=dev_id)
        headers = {
            'content-type': 'application/json',
            'Authorization': 'Bearer {auth_token}'.format(auth_token=self.full_acc_key),
            'content-length': '0',
            'Host': 'eu1.cloud.thethings.network'
        }
        result = requests.delete(url=url, headers=headers)
        status_code = result.status_code
        if status_code != 200:
            print(result.text)

        return status_code

    def delete_ttn_app(self, app_id):
        url = 'https://eu1.cloud.thethings.network/api/v3/applications/{app_id}'.format(app_id=app_id)
        headers = {
            'content-type': 'application/json',
            'Authorization': 'Bearer {auth_token}'.format(auth_token=self.full_acc_key),
            'content-length': '0',
            'Host': 'eu1.cloud.thethings.network'
        }
        result = requests.delete(url=url, headers=headers)
        status_code = result.status_code
        if status_code != 200:
            print(result.text)

        return status_code



    def get_generated_dev_eui(self, app_id):
        url = 'https://eu1.cloud.thethings.network/api/v3/applications/{application_id}/dev-eui'.format(
            application_id=app_id)
        headers = {
            'Authorization': 'Bearer {auth_token}'.format(auth_token=self.full_acc_key),
        }
        body = {}
        result = requests.post(url=url, headers=headers, data=json.dumps(body))        
        return result.json()["dev_eui"]

    def generate_random_dev_eui(self):
        dev_eui = ""
        for _ in range(8):
            dev_eui += str(hex(random.randint(0, 255))).replace("0x", "")
        return dev_eui
