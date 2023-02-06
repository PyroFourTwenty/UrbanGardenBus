python_client_code_template ="""from GardenBusClient.sensor import GardenBusSensor
from GardenBusClient.client import GardenBusClient
import can
{% for sensor in sensors %}
def get_value_for_{{sensor.sensor_name_in_snakecase}}():
    return 123.4 #replace '123.4' with your sensor reading

{% if sensor.needs_calibration %}def apply_calibration_value_for_{{sensor.sensor_name_in_snakecase}}(value, calibration_value):
    value += calibration_value
    # you can do further value processing here
    # i.e. you can convert a value reading to a percentage using this 
    return value
{% endif %}{% endfor %}
if __name__=='__main__':
    client = GardenBusClient(
        # this example utilizes the virtual canbus
        bus=can.interface.Bus('test', bustype='virtual'),
        # the id of the node, has to be unique, values can be (including) 1 and 65535
        node_id={{station_id}},
        tick_rate=30.0,  # specifies the seconds between "alive" packets; defaults to 30.0
        # if set to True, the client starts the (blocking) loop; defaults to True
        start_looping=True,
        print_tick_rate=True  # prints the tick rate in constructor; defaults to True
    )

    client.send_entry_packet()
    {% for sensor in sensors %}
    {{sensor.sensor_name_in_snakecase}} = GardenBusSensor(
        sensor_model_id = {{sensor.model_id}},
        get_value_function=get_value_for_{{sensor.sensor_name_in_snakecase}}{% if sensor.needs_calibration %},
        calibration_function=apply_calibration_value_for_{{sensor.sensor_name_in_snakecase}}
    {% endif %})

    register_success = client.register_sensor(
        sensor = {{sensor.sensor_name_in_snakecase}},
        slot = {{sensor.slot}},
        resend_count = 6,
        response_timeout = 30
    )
    calibration_success = client.calibrate_sensor({{sensor.sensor_name_in_snakecase}},{{sensor.slot}})  
    {%endfor%}
    """

ttn_payload_formatter_template = """
        function decodeUplink(input) {
            return {
                data: {
                    {% for element in elements %}
                    "{{element}}": bytesToFloat(input.bytes.slice({{loop.index0*4}}, {{loop.index0*4+4}})).toFixed(2),
                    {% endfor %}

                },
            warnings: [],
            errors: []
            };
        }
        function bytesToFloat(bytes) {
            //https://stackoverflow.com/a/37471538
            // JavaScript bitwise operators yield a 32 bits integer, not a float.
            // Assume LSB (least significant byte first).
            var bits = bytes[3]<<24 | bytes[2]<<16 | bytes[1]<<8 | bytes[0];
            var sign = (bits>>>31 === 0) ? 1.0 : -1.0;
            var e = bits>>>23 & 0xff;
            var m = (e === 0) ? (bits & 0x7fffff)<<1 : (bits & 0x7fffff) | 0x800000;
            var f = sign * m * Math.pow(2, e - 150);
            return f;
        }
    """
