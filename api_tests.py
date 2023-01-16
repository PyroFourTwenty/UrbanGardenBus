import requests
import json
import random
import jinja2
from ApiAccess.OsemAccess import OsemAccess
from ApiAccess.TtnAccess import TtnAccess


def do_process():
    ttn_full_acc_key ="full-acc-key-here"
    ttn_username = 'ttn-username-here'
    osem_mail = "osem-mail-here"
    osem_pw = "osem-pw-here"    
    s = """
        function decodeUplink(input) {
            return {
                data: {
                    {% for element in elements %}
                    "{{element}}": bytesToFloat(input.bytes.slice({{loop.index0*4}}, {{loop.index0*4+3}})).toFixed(2),
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

    ttn = TtnAccess(full_account_key=ttn_full_acc_key,
        username=ttn_username
    )
    app_id = "delete-me"+str(random.randint(0,999))
    print('creating new app:',ttn.create_new_ttn_app(app_id=app_id,app_description="nothing interesting to see here i guess", app_name="a whole new world"))
    dev_eui = ttn.generate_random_dev_eui()
    dev_id = "a-python-created-device"+str(random.randint(0,999))
    while(ttn.create_new_ttn_enddevice(join_eui="1111111111111111", dev_eui=dev_eui, dev_id=dev_id, app_id=app_id)!=200):
        print('creating enddevice ',dev_id)
        dev_eui = ttn.generate_random_dev_eui()
        #print('creating new enddevice',ttn.create_new_ttn_enddevice(join_eui="1111111111111111", dev_eui=dev_eui, dev_id=dev_id, app_id=app_id))
    print('created enddevice ',dev_id)
    
    
    
    osem_access = OsemAccess(osem_mail,osem_pw)
    list_of_senseboxes = osem_access.get_available_senseboxes()

    name_of_new_sensebox = app_id
    
    if not name_of_new_sensebox in [names_list[0] for names_list in list_of_senseboxes]:
        post_result = osem_access.post_new_sensebox(name_of_new_sensebox, dev_id , app_id)
        if post_result[0] == 201:
            print('Posted new sensebox ', name_of_new_sensebox, 'and got sensebox-id',post_result[1])
            put_sensor_result = osem_access.put_new_sensor(
                sensebox_id=str(post_result[1]),
                icon='', 
                phenomenon='temperatur',
                sensor_type='DHT22',
                unit='°C')
            if put_sensor_result[0]==200:
                
                put_sensor_result = osem_access.put_new_sensor(
                    sensebox_id=str(post_result[1]),
                    icon='', 
                    phenomenon='feuchtigkeit',
                    sensor_type='DHT22',
                    unit='%')
                if put_sensor_result[0]==200:
            

                    print("Put new sensor and got id", put_sensor_result[1])
                    sensor_ids = osem_access.get_sensor_ids_of_sensebox(sensebox_id= post_result[1])
                    ttn.create_new_ttn_enddevice_formatter(dev_id=dev_id, payload_formatter_js=jinja2.Template(s).render(elements=sensor_ids), application_id=app_id)
                    #print('deleting created enddevice',ttn.delete_ttn_enddevice_from_app(app_id=app_id, dev_id=dev_id))
                    #print('deleting created ttn app',ttn.delete_ttn_app(app_id=app_id))

            else:
                print('Failed to put new sensor with status code', put_sensor_result[0])

        else:
            print('Could not post new sensebox: ', post_result[0])
    else:
        print('Sensebox with name', name_of_new_sensebox, 'already exists')

if __name__ == '__main__':

    do_process()
