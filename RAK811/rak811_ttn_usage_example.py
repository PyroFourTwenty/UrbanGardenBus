if __name__=='__main__':
    from rak811_control import RAK811

    import numpy as np
    import requests
        
    def get_value_as_hex(value):
        return np.float32(value).tobytes().hex()
    
    def get_temperature_as_hex():
        try:
            temperature = requests.get("https://api.open-meteo.com/v1/forecast?latitude=52.52&longitude=13.41&current_weather=true").json()["current_weather"]["temperature"]
            return get_value_as_hex(temperature)
        except:
            return get_value_as_hex(-20)

    rak811 = RAK811('/dev/ttyUSB0')
    
    rak811.send_lorawan_message(message="1234",
            region='EU868',
            app_eui='app-eui-here', 
            app_key='app-key-here',
            dev_eui='dev-eui-here'
    )

    rak811.print_response(return_on_ok=True, time_to_read=60)