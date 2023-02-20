from GardenBusClient.SupportedSensors import supported_sensors


def number_to_bytes(number_ : int, number_of_bytes : int = 1, print_to_console:bool= False):
    binary_node_id = bin(number_).replace("0b","")
    leading_zeros = "0" * (number_of_bytes*8-len(binary_node_id))
    
    stuffed = leading_zeros+binary_node_id
    if print_to_console:
        print(stuffed)
    return ([int(stuffed[i:i+8],2) for i in range(0, len(stuffed), 8)])

def get_sensor_key_by_id(sensor_id:int):
    sensors = supported_sensors.sensors
    for sensor in sensors:
        if sensors[sensor]['id']==sensor_id: #if the value corresponding to the key we are holding has the id we are looking for
            return sensor # return the key of the sensor
    #returns None if no sensor could be found with the searched id

def get_tags_for_supported_sensor(sensor_model_id:int):
    sensor_name_from_id = get_sensor_key_by_id(sensor_model_id)
    tags_from_supported_sensors = supported_sensors.sensors[sensor_name_from_id]["tags"]
    return tags_from_supported_sensors

def get_calibration_needed_for_supported_sensor(sensor_model_id):
    return supported_sensors.sensors[get_sensor_key_by_id(sensor_model_id)]["calibration_needed"] 

def bytes_to_number(bytes:list):
    return int.from_bytes(bytearray(bytes),"big")

def byte_to_number(byte):
    return bytes_to_number([byte])
