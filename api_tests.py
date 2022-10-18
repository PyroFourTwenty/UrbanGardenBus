import requests
import json
import random

def sign_in_to_osem(osem_data):
    url = 'https://api.opensensemap.org/users/sign-in'
    params = {
        'email': osem_data['email'],
        'password': osem_data['password']
    }
    headers = {'content-type': 'application/json'}
    r = requests.post(url, params=params, headers=headers)
    osem_data['auth_token'] = r.json()["token"]
    osem_data['refresh_token'] = r.json()["refreshToken"]
    return r.status_code == 200


def get_list_of_available_senseboxes(osem_data):
    sense_box_names = []
    headers = {
        'content-type': 'application/json',
        'Authorization': 'Bearer {auth_token}'.format(auth_token=osem_data['auth_token'])
    }
    response = requests.get(
        "https://api.opensensemap.org/users/me/boxes", headers=headers)
    for box in response.json()['data']['boxes']:
        sense_box_names.append(box['name'])

    return sense_box_names


def post_new_sensebox(sensebox_name, osem_data):
    url = 'https://api.opensensemap.org/boxes'
    headers = {
        'content-type': 'application/json',
        'Authorization': 'Bearer '+osem_data['auth_token']
    }
    body = {
        'name': sensebox_name,
        'grouptag': 'UrbanGarden',
        'exposure': 'outdoor',
        'location': {"lat": 51.972, "lng": 7.684, "height": 66.6},
        'sensors': [
            {
                'title': '1',
                'unit': 'no unit, just a test',
                'sensorType': 'testSensorType'
            },
            {
                'title': 'Sensor2',
                'unit': 'no unit, just a test',
                'sensorType': 'anotherTestSensorType'
            }
        ],
        'ttn': {
            'dev_id': '123412341234',
            'app_id': 'lora-test-id',
            'profile': 'json'
        }
    }

    post_new_sensebox = requests.post(
        'https://api.opensensemap.org/boxes', headers=headers, data=json.dumps(body))

    return post_new_sensebox.status_code


def do_process():
    osem_data = {
        'email': '', #email here
        'password': '', #password here
        'auth_token': '',
        'refresh_token': ''
    }

    ttn_data = {

    }

    success = sign_in_to_osem(osem_data)
    if success:
        print('Successfully signed in to OSeM')
    else:
        print("Sign in to OSeM failed")
        return

    list_of_senseboxes = get_list_of_available_senseboxes(osem_data)

    name_of_new_sensebox = 'Node2'
    if not name_of_new_sensebox in list_of_senseboxes:
        post_result = post_new_sensebox(name_of_new_sensebox, osem_data)
        if post_result == 201:
            print('Posted new sensebox ', name_of_new_sensebox)
        else:
            print('Could not post new sensebox: ', post_result)
    else:
        print('Sensebox with name', name_of_new_sensebox, 'already exists')


def create_new_ttn_app(app_id, app_name="", app_description=""):
    full_acc = "" #key here
    url = 'https://eu1.cloud.thethings.network/api/v3/users/pyrofourtwenty/applications'
    headers = {
        'content-type': 'application/json',
        'Authorization': 'Bearer {auth_token}'.format(auth_token=full_acc)
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


def create_new_ttn_enddevice(join_eui, dev_eui, dev_id, app_id):
    full_acc = "" # key here
    url = 'https://eu1.cloud.thethings.network/api/v3/applications/{app_id}/devices'.format(app_id=app_id)
    headers = {
        'content-type': 'application/json',
        'Authorization': 'Bearer {auth_token}'.format(auth_token=full_acc)
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
    if status_code!=200:
        print(result.text)
    return status_code

def create_new_ttn_enddevice_formatter(dev_id, payload_formatter_js, application_id):
    full_acc = ""
    url = 'https://eu1.cloud.thethings.network/api/v3/as/applications/{application_id}/devices/{dev_id}'.format(application_id = application_id, dev_id=dev_id)
    
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
        'Authorization': 'Bearer {auth_token}'.format(auth_token=full_acc),
        'content-length': str(len(json.dumps(body))),
        'Host': 'eu1.cloud.thethings.network'
    }
    result = requests.put(url=url, headers=headers, data=json.dumps(body))
    status_code = result.status_code
    if status_code!=200:
        print(result.text)
    
    return status_code

def get_generated_dev_eui(app_id):
    full_acc = ""
    url = 'https://eu1.cloud.thethings.network/api/v3/applications/{application_id}/dev-eui'.format(application_id = app_id)
    headers = {
        #'content-type': 'application/json',
        'Authorization': 'Bearer {auth_token}'.format(auth_token=full_acc),
    }    
    body = {}
    result = requests.post(url=url, headers=headers, data=json.dumps(body))
    print(result.text)
    return result.json()["dev_eui"]

def generate_random_dev_eui():
    dev_eui = ""
    for _ in range(8):
        dev_eui+=str(hex(random.randint(0,255))).replace("0x","")
    return dev_eui

if __name__ == '__main__':
    # do_process()
    app_id = "idontfuckinknow"

    #dev_eui = get_generated_dev_eui(app_id=app_id)
    dev_eui = generate_random_dev_eui()
    dev_id = "a-python-created-device"+str(random.randint(0,999))
    print("got generated dev_eui:",dev_eui)
    print('creating new app:',create_new_ttn_app(app_id=app_id,app_description="nothing interesting to see here i guess", app_name="a whole new world"))
    print('creating new enddevice',create_new_ttn_enddevice(join_eui="0000000000000000", dev_eui=dev_eui, dev_id=dev_id, app_id=app_id))
    print('creating new payload formatter',create_new_ttn_enddevice_formatter(application_id=app_id, dev_id=dev_id, payload_formatter_js="not a real js script"))
    