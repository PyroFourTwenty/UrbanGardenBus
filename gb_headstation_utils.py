from GardenBusClient.SupportedSensors import supported_sensors
import struct
from flask_app import app
from flask_sqlalchemy import SQLAlchemy
from models import Station, Sensor, CalibrationValueForSensor, SetActorValue

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

def get_ttn_data_from_db_for_node(node_id):
    with app.app_context():
        try:
            station = Station.query.filter_by(id=node_id).first() 
            ttn_data = {
                "app_eui" : station.ttn_enddevice_join_eui,
                "app_key" : station.ttn_enddevice_app_key,
                "dev_eui" : station.ttn_enddevice_dev_eui 
            }
            return ttn_data
        except:
            pass

def get_all_set_actor_values_from_db():
    with app.app_context():
        all_set_actor_values_list = []
        try:
            all_set_actor_values = SetActorValue.query.all()
            for set_actor_value in all_set_actor_values:
                all_set_actor_values_list.append({
                    "belongs_to_station_id": set_actor_value.belongs_to_station_id,
                    "station_slot": set_actor_value.station_slot,
                    "actor_value": set_actor_value.actor_value
                })
        except:
            pass
        return all_set_actor_values_list

def delete_set_actor_value_from_db(node_id, station_slot, actor_value):
    with app.app_context():
        try:
            delete_set_actor_value = SetActorValue.__table__.delete().where(SetActorValue.belongs_to_station_id==node_id,SetActorValue.station_slot==station_slot,SetActorValue.actor_value==actor_value)
            db.session.execute(delete_set_actor_value)
            db.session.commit()
        except Exception as e:

            print("Something went wrong while deleting SetActorValue for node {node} on actor slot {slot}".format(node=node_id,slot=station_slot))
            print(e)

def get_model_id_of_sensor_of_node(node_id, sensor_slot):
    with app.app_context():
        try:
            return Sensor.query.filter_by(belongs_to_station_id=node_id, station_slot=sensor_slot).first().sensor_model_id
        except:
            pass