from GardenBusClient.SupportedSensors import supported_sensors
import struct
from flask_app import app
from flask_sqlalchemy import SQLAlchemy
from models import Station, Sensor, CalibrationValueForSensor

db = SQLAlchemy(app)

def number_to_bytes(number_ : int, number_of_bytes : int = 1, print_to_console:bool= False) -> bytearray:
    binary_node_id = bin(number_).replace("0b","")
    leading_zeros = "0" * (number_of_bytes*8-len(binary_node_id))
    
    stuffed = leading_zeros+binary_node_id
    if print_to_console:
        print(stuffed)
    return ([int(stuffed[i:i+8],2) for i in range(0, len(stuffed), 8)])

def byte_to_number(byte):
    return bytes_to_number([byte])

def bytes_to_number(bytes:list) -> int:
    return int.from_bytes(bytearray(bytes),"big")

def get_sensor_key_by_id(sensor_id:int):
    sensors = supported_sensors.sensors
    for sensor in sensors:
        if sensors[sensor]['id']==sensor_id: #if the value corresponding to the key we are holding has the id we are looking for
            return sensor # return the key of the sensor
    #returns None if no sensor could be found with the wanted id

def bitstring_to_bytes(s):
    return int(s, 2).to_bytes((len(s) + 7) // 8, byteorder='big')

def binary(num):
    return ''.join('{:0>8b}'.format(c) for c in struct.pack('!f', num))

def get_calibration_value_for_sensor_of_node(node_id, sensor_slot ):
    with app.app_context():
        try:
            return CalibrationValueForSensor.query.filter_by(
                belongs_to_sensor_id = Sensor.query.filter_by(belongs_to_station_id=node_id, station_slot=sensor_slot).first().id
            ).first().calibration_value
        except:
            pass

def get_model_id_of_sensor_of_node(node_id, sensor_slot):
    with app.app_context():
        try:
            return Sensor.query.filter_by(belongs_to_station_id=node_id, station_slot=sensor_slot).first().sensor_model_id
        except:
            pass