from GardenBusClient.SupportedSensors import supported_sensors
from . import gb_utils
class GardenBusSensor():
    sensor_name: str = None  #stores the model name of the sensor
    sensor_model_id: int = None #
    tags: list = None
    calibration_required = None
    calibration_value = None
    get_value_function = None 


    def __init__(self, sensor_model_id, 
            get_value_function, 
            tags: list = [],
            calibration_required = False,
            calibration_function = None,
            calibration_value: float = None,
            sensor_name: str = None):

        self.sensor_model_id = sensor_model_id

        self.tags = list(set(tags+gb_utils.get_tags_for_supported_sensor(sensor_model_id))) #append the tags from the file to the user defined tags
        self.calibration_required = calibration_required
        self.sensor_model_name = sensor_name
        self.get_value_function = get_value_function
        self.calibration_function = calibration_function
        self.calibration_value = calibration_value


    def apply_calibration(self, *args, calibration_value):
        return self.calibration_function(*args, calibration_value=calibration_value)

    def get_value(self,*args):
        if self.calibration_required:
            if not self.calibration_value is None:
                return self.apply_calibration(self.get_value_function(*args),calibration_value=self.calibration_value) 
            else:
                raise Exception("This sensor needs a calibration value prior to reading values")
        else:
            return self.get_value_function(*args)
