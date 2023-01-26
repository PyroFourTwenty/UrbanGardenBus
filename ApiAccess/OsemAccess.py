import requests
import json


class OsemAccess:
    email: str = ''
    password: str = ''
    auth_token = ''
    refresh_token = ''

    def __init__(self, email: str = '', password: str = ''):
        self.email = email
        self.password = password
        self.sign_in()

    def sign_in(self):
        url = 'https://api.opensensemap.org/users/sign-in'
        params = {
            'email': self.email,
            'password': self.password
        }
        headers = {'content-type': 'application/json'}
        r = requests.post(url, params=params, headers=headers)
        if r.status_code == 200:
            self.auth_token = r.json()["token"]
            self.refresh_token = r.json()["refreshToken"]
        else:
            raise Exception("OsemAccess: OpenSenseMap login credentials seem to be invalid")
        return r.status_code == 200

    def get_available_senseboxes(self):
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

    def put_new_sensor(self, sensebox_id:str, icon:str, sensor_type:str, phenomenon:str, unit:str):
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

        put_new_sensor = requests.put(
            url, headers=headers, data=json.dumps(body))
        self.delete_obligatory_first_sensor(sensebox_id=sensebox_id)
        return put_new_sensor.status_code,put_new_sensor.json()['data']['_id']

    def delete_obligatory_first_sensor(self, sensebox_id):
        ''' Deletes the dummy sensor that has to be created upon sensebox creation if at least one other sensor is created '''
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
