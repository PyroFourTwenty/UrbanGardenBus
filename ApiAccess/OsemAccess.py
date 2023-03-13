import requests
import json
from time import time
from .ApiAccessExceptions import InvalidCredentials, NoInternetConnection
class OsemAccess:
    email: str = ''
    password: str = ''
    auth_token = ''
    refresh_token = ''
    last_sign_in = None
    refresh_sign_in_after_seconds = 10*60 # 10 minutes
    def __init__(self, email: str = '', password: str = '', auto_sign_in = True):
        self.email = email
        self.password = password
        if auto_sign_in:
            self.sign_in()

    def sign_in(self):
        url = 'https://api.opensensemap.org/users/sign-in'
        params = {
            'email': self.email,
            'password': self.password
        }
        headers = {'content-type': 'application/json'}
        try:
            r = requests.post(url, params=params, headers=headers)
            if r.status_code == 200:
                self.auth_token = r.json()["token"]
                self.refresh_token = r.json()["refreshToken"]
                self.last_sign_in = time()
            else:
                raise InvalidCredentials()
            return r.status_code == 200
        except requests.exceptions.ConnectionError:
            raise NoInternetConnection()

    def check_last_sign_in(self):
        if self.last_sign_in is not None:
            if time()-self.last_sign_in>=self.refresh_sign_in_after_seconds:
                self.sign_in()
        else:
            self.sign_in()

    def get_available_senseboxes(self):
        self.check_last_sign_in()
        sensebox_names = []
        headers = {
            'content-type': 'application/json',
            'Authorization': 'Bearer {auth_token}'.format(auth_token=self.auth_token)
        }
        response = requests.get(
            "https://api.opensensemap.org/users/me/boxes", headers=headers)
        for box in response.json()['data']['boxes']:
            sensebox_names.append((box['name'],box['_id']))
            #print(box['name'],'has id',box['_id'])

        return sensebox_names

    def get_sensor_ids_of_sensebox(self, sensebox_id):
        self.check_last_sign_in()
        sensor_ids = []
        headers = {
            'content-type': 'application/json',
            'Authorization': 'Bearer {auth_token}'.format(auth_token=self.auth_token)
        }
        response = requests.get(
            "https://api.opensensemap.org/users/me/boxes", headers=headers)
        for box in response.json()['data']['boxes']:
            if box["_id"] == sensebox_id:
                for sensor in box['sensors']:
                    sensor_ids.append((sensor['_id']))
        return sensor_ids
        
    def post_new_sensebox(self, sensebox_name, ttn_dev_id, ttn_app_id, lat=52.4564629, lng=13.5233899, height=36):
        self.check_last_sign_in()
        url = 'https://api.opensensemap.org/boxes'
        headers = {
            'content-type': 'application/json',
            'Authorization': 'Bearer '+self.auth_token
        }
        body = {
            'name': sensebox_name,
            'grouptag': 'UrbanGarden',
            'exposure': 'outdoor',
            'location': {"lat": lat, "lng": lng, "height": height},
            'sensors': [{
                "id": 0,
                "sensorType": "delete-me",
                "title": "delete-me",
                "unit": "delete-me"
            }],
            'ttn': {
                'dev_id': ttn_dev_id,
                'app_id': ttn_app_id,
                'profile': 'json'
            }
        }

        post_new_sensebox = requests.post(
                url, headers=headers, data=json.dumps(body))

        sensebox_id = None
        try:
            sensebox_id = post_new_sensebox.json()['data']['_id']
        except KeyError:
            pass    
        return post_new_sensebox.status_code, sensebox_id

    def delete_sensebox(self, sensebox_id):
        self.check_last_sign_in()
        url = 'https://api.opensensemap.org/boxes/{sensebox_id}'.format(sensebox_id=sensebox_id)
        headers = {
            'content-type': 'application/json',
            'Authorization': 'Bearer '+self.auth_token
        }
        body= {
            "password" : self.password
        }
        return requests.delete(url=url, headers=headers,data=json.dumps(body)).status_code

    def put_new_sensor(self, sensebox_id:str, icon:str, sensor_type:str, phenomenon:str, unit:str, delete_dummy_sensor= True):
        print("checking last signin")
        self.check_last_sign_in()
        print("checking last signin done")
        url = 'https://api.opensensemap.org/boxes/{sensebox_id}'.format(
            sensebox_id=sensebox_id)

        headers = {
            'content-type': 'application/json',
            'Authorization': 'Bearer '+self.auth_token
        }
        body = {
            "sensors": [
                {
                    "icon": icon,
                    "sensorType": sensor_type,
                    "title": phenomenon,
                    "unit": unit,
                    "new": True,
                    "edited": True
                }
            ]
        }
        print("now putting new sensor")
        put_new_sensor = requests.put(
                url, headers=headers, data=json.dumps(body))
            
        for _ in range(10):

            print("ASDASDASD")
        print("PUT NEW SENSOR", put_new_sensor)
        if delete_dummy_sensor:
            self.delete_obligatory_first_sensor(sensebox_id=sensebox_id)
        new_sensor_id = None
        sensors_in_response = put_new_sensor.json()['data']['sensors'] 
        latest_sensor = sensors_in_response[len(sensors_in_response)-1]
        new_sensor_id = latest_sensor['_id']
                
        return put_new_sensor.status_code,new_sensor_id

    def delete_sensor(self, sensebox_id, sensor_id):
        self.check_last_sign_in()
        headers = {
            'content-type': 'application/json',
            'Authorization': 'Bearer {auth_token}'.format(auth_token=self.auth_token)
        }
        delete_url = 'https://api.opensensemap.org/boxes/{sensebox_id}'.format(sensebox_id=sensebox_id)

        body={
            "sensors":[
                {
                    "sensorType":"delete-me",
                    "title":"delete-me",
                    "unit":"delete-me",
                    "_id": sensor_id,
                    "chart":{"yAxisTitle":"","data":[],"done":False,"error":False},"deleted":True
                }
            ]
        }
        print("Deleting sensor {sensor}  in sensebox id {sensebox} ".format(sensor=sensor_id, sensebox=sensebox_id))
        delete_response = requests.put(delete_url, headers=headers, data=json.dumps(body))
        if delete_response.status_code==400:
            if "needs at least one" in delete_response.json()["message"]:
                print("putting dummy sensor to delete the other one")
                self.put_new_sensor(sensebox_id=sensebox_id, icon='', sensor_type='delete-me',phenomenon='delete-me',unit='delete-me', delete_dummy_sensor=False)
        delete_response = requests.put(delete_url, headers=headers, data=json.dumps(body))
        return delete_response.status_code
    
    def delete_obligatory_first_sensor(self, sensebox_id):
        ''' Deletes the dummy sensor that has to be created upon sensebox creation if at least one other sensor is created '''
        self.check_last_sign_in()
        headers = {
            'content-type': 'application/json',
            'Authorization': 'Bearer {auth_token}'.format(auth_token=self.auth_token)
        }
        response = requests.get(
            "https://api.opensensemap.org/users/me/boxes", headers=headers)
        sensor_count = None
        dummy_sensor_id = None
        for box in response.json()['data']['boxes']:
            if box['_id'] == sensebox_id:
                for sensor in box['sensors']:
                    sensor_count = len(box['sensors'])
                    if sensor['sensorType'] == 'delete-me':
                        dummy_sensor_id=sensor['_id']

        print('Found ',sensor_count,'sensor(s)')
        if dummy_sensor_id:
            delete_url = 'https://api.opensensemap.org/boxes/{sensebox_id}'.format(sensebox_id=sensebox_id)
            
            body={
                "sensors":[
                    {
                        "sensorType":"delete-me",
                        "title":"delete-me",
                        "unit":"delete-me",
                        "_id": dummy_sensor_id,
                        "chart":{"yAxisTitle":"","data":[],"done":False,"error":False},"deleted":True
                    }
                ]
            }
            delete_response = requests.put(delete_url, headers=headers, data=json.dumps(body))
            print('Yeeted this sensor -> ',dummy_sensor_id)