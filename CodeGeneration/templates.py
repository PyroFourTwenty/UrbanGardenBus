lora32_code_template = """
#include <Arduino.h>
#include <UrbanGardenBusClient/UrbanGardenBusClient.h>
#include <UrbanGardenBusClient/UrbanGardenBusConfig.h>

UrbanGardenBusClient client;

// lorawan specific stuff
static const u1_t PROGMEM APPEUI[8] = { {{ttn_data["join_eui"]}} }; // this is in little endian format
static const u1_t PROGMEM DEVEUI[8] = { {{ttn_data["dev_eui"]}} }; // this is in little endian format
static const u1_t PROGMEM APPKEY[16] = { {{ttn_data["app_key"]}} };
void os_getArtEui (u1_t* buf) { memcpy_P(buf, APPEUI, 8);}
void os_getDevEui (u1_t* buf) { memcpy_P(buf, DEVEUI, 8);}
void os_getDevKey (u1_t* buf) {  memcpy_P(buf, APPKEY, 16);}

// pass any LoRaWAN to our UrbanGardenBusClient object  
void onEvent(ev_t ev){
  client.onEvent(ev);
}
{% for sensor in sensors %}
// get value function for {{sensor.sensor_name_in_camelcase}} on slot {{sensor.slot}}
float getValueFor{{sensor.sensor_name_in_camelcase_first_letter_cap}}OnSlot{{sensor.slot}}(){
  // read your sensor here 
  return 420.0; // replace this value with your sensor reading
}
{% if sensor.needs_calibration %}
float applyCalibrationValueFor{{sensor.sensor_name_in_camelcase_first_letter_cap}}OnSlot{{sensor.slot}}(float value, float calibrationValue){
  // apply your calibration value to your sensor reading here
  // value is the raw value that we got from our sensor
  // calibrationValue is the value we calibrated our sensor with
  // as an example you can subtract the calibration value from 
  // the sensor reading and return it like this:
  return value - calibrationValue;
}{% endif %}{% endfor %}
void setup() {
  Serial.begin(9600);
  while (!Serial);
  Serial.println("Running GardenBusClient (LoRa32 version)");
  client = UrbanGardenBusClient(
    {{station_id}}, // your individual node id, don't change it!
    30000 // tick rate in milliseconds
  ); //initialize the UrbanGardenBusClient
  
  {% for sensor in sensors %}
  UrbanGardenSensor {{sensor.sensor_name_in_camelcase}}OnSlot{{sensor.slot}};
  {{sensor.sensor_name_in_camelcase}}OnSlot{{sensor.slot}}.slot={{sensor.slot}};
  {{sensor.sensor_name_in_camelcase}}OnSlot{{sensor.slot}}.sensorModelId = {{sensor.model_id}};
  {{sensor.sensor_name_in_camelcase}}OnSlot{{sensor.slot}}.getValueFunction = getValueFor{{sensor.sensor_name_in_camelcase_first_letter_cap}}OnSlot{{sensor.slot}};
  {%if sensor.needs_calibration%}
  // one way to apply a (hardcoded) calibration value for a sensor:
  {{sensor.sensor_name_in_camelcase}}OnSlot{{sensor.slot}}.calibrationValue = {{sensor.calibration_value}};
  {{sensor.sensor_name_in_camelcase}}OnSlot{{sensor.slot}}.needsCalibration=true;
  {{sensor.sensor_name_in_camelcase}}OnSlot{{sensor.slot}}.applyCalibrationFunction = applyCalibrationValueFor{{sensor.sensor_name_in_camelcase_first_letter_cap}}OnSlot{{sensor.slot}};
  
  {%endif%}
  Serial.print("Registering {{sensor.sensor_name_in_camelcase}}OnSlot{{sensor.slot}}: ");
  if (client.registerSensor({{sensor.sensor_name_in_camelcase}}OnSlot{{sensor.slot}},20)){
    Serial.println("success");
  }else{
    Serial.println("failed");
  }
  {%if sensor.needs_calibration%}
  // or for dynamically requesting a calibration value that is saved at the headstation:
  client.requestCalibrationForSensor({{sensor.sensor_name_in_camelcase}}OnSlot{{sensor.slot}}, 20);{%endif%}{% endfor %}
}

void loop() {
  client.do_loop();   
}"""


python_client_code_template ="""from GardenBusClient.sensor import GardenBusSensor
from GardenBusClient.client import GardenBusClient
import can
{% for sensor in sensors %}
def get_value_for_{{sensor.sensor_name_in_snakecase}}_on_slot_{{sensor.slot}}():
    return 123.4 #replace '123.4' with your sensor reading

{% if sensor.needs_calibration %}def apply_calibration_value_for_{{sensor.sensor_name_in_snakecase}}_on_slot_{{sensor.slot}}(value, calibration_value):
    value += calibration_value
    # you can do further value processing here
    # i.e. you can convert a value reading to a percentage using this 
    return value
{% endif %}{% endfor %}
if __name__=='__main__':
    client = GardenBusClient(
        # this example utilizes the virtual canbus
        bus=can.interface.Bus('test', bustype='virtual'),
        node_id={{station_id}},
        ttn_dev_eui='{{ttn_data["dev_eui"]}}', 
        ttn_dev_id='{{ttn_data["dev_id"]}}', 
        ttn_app_key='{{ttn_data["app_key"]}}', 
        ttn_join_eui='{{ttn_data["join_eui"]}}',
        tick_rate=30.0,  # specifies the seconds between "alive" packets; defaults to 30.0
        # if set to True, the client starts the (blocking) loop; defaults to True
        start_looping=False,
        print_tick_rate=True  # prints the tick rate in constructor; defaults to True,

    )

    client.send_entry_packet()
    {% for sensor in sensors %}
    {{sensor.sensor_name_in_snakecase}}_on_slot_{{sensor.slot}} = GardenBusSensor(
        sensor_model_id = {{sensor.model_id}},
        get_value_function=get_value_for_{{sensor.sensor_name_in_snakecase}}_on_slot_{{sensor.slot}}{% if sensor.needs_calibration %},
        calibration_function=apply_calibration_value_for_{{sensor.sensor_name_in_snakecase}}_on_slot_{{sensor.slot}}
    {% endif %})

    register_success = client.register_sensor(
        sensor = {{sensor.sensor_name_in_snakecase}}_on_slot_{{sensor.slot}},
        slot = {{sensor.slot}},
        resend_count = 6,
        response_timeout = 30
    ){%if sensor.needs_calibration %}
    calibration_success = client.calibrate_sensor({{sensor.sensor_name_in_snakecase}}_on_slot_{{sensor.slot}},{{sensor.slot}})  
    {% endif %}
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


