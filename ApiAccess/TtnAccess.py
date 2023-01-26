import requests
import json
import random
import secrets

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
        
        request = requests.post(
            url=url, headers=headers, data=json.dumps(body))
        return request.status_code

    def create_new_ttn_enddevice(self, join_eui, dev_eui, dev_id, app_id, app_key):
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

        body = {
            "end_device":{
                "frequency_plan_id":"EU_863_870_TTN",
                "lorawan_version":"MAC_V1_0_2",
                "lorawan_phy_version":"PHY_V1_0_2_REV_A",
                "supports_join":True,
                "multicast":False,
                "supports_class_b":False,
                "supports_class_c":False,
                "mac_settings":{
                    "rx2_data_rate_index":0,
                    "rx2_frequency":"869525000"
                },
                "ids":{
                    "join_eui":join_eui,
                    "dev_eui":dev_eui,
                    "device_id":dev_id,
                    "application_ids":{
                        "application_id":app_id
                    }
                }
            },
            "field_mask":{
                "paths":[
                    "frequency_plan_id",
                    "lorawan_version",
                    "lorawan_phy_version",
                    "supports_join",
                    "multicast",
                    "supports_class_b",
                    "supports_class_c",
                    "mac_settings.rx2_data_rate_index",
                    "mac_settings.rx2_frequency","ids.join_eui","ids.dev_eui","ids.device_id","ids.application_ids.application_id"] 
            }
        }
        configure_device_ns =  requests.put(url="https://eu1.cloud.thethings.network/api/v3/ns/applications/{app_id}/devices/{dev_id}".format(app_id=app_id, dev_id=dev_id), headers=headers, data=json.dumps(body))
        print('Configuration ns status code:',configure_device_ns.status_code)
        
        body = {
            "end_device": {
              "ids": {
                "join_eui": join_eui,
                "dev_eui": dev_eui,
                "device_id": dev_id,
                "application_ids": {
                  "application_id": app_id
                }
              }
            },
            "field_mask": {
              "paths": [
                "ids.join_eui",
                "ids.dev_eui",
                "ids.device_id",
                "ids.application_ids.application_id"
              ]
            }
        }

        configure_device_as = requests.put(url="https://eu1.cloud.thethings.network/api/v3/as/applications/{app_id}/devices/{dev_id}".format(app_id=app_id, dev_id=dev_id), headers=headers, data=json.dumps(body))
        print('Configuration as status code:',configure_device_as.status_code)

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
            "root_keys": {
              "app_key": {
                "key": app_key
              }
            }
          },
          "field_mask": {
            "paths": [
              "network_server_address",
              "application_server_address",
              "ids.join_eui",
              "ids.dev_eui",
              "ids.device_id",
              "ids.application_ids.application_id",
              "root_keys.app_key.key"
            ]
          }
        }
        
        configure_device_js = requests.put(url="https://eu1.cloud.thethings.network/api/v3/js/applications/{app_id}/devices/{dev_id}".format(app_id=app_id, dev_id=dev_id), headers=headers, data=json.dumps(body))
        print('Configuration js status code:',configure_device_js.status_code)
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

    def generate_random_dev_eui(self, length=8):
        return secrets.token_hex(length)

    def get_activation_info_for_enddevice(self, app_id, dev_id):
        headers = {
            'Authorization': 'Bearer {auth_token}'.format(auth_token=self.full_acc_key),
        }
        #get_device_id = requests.get(
        #    url="https://eu1.cloud.thethings.network/api/v3/applications/{app_id}/devices/{dev_id}?field_mask=root_keys".format(app_id=app_id, dev_id=dev_id), headers=headers)
        #
        #device_id = get_device_id.json()["ids"]["device_id"] 
        #print("got device_id for enddevice", dev_id,"-->",device_id)
        #https://eu1.cloud.thethings.network/api/v3/js/applications/lora-test-id/devices/eui-70b3d57ed005925a?field_mask=root_keys
        url = 'https://eu1.cloud.thethings.network/api/v3/js/applications/{app_id}/devices/{dev_id}?field_mask=root_keys'.format(app_id=app_id, dev_id=dev_id)
        
        body = {}
        result = requests.post(url=url, headers=headers, data=json.dumps(body))       
        print(result.json())
        activation = {
            "app_eui": result.json()["ids"]["join_eui"],
            "app_key": result.json()["root_keys"]["app_key"]["key"],
            "dev_eui": result.json()["ids"]["dev_eui"],
        }
        return activation

    def add_webhook_to_ttn_app(self, app_id, webhook_id):
        url = 'https://eu1.cloud.thethings.network/api/v3/as/webhooks/{app_id}'.format(app_id=app_id)
        headers = {
            'Authorization': 'Bearer {auth_token}'.format(auth_token=self.full_acc_key),
        }

        body = {"webhook":{
                "service_data":None,
                "location_solved":None,
                "downlink_queue_invalidated":None,
                "downlink_queued":None,
                "downlink_failed":None,
                "downlink_sent":None,
                "downlink_nack":None,
                "downlink_ack":None,
                "join_accept":None,
                "uplink_normalized":None,
                "uplink_message":{
                    "path":""
                },
                "downlink_api_key":"",
                "base_url":"https://ttn.opensensemap.org/v3",
                "field_mask":{
                    "paths":[]
                },
                "format":"json",
                "ids":{
                    "webhook_id":webhook_id
                },
                "headers":{}
                },
                "field_mask":{"paths":["service_data","location_solved","downlink_queue_invalidated","downlink_queued","downlink_failed","downlink_sent","downlink_nack","downlink_ack","join_accept","uplink_normalized","uplink_message.path","downlink_api_key","base_url","field_mask","format","ids.webhook_id","headers"
                ]
            }
            }
        result = requests.post(url=url, headers=headers, data=json.dumps(body))
        return result.status_code 
    
    def get_application_ids(self):
        ids = []
        url = "https://eu1.cloud.thethings.network/api/v3/applications"#?page=1&limit=20&order=-created_at&field_mask=name%2Cdescription%2Cnetwork_server_address%2Capplication_server_address%2Cjoin_server_address"
        headers = {
            'Authorization': 'Bearer {auth_token}'.format(auth_token=self.full_acc_key),
        }
        result = requests.get(url=url, headers=headers)
        if result.status_code == 200:
            for app in result.json()['applications']:
                ids.append(app["ids"]["application_id"])
        return ids
    
    def get_enddevice_ids_of_app(self, app_id):
        ids = []
        url = "https://eu1.cloud.thethings.network/api/v3/applications/{app_id}/devices".format(app_id=app_id)
        headers = {
            'Authorization': 'Bearer {auth_token}'.format(auth_token=self.full_acc_key),
        }
        result = requests.get(url=url, headers=headers)
        if result.status_code == 200:
            try:

                for app in result.json()['end_devices']:
                    ids.append(app["ids"]["device_id"])
            except KeyError:
                pass
        return ids
    
