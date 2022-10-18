import requests
import json

class OsemAccess:
    email :str = ''
    password :str = ''
    auth_token = ''
    refresh_token = ''

    def __init__(self, email:str = '', password:str = '') :
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
        self.auth_token = r.json()["token"]
        self.refresh_token = r.json()["refreshToken"]
        return r.status_code == 200
    
    def get_available_senseboxes(self):
        sense_box_names = []
        headers = {
            'content-type': 'application/json',
            'Authorization': 'Bearer {auth_token}'.format(auth_token=self.auth_token)
        }
        response = requests.get(
            "https://api.opensensemap.org/users/me/boxes", headers=headers)
        for box in response.json()['data']['boxes']:
            sense_box_names.append(box['name'])

        return sense_box_names


    def post_new_sensebox(self,sensebox_name, lat=52.4564629, lng=13.5233899,height=36):
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
            'sensors': [],
            'ttn': {
                'dev_id': '123412341234',
                'app_id': 'lora-test-id',
                'profile': 'json'
            }
        }

        post_new_sensebox = requests.post(
            'https://api.opensensemap.org/boxes', headers=headers, data=json.dumps(body))

        return post_new_sensebox.status_code  