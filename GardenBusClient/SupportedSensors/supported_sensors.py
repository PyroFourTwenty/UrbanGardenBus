sensors = {
    "dht22_temperature":{
        "id" : 1,
        "model_name":"DHT22 Temperature",
        "calibration_needed": False,
        "tags" :[
            "temperature", "celsius"
        ]
    },
    "dht22_humidity":{
        "id":2,
        "model_name":"DHT22 Humidity",
        "calibration_needed": False,
        "tags" :[
            "humidity", "air", "percent"
        ]
    },
    "yl_69":{
        "id":3,
        "model_name":"YL 69 Soil Moisture",
        "calibration_needed": True,
        "tags" :[
            "soil", "moisture", "percent", "water"
        ]
    }
}