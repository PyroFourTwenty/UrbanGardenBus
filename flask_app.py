from flask import Flask, render_template, redirect, url_for, request, Response
from flask_login import login_user, LoginManager, login_required, logout_user, current_user
from forms import LoginForm, RegisterForm, CreateNewStation, AddNewSensorToStation, CreateNewSensorModelForm
from models import User, Station, Sensor, SensorModel, CalibrationValueForSensor
from database import db
from flask_bcrypt import Bcrypt
import folium
from folium.features import ClickForLatLng, ClickForMarker, LatLngPopup
from ApiAccess.OsemAccess import OsemAccess
from ApiAccess.TtnAccess import TtnAccess
import json
from werkzeug.exceptions import BadRequestKeyError
from jinja2 import Template
import requests

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
bcrypt = Bcrypt(app)

app.config['SECRET_KEY'] = 'thisisasecret'
db.init_app(app)
with app.app_context():
    db.create_all()

osem_access = None
ttn_access = None
ttn_app_id = "dev-ubg-app"
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

with app.app_context():
    db.create_all()

@app.route('/favicon.ico')
def favicon():
    return redirect("http://www.htw-berlin.de/templates/htw/images/favicon.ico")

@app.route('/')
def home():
    if current_user.is_authenticated:
        redirect(url_for('dashboard'))
    return render_template('home.html')

@app.route('/aerial')
def aerial():
    return render_template('aerial.html')

@app.route('/map')
def map():
    start_coords = (52.456463,13.52339)
    folium_map = folium.Map(location=start_coords, zoom_start=14, max_zoom=25)
    #tile = folium.TileLayer(
    #    tiles = 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    #    attr = 'Esri',
    #    name = 'Esri Satellite',
    #    overlay = False,
    #    control = True
    #   ).add_to(folium_map)
    click_for_lat_lng =  ClickForLatLng()
    click_for_lat_lng._template = Template(u"""
            {% macro script(this, kwargs) %}
                function getLatLng(e){
                    var lat = e.latlng.lat.toFixed(6);
                    var lng = e.latlng.lng.toFixed(6);
                    window.parent.parent.document.getElementById("latitude").value=lat;
                    window.parent.parent.document.getElementById("longitude").value=lng;
                    {% if this.alert %}return false{% endif %}
                    };
                {{this._parent.get_name()}}.on('click', getLatLng);
                {{this._parent.get_name()}}.on('touchstart', getLatLng);
            {% endmacro %}
            """)  
    folium_map.add_child(click_for_lat_lng)
    all_stations = Station.query.filter().all()

    for station in all_stations:
        folium.Marker(
            location=[station.latitude, station.longitude],
#            popup='''<i><a onclick='window.location.href("'''+url_for('update_station',id=station.id)+'''")>'''+station.station_name+"</a></i>"
            popup="""<i><p onclick="window.parent.parent.location.replace('"""+url_for('update_station',id=station.id)+"""')">"""+ station.station_name +"""</p></i>"""
            #popup='<a onclick="'+url_for('update_station',id=station.id)+'">asdasd</a>'
            
        ).add_to(folium_map)

    return folium_map._repr_html_()

