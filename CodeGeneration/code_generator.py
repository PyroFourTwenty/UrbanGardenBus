from jinja2 import Template
from .templates import python_client_code_template, ttn_payload_formatter_template

class CodeGenerator():
    def get_python_client_code(sensors, station_id):
        s = python_client_code_template 
        return Template(s).render(sensors=sensors, station_id=station_id)

    def get_ttn_payload_formatter_code(osem_sensor_ids):
        s = ttn_payload_formatter_template
        return Template(s).render(elements=osem_sensor_ids)