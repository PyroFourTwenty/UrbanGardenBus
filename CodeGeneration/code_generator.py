from jinja2 import Template
from .templates import python_client_code_template, ttn_payload_formatter_template, lora32_code_template

class CodeGenerator():
    def get_python_client_code(sensors, station_id, ttn_data):
        s = python_client_code_template 
        return Template(s).render(sensors=sensors, station_id=station_id, ttn_data=ttn_data)

    def get_ttn_payload_formatter_code(osem_sensor_ids):
        s = ttn_payload_formatter_template
        return Template(s).render(elements=osem_sensor_ids)
    
    def get_lora32_client_code(sensors, station_id, ttn_data):
        s = lora32_code_template
        return Template(s).render(sensors=sensors, station_id=station_id, ttn_data=ttn_data)