@app.route('/login', methods=['GET','POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user:
            if bcrypt.check_password_hash(user.password, form.password.data):
                login_user(user)
                return redirect(url_for('dashboard'))
    return render_template('login.html',form=form)


@app.route('/dashboard',methods=['GET','POST'])
@login_required
def dashboard():
    current_user_id = User.query.filter_by(username=current_user.username).first().id
    data = []
    for station in Station.query.filter_by(belongs_to_user_id=current_user_id):
        if station.osem_sensebox_id:
            request = "https://api.opensensemap.org/boxes/{sensebox_id}".format(sensebox_id=station.osem_sensebox_id)
            json_response = requests.get(request).json()
            data.append(json_response)
    return render_template('dashboard.html',username=current_user.username, data=data)

@app.route('/stations',methods=['GET','POST'])
@login_required
def stations():
    form = CreateNewStation(latitude=52.454659, longitude=13.526368, height=36.0)
    current_user_id = User.query.filter_by(username=current_user.username).first().id
    if form.validate_on_submit():
        print('user', current_user.username,'wants to submit a new station called', form.station_name.data )
        dev_eui = ttn_access.generate_random_dev_eui()
        dev_id = str(form.station_name.data).replace(" ","-").lower()+ttn_access.generate_random_dev_eui(4)
        app_key = ttn_access.generate_random_dev_eui(16)
        join_eui = '1111111111111111'
        name_of_new_sensebox = form.station_name.data
        ttn_status_tuple = ttn_access.create_new_ttn_enddevice(join_eui=join_eui, dev_eui=dev_eui, dev_id=dev_id, app_id=ttn_app_id, app_key=app_key)
        print("creating new enddevice status code:",ttn_status_tuple)
        if ttn_status_tuple[0]==200 and ttn_status_tuple[1]==200 and ttn_status_tuple[2]==200 and ttn_status_tuple[3]==200:
            osem_status_tuple = osem_access.post_new_sensebox(name_of_new_sensebox, 
                dev_id, 
                ttn_app_id,
                lat=form.latitude.data,
                lng=form.longitude.data,
                height=form.height.data)
            print("creating new sensebox status code:", osem_status_tuple)

            if osem_status_tuple[0]==201:
                osem_sensebox_id = osem_status_tuple[1]

                new_station = Station(station_name=form.station_name.data,
                    belongs_to_user_id = current_user_id,
                    latitude=form.latitude.data,
                    longitude=form.longitude.data,
                    height=form.height.data,
                    ttn_enddevice_dev_eui = dev_eui,
                    ttn_enddevice_dev_id = dev_id,
                    ttn_enddevice_app_key = app_key,
                    ttn_enddevice_join_eui= join_eui,
                    osem_sensebox_id = osem_sensebox_id
                )
            
                db.session.add(new_station)
                db.session.commit()


        return redirect(url_for('stations'))
    user_dict = {}
    
    own_stations = Station.query.filter_by(belongs_to_user_id=current_user_id)
    other_stations = Station.query.filter(Station.belongs_to_user_id!=current_user_id)
    sensor_count_of_stations = {}
    for sensor in Sensor.query.all():
        if not sensor.belongs_to_station_id in sensor_count_of_stations:
            sensor_count_of_stations[sensor.belongs_to_station_id]= {
                "count":1
            } 
        else:
            sensor_count_of_stations[sensor.belongs_to_station_id]["count"] += 1
    for station in other_stations:
        user = User.query.filter_by(id=station.belongs_to_user_id).first()
        if not user.id in user_dict:
            user_dict[user.id] = user.username
    return render_template('stations.html',
                            form=form, 
                            own_stations=own_stations, 
                            other_stations=other_stations, 
                            user_dict=user_dict,
                            sensor_count_of_stations=sensor_count_of_stations)


@app.route('/sensormodel',methods=['GET','POST'])
@login_required
def sensor_model():
    form = CreateNewSensorModelForm()
    if form.validate_on_submit():
        sensor_model_from_db = SensorModel.query.filter_by(model_name=form.model_name.data, phenomenon_name=form.phenomenon_name.data,unit_name=form.unit_name.data).first()
        if sensor_model_from_db:
            print("sensor model combination already exists!")
            return redirect(url_for("sensor_model"))
        else:
            print("Sensor model is new or different")
        new_sensor_model = SensorModel(model_name=form.model_name.data, 
            phenomenon_name=form.phenomenon_name.data,
            unit_name=form.unit_name.data,
            calibration_needed=form.calibration_needed.data)
        db.session.add(new_sensor_model)
        db.session.commit()
        return redirect(url_for("sensor_model"))
    
    available_sensors=[]

    for sensor_model in SensorModel.query.all():
        available_sensors.append({
            "id": sensor_model.id,
            "model_name" : sensor_model.model_name,
            "phenomenon_name": sensor_model.phenomenon_name,
            "unit_name": sensor_model.unit_name,
            "calibration_needed": sensor_model.calibration_needed
            }
        )  

    return render_template('sensor_model_creation.html',form=form, available_sensors=available_sensors)

@app.route('/station/<id>',methods=['GET','POST'])
@login_required
def update_station(id,extend_collapsible=True):
    station = Station.query.filter_by(id=id).first()
    if not station:
        return Response('Station does not exist', status=404)
    station_belongs_to_current_user=User.query.filter_by(username=current_user.username).first().id == station.belongs_to_user_id
    if station_belongs_to_current_user:
        form = CreateNewStation(obj=station)
        if form.validate_on_submit():
            Station.query.filter_by(id=id).update({
                'station_name':form.station_name.data,
                'latitude':form.latitude.data,
                'longitude':form.longitude.data,
                'height': form.height.data
            })

            db.session.commit()
            #sensors = Sensor.query.filter_by(belongs_to_station_id = id).all()
            #sensors = list(['asd1', 'asd2', 'asd3', 'asd4'])
        available_sensors = []
        for sensor_model in SensorModel.query.all():
            available_sensors.append((sensor_model.id, sensor_model.model_name))
        
        sensor_form = AddNewSensorToStation()
        sensor_form.sensor_type.choices = available_sensors
        
        
        sensors_of_station_from_db = Sensor.query.filter_by(belongs_to_station_id = id).all()
        ttn_data= {
            "dev_eui": station.ttn_enddevice_dev_eui,
            "dev_id" : station.ttn_enddevice_dev_id,
            "app_key" : station.ttn_enddevice_app_key,
            "join_eui" : station.ttn_enddevice_join_eui
        }
        osem_data = {
            "sensebox_id": station.osem_sensebox_id
        }
        sensor_data_for_form = []
        for sensor in sensors_of_station_from_db:
            
            sensor_model = SensorModel.query.filter_by(id = sensor.sensor_model_id).first()
            sensor_model_name = sensor_model.model_name
            phenomenon = sensor_model.phenomenon_name
            calibration_value_row = CalibrationValueForSensor.query.filter_by(belongs_to_sensor_id=sensor.id).first()
            calibration_value_for_sensor = None
            if calibration_value_row:
                calibration_value_for_sensor = calibration_value_row.calibration_value
            data = {
                "sensor_id": sensor.id,
                "sensor_model_name": sensor_model_name,
                "sensor_slot": sensor.station_slot,
                "calibration_needed": sensor_model.calibration_needed,
                "phenomenon": phenomenon,
                "calibration_value": calibration_value_for_sensor
            }
            sensor_data_for_form.append(data)

        blocked_slots_for_station = []
        for sensor in Sensor.query.filter_by(belongs_to_station_id=id):
            blocked_slots_for_station.append(sensor.station_slot)
        
        python_code_example = get_python_code_example_for_station(station.id)
        
        return render_template('station_view.html',python_client_code = python_code_example,  form=form, ttn_data=ttn_data, osem_data=osem_data, station=station, sensor_form=sensor_form, sensors=sensor_data_for_form, blocked_slots_for_station=json.dumps(blocked_slots_for_station), extend_collapsible=json.dumps(extend_collapsible), map=map())
    else:
        return Response('not yours, sorry',status=403)

def get_python_code_example_for_station(station_id):
    sensors = []

    for sensor in Sensor.query.filter_by(belongs_to_station_id=station_id):
        sensor_model = SensorModel.query.filter_by(id=sensor.sensor_model_id).first()
        model_name_in_snakecase = str(sensor_model.model_name).lower().replace(" ", "_").replace("-","_")
        sensor_to_append = {
            "sensor_name_in_snakecase" : model_name_in_snakecase,
            "needs_calibration" : sensor_model.calibration_needed,
            "slot": sensor.station_slot,
            "model_id": sensor.sensor_model_id
        }
        sensors.append(sensor_to_append)
    
    s = """
from GardenBusClient.sensor import GardenBusSensor
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

    return Template(s).render(sensors=sensors, station_id=station_id)

@app.route('/sensor/calibrate/<sensor_id>', methods=['POST', 'PUT'])
@login_required
def calibrate_sensor(sensor_id):
    calibration_value = request.form['calibration_value']
    try:
        calibration_value = float(calibration_value)
    except ValueError:
        return Response("Sumbitted calibration value is not a number", status=400)

    calibration_value_from_db = CalibrationValueForSensor.query.filter_by(belongs_to_sensor_id=sensor_id).first()
    if calibration_value_from_db:
        CalibrationValueForSensor.query.filter_by(id=calibration_value_from_db.id).update({
            "calibration_value":calibration_value
        })
        db.session.commit()
        return Response("Calibration value has been updated", status=204)
    else:
        new_calibration_value_row = CalibrationValueForSensor(belongs_to_sensor_id=sensor_id,calibration_value=calibration_value)
        db.session.add(new_calibration_value_row)
        db.session.commit()
        return Response("Calibration value has been created", status=201)


@app.route('/station/delete/<id>', methods=['GET'])
@login_required
def delete_station(id):
    station_query = Station.query.filter_by(id=id)
    if not station_query.first():
        return Response('Station does not exist', status=404)
    station_belongs_to_current_user=User.query.filter_by(username=current_user.username).first().id == station_query.first().belongs_to_user_id
    if station_belongs_to_current_user:
        sensebox_id = station_query.first().osem_sensebox_id
        if osem_access.delete_sensebox(sensebox_id)==200:

            delete_sensors = Sensor.__table__.delete().where(Sensor.belongs_to_station_id==id)
            db.session.execute(delete_sensors)
            station_query.delete()
            db.session.commit()
        return redirect(url_for('stations'))
    else:
        return 'nope, not yours'

@app.route('/sensor/<station_id>', methods=['POST'])
@login_required
def add_sensor_to_station(station_id):
    sensor_model_id = request.form['sensor_type']
    slot = None
    try:
        slot = int(request.form['slot'])
    except (ValueError, BadRequestKeyError):
        return Response("No valid slot supplied", status=400)
    if slot<0 or slot>255:
        return Response("Invalid slot (0-255)", status=400)
    station_query = Station.query.filter_by(id=station_id)
    slot_occupied = Sensor.query.filter_by(belongs_to_station_id=station_id, station_slot=slot).first() != None
    if slot_occupied:
        return Response("Slot occupied", status=400)
    station_belongs_to_current_user=User.query.filter_by(username=current_user.username).first().id == station_query.first().belongs_to_user_id
    if station_belongs_to_current_user:
        sensebox_id = station_query.first().osem_sensebox_id
        sensor_model = SensorModel.query.filter_by(id=sensor_model_id).first()
        put_sensor_result = osem_access.put_new_sensor(
                sensebox_id=sensebox_id,
                icon='', 
                phenomenon=sensor_model.phenomenon_name,
                sensor_type=sensor_model.model_name,
                unit=sensor_model.unit_name)
        if put_sensor_result[0]==200:
            new_sensor = Sensor(
                belongs_to_station_id=station_id,
                sensor_model_id=sensor_model_id,
                station_slot=slot,
                osem_sensor_id = put_sensor_result[1]
            )
            db.session.add(new_sensor)
            db.session.commit()
            return redirect(url_for('update_station', id=station_id))
        else:
            return redirect(url_for('update_station', id=station_id))

    else:
        return Response("Station is not yours, sorry", status=403)

@app.route('/sensor/delete/<station_id>/<slot>', methods=['POST'])
@login_required
def delete_sensor(station_id, slot):
    station_query = Station.query.filter_by(id=station_id)
    station_belongs_to_current_user = None
    try:
        station_belongs_to_current_user=User.query.filter_by(username=current_user.username).first().id == station_query.first().belongs_to_user_id
    except:
        return Response("Station or sensor of that station does not exist", status=404)
    if station_belongs_to_current_user:
        sensor = Sensor.query.filter_by(belongs_to_station_id=station_id, station_slot=slot).first()
        if sensor:
            calibration_value_for_sensor = CalibrationValueForSensor.query.filter_by(belongs_to_sensor_id=sensor.id).first()
            if calibration_value_for_sensor:
                CalibrationValueForSensor.query.filter_by(belongs_to_sensor_id=sensor.id).delete()
            osem_sensebox_id_for_sensor = station_query.first().osem_sensebox_id
            osem_sensor_id_for_sensor = sensor.osem_sensor_id
            print('sensebox_id: ',osem_sensebox_id_for_sensor)
            print('sensor_id: ',osem_sensor_id_for_sensor)

            deletion = osem_access.delete_sensor(sensebox_id=osem_sensebox_id_for_sensor, sensor_id=osem_sensor_id_for_sensor)
            if deletion==200:
                db.session.query(Sensor).filter(Sensor.belongs_to_station_id==station_id, Sensor.station_slot==slot).delete()
                db.session.commit()
            return redirect(url_for('update_station', id=station_id))
        else:
            return Response("Sensor slot not found for this station", status=404)
    else:
        return Response('not yours, sorry', status=403)


@app.route('/register', methods=['GET','POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data)
        if User.query.filter_by(username=form.username.data).first():
            print("A user with this name already exists")
        new_user = User(username=form.username.data, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('register.html',form=form)


@app.route('/logout', methods=['GET','POST'])
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


if __name__ == '__main__':
    ttn_full_acc_key = ""
    ttn_username = ""
    osem_access = OsemAccess("", "")
    ttn_access = TtnAccess(full_account_key=ttn_full_acc_key,
        username=ttn_username
    )
    app.run(debug=True, host='0.0.0.0')