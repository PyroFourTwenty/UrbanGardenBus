from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

class Persistence():
    client = None
    connection_data = {}
    def __init__(self,connection_data):
        self.connection_data = connection_data
        self.connect_to_db()
    
    def connect_to_db(self):
        self.client = InfluxDBClient(
            url=self.connection_data["url"],
            token=self.connection_data["token"],
            org= self.connection_data["org"],
            debug=self.connection_data["debug"],
        )

    def write_to_db(self, data:dict):
        write_api = self.client.write_api(write_options=SYNCHRONOUS)
        _point = Point(data["packet_identifier"])
        
        for key in data["meta"]:
            _point.tag(key, data["meta"][key])
        if "payload" in data:
            for key in data["payload"]:
                _point.field(key, data["payload"][key])
        else:
            _point.field("payload", 0)
        bucket = 'ugb_data/autogen'
        write_api.write(bucket=bucket, record=_point)

