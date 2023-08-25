from flask import Flask, render_template, redirect, url_for, request, Response, flash
from flask_login import login_user, LoginManager, login_required, logout_user, current_user
from forms import LoginForm, RegisterForm, CreateNewStation, AddNewSensorToStation, CreateNewSensorModelForm, AddNewActorToStation, CreateNewPostForm, CreateNewCommentForm
from models import User, Station, Sensor, SensorModel, CalibrationValueForSensor, Actor, Post, Comment, PostReaction, SetActorValue
from CodeGeneration.code_generator import CodeGenerator
from database import db
from flask_bcrypt import Bcrypt
from ApiAccess.OsemAccess import OsemAccess
from ApiAccess.TtnAccess import TtnAccess
from ApiAccess.ApiAccessExceptions import NoInternetConnection, NotSignedIn, InvalidCredentials
import json
from werkzeug.exceptions import BadRequestKeyError
from jinja2 import Template
import requests
import re
import configparser
from datetime import datetime, timedelta
from PersistenceLayer.persistence import Persistence
from PersistenceLayer.mock_persistence import MockPersistence

import gardenbus_config

app = Flask(__name__) # initialize Flask app
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db' # path to the database location
bcrypt = Bcrypt(app) # initialize Bcrypt for hashing user passwords

app.config['SECRET_KEY'] = 'thisisasecret'
db.init_app(app)
with app.app_context(): # get the context of the Flask app
    db.create_all() # create all tables

osem_access : OsemAccess = None # declare object for accessing OpenSenseMap
ttn_access : TtnAccess = None # declare object for accessing TheThingsNetwork
ttn_app_id = "" # this is the name of your TheThingsNetwork application
login_manager = LoginManager() # initialize LoginManager object
login_manager.init_app(app) # connect LoginManager to the Flask app
login_manager.login_view = 'login' # tell LoginManager which route of the Flask app is used for loggin in
persistence_object: Persistence = None # declare the object for reading GardenBus packets 

@login_manager.user_loader
def load_user(user_id): 
    return User.query.get(int(user_id))

@app.route('/favicon.ico')
def favicon():
    return redirect("http://www.htw-berlin.de/templates/htw/images/favicon.ico")

@app.route('/')
def home():
    if current_user.is_authenticated: # if the login was successful
        redirect(url_for('dashboard')) # redirect the user to the dashboard
    return redirect(url_for('login')) # if the login was not successful, let the user login again

@app.route('/aerial')
def aerial(): # unused route (for now)
    return render_template('aerial.html')

@app.route('/map')
def map(): # unused route (for now)
    import folium
    from folium.features import ClickForLatLng, ClickForMarker, LatLngPopup
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
    form = LoginForm() # initialize the LoginForm object
    if form.validate_on_submit(): # if the login form is submitted and valid
        user = User.query.filter_by(username=form.username.data).first() # get the user row from the database
        if user: # if the user exists
            if bcrypt.check_password_hash(user.password, form.password.data): # if the generated password hash from the login form equals the hash stored in the database
                login_user(user) # tell LoginManager that the user is logged in
                return redirect(url_for('dashboard')) # redirect the user to the dashboard
    return render_template('login.html',form=form) # if the login form was not valid, redirect the user to the login page


@app.route('/dashboard',methods=['GET','POST'])
@login_required
def dashboard():
    ######################
    # In this route we have to collect data from the SQLite database as well as InfluxDB (using the Persistence object).
    # We have to
    # 1. find out which station(s) belongs to the user and when it sent the last "ALIVE" packet
    # 2. find out which sensor(s) belongs to the station(s) of the user and which value it/they sent
    # 3. collect all the posts in a descending order (timewise) and the comments of the post in an ascending order
    # 4. collect all reactions that belongs to every post
    ######################

    current_user_id = User.query.filter_by(username=current_user.username).first().id # get the id of the logged in user
    data = [] # init the list for the station data
    now = datetime.now() - timedelta(hours=1) # TODO is this time delta still necessary?
    for station in Station.query.filter_by(belongs_to_user_id=current_user_id): # get every station row that belongs to the current user
        last_alive_query = """
                from(bucket:"{table}") 
                |> range(start: -1d) 
                |> filter(fn: (r) => r._measurement == "{alive_packet_identifier}")
                |> filter(fn: (r) => r.node_id == "{station_id}")
                |> last()""".format(table=persistence_object.connection_data["table"],alive_packet_identifier=gardenbus_config.ALIVE_PACKET,station_id=station.id) # create the query for the last "ALIVE" packet that was caught by the headstation over the last day
        station_data = {
            'station_name': station.station_name,
            'station_id': station.id,
            'sensor_data':[]
        } # init the dictionary for the station data, that will be shown on the dashboard
        try:
            query_data = json.loads(persistence_object.query(last_alive_query)) # execute the InfluxDB query for the last "ALIVE" packet of the station
            if len(query_data)>0:
                seconds_ago = round((now - datetime.strptime(query_data[0]["_time"], "%Y-%m-%dT%H:%M:%S.%f+00:00")).total_seconds(),1) # format the time of the last "ALIVE" as a difference of time to now (in seconds)
                station_data['last_alive'] = seconds_ago # write the second difference in the station dictionary
        except Exception as e:
            print(e)
            pass # if any exception occurs here (ie. if no "ALIVE" packet was found for that station), just ignore it
        
        for sensor in Sensor.query.filter_by(belongs_to_station_id=station.id): # query every registered sensor of that station 
            sensor_model_data = SensorModel.query.filter_by(id=sensor.sensor_model_id).first() # get the sensor model row for that specific sensor            
            last_value_query = """
                from(bucket:"{table}") 
                |> range(start: -1d) 
                |> filter(fn: (r) => r._measurement == "{value_response_packet_identifier}")
                |> filter(fn: (r) => r.node_id == "{station_id}")
                |> filter(fn: (r) => r.sensor_slot == "{sensor_slot}")
                |> last()""".format(table=persistence_object.connection_data["table"],value_response_packet_identifier=gardenbus_config.VALUE_RESPONSE,station_id=station.id, sensor_slot=sensor.station_slot) # format the InfluxDB query for the last "VALUE_RESPONSE" packet caught by the headstation for that sensor
            sensor_data= {
                "model_name": sensor_model_data.model_name,
                "phenomenon": sensor_model_data.phenomenon_name,
                "unit": sensor_model_data.unit_name,
            } # create the sensor dictionary with all info
            try:
                query_data = json.loads(persistence_object.query(last_value_query)) # get the last "VALUE_REPONSE" from InfluxDB
                if len(query_data)>0:
                    sensor_data["last_value"] = round(query_data[0]["_value"],3) # round the sensor value and write it into our sensor data dictionary
                    sensor_data["seconds_ago"] = round((now - datetime.strptime(query_data[0]["_time"], "%Y-%m-%dT%H:%M:%S.%f+00:00")).total_seconds(),1) # write the time of the sensor value into our sensor data dictionary                
            except Exception as e:
                print(e)
                pass # if any exception occurs, just ignore it
            station_data["sensor_data"].append(sensor_data) # append the collected sensor data to our station data
        data.append(station_data) # append the collected station data (with the sensor data) to our data list 
    posts = [] # init the post list for the dashboard
    for post in Post.query.order_by(Post.created.desc()).all(): # iterate all posts (starting with the newest)
        posts.append({
            "id": post.id,
            "created": post.created,
            "author_name": User.query.filter_by(id=post.author_id).first().username,
            "header": post.header,
            "text": post.text,
            "comments": [],
            "reactions": {}
        }) # add the post specific data as a dictionary to the post list
        comments_of_post = Comment.query.filter_by(belongs_to_post_id=post.id).order_by(Comment.created.asc()).all() # get all comments of the iterated post (oldest comment first) 
        for comment in comments_of_post: # iterate over the comments of the post
            posts[-1]["comments"].append({
                "created": comment.created,
                "author_name": User.query.filter_by(id=comment.author_id).first().username,
                "text": comment.text,
                "id": comment.id
            }) # append the comment data to the last post of the list
        reactions_of_post = PostReaction.query.filter_by(belongs_to_post_id=post.id).all() # get all reactions of the iterated post
        for reaction in reactions_of_post:
            if reaction.reaction_type in posts[-1]["reactions"]:
                posts[-1]["reactions"][reaction.reaction_type] += 1 # if the reaction exists in the reactions dictionary, increase the count by one
            else:
                posts[-1]["reactions"][reaction.reaction_type] = 1 # if the reaction type is not in the dictionary, set the value to one

    return render_template('dashboard.html',username=current_user.username, data=data, posts=posts, comment_form=CreateNewCommentForm()) # return the dashboard with all the collected data

@app.route('/stations',methods=['GET','POST'])
@login_required
def stations():
    form = CreateNewStation(latitude=52.454659, longitude=13.526368, height=36.0) # initialize a new form object that lets the user create new stations
    current_user_id = User.query.filter_by(username=current_user.username).first().id # get the id of the current user 
    if form.validate_on_submit(): # if the user submitted the form and the entered data is valid
        print('user', current_user.username,'wants to submit a new station called', form.station_name.data )
        dev_eui = ttn_access.generate_random_dev_eui() # generate a new random DevEUI using our TtnAccess object
        dev_id = str(form.station_name.data).replace(" ","-").lower()+ttn_access.generate_random_dev_eui(4) # replace whitespaces with a dash and add 4 random characters
        # The 4 random characters are added to the DevID to make a commonly used dev_id usable with TTN. For example the station named "Test" can only be used once globally, but by adding
        # 4 random characters to the end, we can still use this id because it becomes a unique ID 
        app_key = ttn_access.generate_random_dev_eui(16) # use the same TtnAccess object to generate a random AppKey
        join_eui = '1111111111111111' # this is static, but can be anything (except "0000000000000000" because RAK modules do not accept an all zeroes JoinEUI), best practice would be to randomly generate this
        name_of_new_sensebox = form.station_name.data # get the name of the new sensebox from the form
        try:
            # try to create a new TTN enddevice using the data we generated (JoinEUI, DevEUI, DevID, AppID and AppKey) 
            # In order to create a new TTN enddevice, our TtnAccess object has to send several web requests. The status codes are collected and returned as a tuple.
            # If everything worked as expected, every entry in the tuple should be 200 (HTTP status code for OK) 
            ttn_status_tuple = ttn_access.create_new_ttn_enddevice(join_eui=join_eui, dev_eui=dev_eui, dev_id=dev_id, app_id=ttn_app_id, app_key=app_key)
            print("creating new enddevice status code:",ttn_status_tuple)
            if ttn_status_tuple[0]==200 and ttn_status_tuple[1]==200 and ttn_status_tuple[2]==200 and ttn_status_tuple[3]==200: # if everything worked as expected
                # the OsemAccess object works in a similar way, it also returns a tuple, but this tuple contains both the status code and the id of the new sensebox
                osem_status_tuple = osem_access.post_new_sensebox(name_of_new_sensebox, 
                    dev_id, 
                    ttn_app_id,
                    lat=form.latitude.data,
                    lng=form.longitude.data,
                    height=form.height.data) # pass the name and the TTN data to the OsemAccess object, which creates a new sensebox and establishes a connection between the sensebox and the TTN enddevice 
                
                print("creating new sensebox status code:", osem_status_tuple)

                if osem_status_tuple[0]==201: # if the OsemAccess object was able to create a new sensebox (HTTP status code 201 means "Created" and signals that a new resource was created on the server-side)
                    osem_sensebox_id = osem_status_tuple[1] # retrieve the sensebox id from the tuple that was returned by the OsemAccess object
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
                    ) # finally we can save all the data by creating a new station row in our database 
                    db.session.add(new_station) # add the new data row to the database
                    db.session.commit() # write changes to the database
                else:
                    flash("Error creating Sensebox") # if anything fails, tell the user
            else:
                flash("Error creating TTN enddevice, TTN does not like 'ä','ö','ü' or other special characters") # if anything fails, tell the user
        except NoInternetConnection:
            # well, no internet connection means we are not able to communicate with TTN or OpenSenseMap
            flash("Action currently not available, no internet connection")
        return redirect(url_for('stations')) # reload the stations page
    
    own_stations = Station.query.filter_by(belongs_to_user_id=current_user_id) # get all stations that are owned by the current user
    sensor_count_of_stations = {} # initialize a dicionary that counts how many sensors belong to every station
    for sensor in Sensor.query.all(): # iterate all sensors
        if not sensor.belongs_to_station_id in sensor_count_of_stations:
            sensor_count_of_stations[sensor.belongs_to_station_id]= {
                "count":1
            } # we found the first sensor of a station, so we set the count of that station to 1
        else:
            sensor_count_of_stations[sensor.belongs_to_station_id]["count"] += 1 # we found another sensor that belongs to the station, so we increase the count by 1
    return render_template('stations.html',
                            form=form, 
                            own_stations=own_stations, 
                            sensor_count_of_stations=sensor_count_of_stations) # return the data we collected and render the page


@app.route('/sensormodel',methods=['GET','POST'])
@login_required # of course you need to be logged in to create new sensormodels
def sensor_model():
    form = CreateNewSensorModelForm() # initialize a form that lets the user create new sensor models
    if form.validate_on_submit(): # if the form is submitted and contains valid data
        # check if a sensor model with the submitted data already exists in the database
        sensor_model_from_db = SensorModel.query.filter_by(model_name=form.model_name.data, phenomenon_name=form.phenomenon_name.data,unit_name=form.unit_name.data).first() 
        if sensor_model_from_db: # if that exact same sensor model already exists
            flash("sensor model combination already exists!") # tell the use
            return redirect(url_for("sensor_model")) # and reload the page
        else:
            print("Sensor model is new or different")
        new_sensor_model = SensorModel(model_name=form.model_name.data, 
            phenomenon_name=form.phenomenon_name.data,
            unit_name=form.unit_name.data,
            calibration_needed=form.calibration_needed.data) # create the new sensor model row
        db.session.add(new_sensor_model) # add the row to the database
        db.session.commit() # write the changes to the database 
        flash("Sensor model created")
        return redirect(url_for("sensor_model")) # reload the page
    
    available_sensors=[] # initialize a new list for all sensor models

    for sensor_model in SensorModel.query.all():
        available_sensors.append({
            "id": sensor_model.id,
            "model_name" : sensor_model.model_name,
            "phenomenon_name": sensor_model.phenomenon_name,
            "unit_name": sensor_model.unit_name,
            "calibration_needed": sensor_model.calibration_needed
            }
        )  # add the data to our list
    return render_template('sensor_model_creation.html',form=form, available_sensors=available_sensors) # render the page with all data and the form

@app.route('/station/<id>',methods=['GET','POST'])
@login_required # login is required so that we know which user has access to which stations
def update_station(id,extend_collapsible=True):
    # in this route we get a detailed overview of all data that belongs to a specific station
    station = Station.query.filter_by(id=id).first() # first we have to query our station by its id
    if not station: # if no station with that id was found
        flash('Station does not exist') # tell the user
        return redirect(url_for('stations')) # and redirect to the stations page
    
    station_belongs_to_current_user=User.query.filter_by(username=current_user.username).first().id == station.belongs_to_user_id # check if the user has the right to alter the station
    if station_belongs_to_current_user: # if the user is allowed to change the station
        form = CreateNewStation(obj=station) # initialize a form with the data of the station from the database
        if form.validate_on_submit(): # if the form is submitted and the entered data is valid
            Station.query.filter_by(id=id).update({
                'station_name':form.station_name.data,
                'latitude':form.latitude.data,
                'longitude':form.longitude.data,
                'height': form.height.data
            }) # change the row in the database according to the data from the form

            db.session.commit() # write the changes to the database
        available_sensors = [] # initialize a list to store our sensor models by their name
        for sensor_model in SensorModel.query.all(): # iterate over all sensor models
            available_sensors.append((sensor_model.id, sensor_model.model_name))  # add a tuple to the list that contains the id and the name of the iterated sensor model
        
        sensor_form = AddNewSensorToStation() # initialize a form that lets the user add new sensors to the station
        sensor_form.sensor_type.choices = available_sensors # add the collected sensor model names to the choices of that form
        
        actor_form = AddNewActorToStation() # initialize a form that lets the user add new actors to their station
        
        ttn_data= {
            "dev_eui": station.ttn_enddevice_dev_eui,
            "dev_id" : station.ttn_enddevice_dev_id,
            "app_key" : station.ttn_enddevice_app_key,
            "join_eui" : station.ttn_enddevice_join_eui
        } # prepare a dictionary that contains all TTN data for our station for later use when rendering the page
        osem_data = {
            "sensebox_id": station.osem_sensebox_id
        } # do the same for OSeM data
        sensor_data_for_form = [] # initialize a list that will contain every sensor with its data
        sensors_of_station_from_db = Sensor.query.filter_by(belongs_to_station_id = id).all() # get all sensors from the database that belong to our station
        blocked_sensor_slots_for_station = [] # initialize a list that lets us keep track of the used sensor slots

        for sensor in sensors_of_station_from_db: # iterate every sensor that belongs to the station            
            sensor_model = SensorModel.query.filter_by(id = sensor.sensor_model_id).first() # get the sensor model of the iterated sensor
            sensor_model_name = sensor_model.model_name # get the name of the sensor model
            phenomenon = sensor_model.phenomenon_name # get the observed phenomenon of that sensor model
            calibration_value_row = CalibrationValueForSensor.query.filter_by(belongs_to_sensor_id=sensor.id).first() # try to get the calibration value of that sensor
            calibration_value_for_sensor = None # initialize a variable for the calibration value of that sensor
            if calibration_value_row: # if theres a row that contains a calibration value for that sensor
                calibration_value_for_sensor = calibration_value_row.calibration_value # apply the value to our variable
            data = {
                "sensor_id": sensor.id,
                "sensor_model_name": sensor_model_name,
                "sensor_slot": sensor.station_slot,
                "calibration_needed": sensor_model.calibration_needed,
                "phenomenon": phenomenon,
                "calibration_value": calibration_value_for_sensor
            } # create a dictionary that contains all the relevant data for that sensor
            sensor_data_for_form.append(data) # append the data to our list
            blocked_sensor_slots_for_station.append(sensor.station_slot) # add the used sensor slot to the list with blocked slots

        actors_of_station_from_db = Actor.query.filter_by(belongs_to_station_id = id).all() # get all actors that belong to the station from the database
        actor_data_for_form = [] # initialize a list that contains all of the actors data
        blocked_actor_slots_for_station = [] # initialize a list that will help us keep track of all the used actor slots
        for actor in actors_of_station_from_db: # iterate all actors of the station
            data = {
                "actor_id": actor.id,
                "actor_name": actor.name,
                "actor_slot": actor.station_slot,
                "actor_value": actor.actor_value
            } # initialize a dictionary containing the data of the iterated actor
            actor_data_for_form.append(data) # add the actors data to our list
            blocked_actor_slots_for_station.append(actor.station_slot) # add the used actor slot to our list

        python_code_example = get_code_example_for_station(station.id, 'python',ttn_data, sensors_of_station_from_db) # generate the template python code for our station using the required TTN data  
        lora32_code_example = get_code_example_for_station(station.id, 'lora32',ttn_data, sensors_of_station_from_db) # do the same for the LoRa32 template code
        return render_template('station_view.html',
                                python_client_code = python_code_example,
                                lora32_client_code = lora32_code_example,
                                form=form, 
                                ttn_data=ttn_data, 
                                osem_data=osem_data, 
                                station=station, 
                                sensor_form=sensor_form,
                                actor_form=actor_form,
                                sensors=sensor_data_for_form, 
                                blocked_sensor_slots_for_station=json.dumps(blocked_sensor_slots_for_station), 
                                actors=actor_data_for_form,
                                blocked_actor_slots_for_station=json.dumps(blocked_actor_slots_for_station),
                                extend_collapsible=json.dumps(extend_collapsible), 
                                map=map()) # and finally return all the collected data and render the page
    else: # if the station does not belong to the user
        flash("Not your station, sorry") # tell the user
        return redirect(url_for("stations")) # and send them back to the station page

def get_model_name_in_camelcase(model_name):
    # This method converts a given word to camelcase. This is used when creating a station
    split_model_name = model_name.split(" ")
    camelcase_name = ""
    for word in split_model_name:
        if word!="":
            lower_word = list(word.lower())
            lower_word[0] = lower_word[0].upper()
        camelcase_name+="".join(lower_word)
    camelcase_name =  list(camelcase_name)
    camelcase_name[0]=camelcase_name[0].lower()
    camelcase_name="".join(list(camelcase_name))
    return camelcase_name

def convert_ttn_data_for_lora32_usage(ttn_data):
    # This method converts the TTN data from big endian to little endian and adds a '0x' in front of every value. This is needed when creating the LoRa32 code.
    ttn_data = {
            "dev_eui": ', '.join(['0x'+ value.upper() for value in re.findall('..',ttn_data['dev_eui'])[::-1]]), # reverse order for little endian and add '0x' in front of every value 
            "dev_id" : ', '.join(['0x'+ value.upper() for value in re.findall('..',ttn_data['dev_id'])]),
            "app_key" : ', '.join(['0x'+ value.upper() for value in re.findall('..',ttn_data['app_key'])]),
            "join_eui" : ', '.join(['0x'+ value.upper() for value in re.findall('..',ttn_data['join_eui'])[::-1]]), # reverse order for little endian and add '0x' in front of every value
        }
    return ttn_data

def get_code_example_for_station(station_id, client_type,ttn_data, sensors_of_station = None):
    # This method generates the code for a station (for Python- and Lora32-client). 
    # First we have to collect the neccessary data for our sensors. Because of different case styles ("snake_case" for Python vs "CamelCase" for C++),
    # we have to somehow convert the sensor model name to fit the specified code type. Furthermore, we have to make sure that the names dont contain characters, that might be problematic to the compiler (like Umlaute, dashes, whitespaces, underscores, etc).
    # These special characters have to be changed to something less problematic. 
    # Additionally, the TTN data has to be changed to "little endian", when we generate the code for our C++ (LoRa32) client.  
    # After all important data for these sensors has been collected, we pass a list of dicts to our CodeGenerator object, that uses Jinja2 to generate the code.
    sensors = [] # initialize the list that will hold our sensor data  
    if sensors_of_station is None: # if no sensor list has been passed to the function, get them from the database
        sensors_of_station = Sensor.query.filter_by(belongs_to_station_id=station_id) 
    for sensor in sensors_of_station: # iterate every sensor and convert the names to make them usable in the clientcode
        sensor_model = SensorModel.query.filter_by(id=sensor.sensor_model_id).first()
        model_name_in_snakecase = str(sensor_model.model_name).lower().replace(" ", "_").replace("-","_").replace("ä","ae").replace("ö","oe").replace("ü","ue").replace("ß","ss")
        model_name_in_camelcase = get_model_name_in_camelcase(sensor_model.model_name).replace("ä","ae").replace("ö","oe").replace("ü","ue").replace("ß","ss")
        model_name_in_camelcase_first_letter_cap = list(model_name_in_camelcase)
        model_name_in_camelcase_first_letter_cap[0]=model_name_in_camelcase_first_letter_cap[0].upper()
        model_name_in_camelcase_first_letter_cap = "".join(model_name_in_camelcase_first_letter_cap)
        calibration_value = None
        if sensor_model.calibration_needed: # if the sensormodel requires calibration, get the corresponding value from the database
            calibration_value = CalibrationValueForSensor.query.filter_by(belongs_to_sensor_id=sensor.id).first().calibration_value
        sensor_to_append = { # create a dictionary that contains the necessary data for the code generation
            "sensor_name_in_snakecase" : model_name_in_snakecase,
            "sensor_name_in_camelcase" : model_name_in_camelcase,
            "sensor_name_in_camelcase_first_letter_cap": model_name_in_camelcase_first_letter_cap,
            "needs_calibration" : sensor_model.calibration_needed,
            "calibration_value": calibration_value,
            "slot": sensor.station_slot,
            "model_id": sensor.sensor_model_id
        } 
        sensors.append(sensor_to_append) # append the collected data to our list
    if client_type=='python': 
        return CodeGenerator.get_python_client_code(sensors,station_id,ttn_data) # return the generated python code 
    elif client_type=='lora32':
        ttn_data=convert_ttn_data_for_lora32_usage(ttn_data) # change the order of the TTN data for LoRa32
        return CodeGenerator.get_lora32_client_code(sensors,station_id,ttn_data) # return the generated LoRa32 code

@app.route('/sensor/calibrate/<sensor_id>', methods=['POST', 'PUT'])
@login_required # of course, we can only calibrate a sensor that belongs to one of our own stations, so we need to be logged in
def calibrate_sensor(sensor_id):
    # This route lets the user store a calibration value for a sensor of a station in the database. 
    # TODO check if the sensor belongs to the user
    calibration_value = request.form['calibration_value'] # get the submitted value from the POST body
    try:
        calibration_value = float(calibration_value) # check if the value is actually valid
    except ValueError: # if the value cannot be cast to a float, it is considered invalid and a ValueError will be thrown 
        return Response("Sumbitted calibration value is not a number", status=400)

    calibration_value_from_db = CalibrationValueForSensor.query.filter_by(belongs_to_sensor_id=sensor_id).first() # get the calibration value from the database
    if calibration_value_from_db: # if a calibration value for that sensor exists, update it with the new value
        CalibrationValueForSensor.query.filter_by(id=calibration_value_from_db.id).update({ 
            "calibration_value":calibration_value
        })
        db.session.commit() # save changes to database
        return Response("Calibration value has been updated", status=204) # respond with status 204 
    else: # if no calibration value is present for that specific sensor
        new_calibration_value_row = CalibrationValueForSensor(belongs_to_sensor_id=sensor_id,calibration_value=calibration_value) # create a new databaserow for a calibration value 
        db.session.add(new_calibration_value_row) # add the row to the database
        db.session.commit() # save the changes to the database
        return Response("Calibration value has been created", status=201) # respond with status 201

@app.route('/actor/set/<station_id>/<actor_slot>', methods=['POST', 'PUT'])
@login_required
def set_actor_value(station_id, actor_slot):
    # this route lets the user set a desired value for an actor
    # TODO check if the actor belongs to the user
    actor_value = request.form['actor_value']
    try:
        actor_value = float(actor_value) # try to cast the value
    except ValueError: # if the value is not a float, a ValueError will be thrown
        return Response("Sumbitted actor value is not a number", status=400) # respond with status 400
    Actor.query.filter_by(belongs_to_station_id=station_id, station_slot=actor_slot).update({ # update the actor value in the database 
            "actor_value": actor_value
        })
    new_set_actor_value = SetActorValue(belongs_to_station_id=station_id, station_slot=actor_slot, actor_value=actor_value)
    db.session.add(new_set_actor_value)
    db.session.commit() # write changes to the database
    return Response("Calibration value has been updated", status=204) # respond with status 204

@app.route('/station/delete/<id>', methods=['GET'])
@login_required # login is required to check if station belongs to the user 
def delete_station(id):
    # This route lets a user delete a station (which belongs to them)
    station_query = Station.query.filter_by(id=id) # get the station by id
    if not station_query.first(): 
        return Response('Station does not exist', status=404) # respond with 404 if no station with that id was found in the database
    station_belongs_to_current_user=User.query.filter_by(username=current_user.username).first().id == station_query.first().belongs_to_user_id # check if the station belongs to the user
    if station_belongs_to_current_user: 
        # if the user has the right to delete the station, we have to delete the corresponding Sensebox and the TTN enddevice
        sensebox_id = station_query.first().osem_sensebox_id # get the sensebox id 
        if osem_access.delete_sensebox(sensebox_id)==200: # if the deletion of the sensebox was successful, we can proceed and delete the TTN enddevice
            ttn_enddevice_deletion = ttn_access.delete_ttn_enddevice_from_app(ttn_app_id, station_query.first().ttn_enddevice_dev_id) # delete the TTN enddevice
            if ttn_enddevice_deletion == 200: # if the deletion of the TTN enddevice was succesful, we can proceed and delete the sensors of the station from the database
                delete_sensors = Sensor.__table__.delete().where(Sensor.belongs_to_station_id==id) # delete all sensors that belong to the station
                db.session.execute(delete_sensors) 
                station_query.delete() # delete the station from the database
                db.session.commit() # write changes to database
        return redirect(url_for('stations')) # send the user back to the station webpage
    else:
        return 'nope, not yours' # tell the user that they cannot delete this station because it does not belong to them 

@app.route('/sensor/<station_id>', methods=['POST'])
@login_required 
def add_sensor_to_station(station_id):
    # This route lets the user add sensor to their stations
    try:
        sensor_model_id = request.form['sensor_type'] # get the sensor model from the POST body
    except BadRequestKeyError: # if no sensor type was supplied 
        return Response("Please provide a sensor type", status=400) # return a 400 status 
    slot = None 
    try:
        slot = int(request.form['sensor_slot']) # try to get the sensor slot from the POST body
    except (ValueError, BadRequestKeyError): # if no sensor slot was supplied or its not an integer
        return Response("No valid slot supplied", status=400) # return a 400 response
    if slot<0 or slot>255: # check if the slot is invalid
        return Response("Invalid slot (0-255 is valid)", status=400) # return a 400 response
    station_query = Station.query.filter_by(id=station_id) # get the station from the database
    slot_occupied = Sensor.query.filter_by(belongs_to_station_id=station_id, station_slot=slot).first() != None # check if the supplied slot is used by another sensor
    if slot_occupied:
        return Response("Slot occupied", status=400) # return a 400 response
    station_belongs_to_current_user=User.query.filter_by(username=current_user.username).first().id == station_query.first().belongs_to_user_id # check if the station belongs to the user
    if station_belongs_to_current_user:
        sensebox_id = station_query.first().osem_sensebox_id # get the sensebox id from the database
        # TODO check if the sensor model with sensor_model_id actually exists 
        sensor_model = SensorModel.query.filter_by(id=sensor_model_id).first() # get the sensor model from the database
        try:
            put_sensor_result = osem_access.put_new_sensor( 
                    sensebox_id=sensebox_id,
                    icon='', 
                    phenomenon=sensor_model.phenomenon_name,
                    sensor_type=sensor_model.model_name,
                    unit=sensor_model.unit_name) # try to create a new sensor for the sensebox in OSeM
            if put_sensor_result[0]==200: # if we successfully created a sensor for the sensebox, write a new sensor row to our database
                new_sensor = Sensor(
                    belongs_to_station_id=station_id,
                    sensor_model_id=sensor_model_id,
                    station_slot=slot,
                    osem_sensor_id = put_sensor_result[1] # put_sensor_result[1] is the sensor id we got from OSeM
                )
                db.session.add(new_sensor)
                if sensor_model.calibration_needed: # create a new calibration row for our sensor row
                    new_calibration_value = CalibrationValueForSensor(
                        belongs_to_sensor_id = new_sensor.id,
                        calibration_value=0.0 # default calibration value is 0.0
                    )
                    db.session.add(new_calibration_value)
                db.session.commit() # write changes to database
                update_payload_formatter_for_ttn_enddevice(station_id) # update the payload formatter in TTN
                flash("TTN payload formatter successfully updated") # tell the user everything worked
                return redirect(url_for('update_station', id=station_id)) # redirect the user
            else: # if the OSeM sensor was not be created  
                flash("OSeM sensor could not be created") # tell the user
                return redirect(url_for('update_station', id=station_id)) # redirect the user
        except NoInternetConnection: # if no internet connection exists
            flash("Action currently not available, no internet connection") # tell the user
            return redirect(url_for('update_station', id=station_id)) # redirect the user
    else: # if the station does not belong to the user
        flash("This station is not yours") # tell the user
        return redirect(url_for('update_station', id=station_id), code=403) # redirect the user

def update_payload_formatter_for_ttn_enddevice(station_id):
    # This function updates the payload formatter in TTN
    print("updating payload formatter for station", station_id)
    osem_sensor_ids = [] # initialize the list that will hold our OSeM sensor ids
    for sensor in Sensor.query.filter_by(belongs_to_station_id=station_id).order_by(Sensor.station_slot.asc()): # iterate the station sensors by ascending slot order
        osem_sensor_ids.append(sensor.osem_sensor_id) # append the OSeM sensor id to the list
    station = Station.query.filter_by(id=station_id).first() # get the station row from database
    status = ttn_access.create_new_ttn_enddevice_formatter( # use the TtnAccess object to create the new payload formatter
        dev_id=station.ttn_enddevice_dev_id, 
        payload_formatter_js=CodeGenerator.get_ttn_payload_formatter_code(osem_sensor_ids), # generate the JavaScript TTN payload formatter for the collected OSeM sensor ids 
        application_id=ttn_app_id            
    )
    print("status",status) 
    return status # return the status


@app.route('/actor/<station_id>', methods=['POST'])
@login_required # login is required to check if the station should be changed by the user
def add_actor_to_station(station_id):
    # This route lets the user add new actors to a station
    slot = None 
    try:
        slot = int(request.form['actor_slot']) # try to cast the supplied actor slot to an integer 
    except (ValueError, BadRequestKeyError): # if the slot cannot be cast to an integer or doesnt exist at all
        return Response("No valid slot supplied", status=400) # respond with status 400
    if slot<0 or slot>255: # check slot for invalid range 
        return Response("Invalid slot (0-255)", status=400) # respond with status 400
    station_query = Station.query.filter_by(id=station_id).first() # get station from database  
    slot_occupied = Actor.query.filter_by(belongs_to_station_id=station_id, station_slot=slot).first() != None # check if the slot is in use

    if slot_occupied:
        return Response("Slot occupied", status=400) # respond with 400 status
    station_belongs_to_current_user=User.query.filter_by(username=current_user.username).first().id == station_query.belongs_to_user_id # check if the station belongs to the user
    if station_belongs_to_current_user:
        # TODO check if actor name was supplied
        actor_name = request.form['actor_name'] # get the actor name from the POST body 
        new_actor = Actor(
            name =  actor_name,
            belongs_to_station_id = station_id,
            station_slot = slot,
            actor_value=0.0
        ) # create a new actor row
        db.session.add(new_actor) # add row to database
        db.session.commit() # write changes to database
        flash("New actor "+actor_name+" added") # tell the user the new actor was added
        return redirect(url_for('update_station', id=station_id)) # redirect user
    else: # if the station does not belong to the user
        return Response('not yours, sorry', status=403) # respond with 403 status    

@app.route('/actor/delete/<station_id>/<actor_slot>', methods=['POST'])
@login_required
def delete_actor(station_id, actor_slot):
    # This route lets users delete actors by station id and actor slot
    try:
        actor_from_db = Actor.query.filter_by(belongs_to_station_id=station_id, station_slot=actor_slot).first() # get the actor from database
        corresponding_station = Station.query.filter_by(id=station_id).first()  # find the station the actor belongs to
        station_belongs_to_current_user = User.query.filter_by(username=current_user.username).first().id == corresponding_station.belongs_to_user_id # check user privileges
        if station_belongs_to_current_user: # if the user has the right to delete the actor
            db.session.query(Actor).filter(Actor.id==actor_from_db.id).delete()  # delete it
            db.session.commit() # write changes to database
            flash("Actor successfully deleted") # tell the user the actor was deleted
        else:  # if the station does not belong to user
            return Response("not yours", status=403) # tell the user
    except: # TODO improve the exception handling by making the response more precise 
        return Response("Station or actor of that station does not exist", status=404) # if station or actor was not found, tell the user and send a 404 status
    return redirect(url_for('update_station', id=corresponding_station.id)) # if everything worked as expected, redirect the user

@app.route('/post/create', methods=['GET', 'POST'])
@login_required # login is required to retrieve information, which user wants to create a post
def create_post():
    # This route lets users create a new post. A post can contain an optional header and text  
    form = CreateNewPostForm() # initialize a formular for creating a new post
    if form.validate_on_submit(): # if the submitted post is valid 
        user_id = User.query.filter_by(username=current_user.username).first().id # get the user id by checking the name of the logged in user
        new_post = Post( # create a new post row
            created=datetime.utcnow(), # creation date as utc timestamp
            author_id=user_id, # author is the logged in user
            header=form.post_header.data, # get the header for the post from the formular
            text=form.post_text.data) # get the text content for the post from the formular
        db.session.add(new_post) # add the new post row to the database
        db.session.commit() # write changes to the database
        flash("Sucessfully posted") # tell the user the post was successfully created
        return redirect(url_for('dashboard')) # redirect the user to the dashboard
    return render_template('create_post.html', form=form) # if the method is GET, send the webpage with the initialized post formular


@app.route('/post/delete/<int:post_id>', methods=['GET'])
@login_required # login is required to check if the user is privileged to delete the specified post
def delete_post(post_id):
    # This route lets the user delete a post they created earlier
    post = Post.query.filter_by(id=post_id).first() # get the post row from database by post id
    if post: # if a post has been found in the database
        user_id = User.query.filter_by(username=current_user.username).first().id # get the user id of the current user 
        if user_id == post.author_id: # if the post has been created by the user
            db.session.query(Post).filter(Post.id==post.id).delete() # delete the post
            db.session.query(Comment).filter(Comment.belongs_to_post_id==post.id).delete() # delete every comment belonging to the post
            db.session.commit() # write changes to the database
            flash('Post deleted') # tell the user the post was deleted
            return redirect(url_for('dashboard')) # redirect the user to the dashboard
        else:
            return Response("This post does not belong to you", status=403) # tell the user they cant delete the post
    else: # if a post with the supplied post id does not exists 
        return Response("This post does not exist", status=404) # send a 404 status


@app.route('/post/comment/<int:post_id>', methods=['POST'])
@login_required # login is required to check who wants to comment on a post
def create_comment(post_id): 
    # This route lets users comment on a post  
    form = CreateNewCommentForm() # initialize the comment formular
    post_exists = Post.query.filter_by(id=post_id).first() # does the post actually exist?
    if post_exists:
        user_id = User.query.filter_by(username=current_user.username).first().id # get the user id of the current user
        if form.validate_on_submit(): # if the submitted data is valid
            new_comment = Comment( # create a new comment row
                created=datetime.utcnow(), # comment creation date
                author_id=user_id, # who commented?
                belongs_to_post_id=post_id, # what post does this comment belong to?
                text=form.comment_text.data # what was acutally commented
            )
            db.session.add(new_comment) # add the comment to the database
            db.session.commit() # write changes to the database
            flash("Comment posted") # tell the user the comment was posted
            return redirect(url_for('dashboard')) # redirect to the dashboard
    else: # if the post does not exists
        return Response('Post not found', status=404) # send a 404 status

@app.route('/post/comment/delete/<int:comment_id>')
@login_required # login is required to check if the user is allowed to delete the comment
def delete_comment(comment_id):
    # This route lets users delete their comment on a post
    comment = Comment.query.filter_by(id=comment_id).first() # get the comment row from database
    if comment: # if the comment exists
        user_id = User.query.filter_by(username=current_user.username).first().id # get the user id of the current user 
        if user_id == comment.author_id: # if the comment was created by the current user
            db.session.query(Comment).filter(Comment.id==comment_id).delete() # delete the comment
            db.session.commit() # write changes to database
            flash('Comment deleted') # tell the user the comment was deleted
            return redirect(url_for('dashboard')) # and redirect them to the dashboard
        else: # the comment does not belong to the current user
            return Response("This comment does not belong to you", status=403) # send a 403 status
    return Response("This comment does not exist", status=404) # no comment with the specified comment_id was found, so we send a 404 status

@app.route('/post/react/<int:post_id>/<string:type>')
@login_required
def react_to_post(post_id, type):
    # This route lets users react to posts. The specified reaction has to be valid
    post_exists = Post.query.filter_by(id=post_id).first() # check if the post with id "post_id" exists
    valid_reactions = ["thumbsup", "thumbsdown"] # the list of valid reactions , TODO: move this list to the flask_app_config
    if post_exists: # if the post exists
        if type in valid_reactions: # check if the reaction type is valid 
            user_id = User.query.filter_by(username=current_user.username).first().id # get the user id by username 
            previous_reaction = PostReaction.query.filter_by(belongs_to_user_id=user_id, belongs_to_post_id=post_id).first() # get the previous reaction of the user for that specific post
            # from here we have to handle 3 different situations:
            # 1. no reaction exists, so we have to create a new one
            # 2. same reaction exists, so the user wants to delete the reaction
            # 3. different reaction has to be created, by deleting the previous one
            same_reaction_posted_again = False 
            if previous_reaction: # if a reaction to this post with id "post_id" exists, delete it
                if previous_reaction.reaction_type == type: # check if the reaction is the same (situation "2")
                    same_reaction_posted_again = True
                    flash("Reaction removed") # tell the user their reaction was deleted 
                else: # the user changed their reaction (situation "3")
                    flash("Reaction changed") # tell the user their reaction was changed 
                db.session.query(PostReaction).filter(PostReaction.belongs_to_user_id==user_id, PostReaction.belongs_to_post_id==post_id).delete() # in situation "2" and "3" the reaction has to be deleted
            if not same_reaction_posted_again: # if the reaction to that post is different than the previous reaction
                new_reaction = PostReaction(
                    belongs_to_user_id = user_id,
                    belongs_to_post_id = post_id,
                    reaction_type = type
                ) # create new PostReaction row
                db.session.add(new_reaction) # add reaction to database
                if not previous_reaction:
                    flash("Reaction posted") # show user that the reaction was successfully posted
                    
            db.session.commit() # save database state
            return redirect(url_for("dashboard")) # redirect the user to the dashboard
        else:
            flash("Invalid reaction") # show user that the reaction was not valid
            return redirect(url_for("dashboard", code=403)) # redirect the user to the dashboard
    else: # if no post with the id was found
        flash("Post not found") # tell the user
        return redirect(url_for('dashboard'), code=404) # send a 404 status
    
@app.route('/sensor/delete/<station_id>/<slot>', methods=['POST'])
@login_required
def delete_sensor(station_id, slot):
    # This route lets the user delete a sensor of their station
    station = Station.query.filter_by(id=station_id).first() # get the station from the database
    station_belongs_to_current_user = None 
    try:
        station_belongs_to_current_user=User.query.filter_by(username=current_user.username).first().id == station.belongs_to_user_id # check if the station belongs to the current user
    except:
        return Response("Station does not exist", status=404) # if the station was not found, send a 404 status
    if station_belongs_to_current_user: # if the station belongs to the current user
        sensor = Sensor.query.filter_by(belongs_to_station_id=station_id, station_slot=slot).first() # get the sensor row from the database 
        if sensor: # if the sensor was found
            calibration_value_for_sensor = CalibrationValueForSensor.query.filter_by(belongs_to_sensor_id=sensor.id).first() # check if a calibration value for that sensor was found
            if calibration_value_for_sensor: # if the calibration value for that sensor exists
                CalibrationValueForSensor.query.filter_by(belongs_to_sensor_id=sensor.id).delete() # delete the calibration value
            osem_sensebox_id_for_sensor = station.osem_sensebox_id 
            osem_sensor_id_for_sensor = sensor.osem_sensor_id
            
            deletion = 408 # HTTP status for request timeout
            sensor_id_present_in_osem = None

            try: 
                deletion = osem_access.delete_sensor(sensebox_id=osem_sensebox_id_for_sensor, sensor_id=osem_sensor_id_for_sensor) # try to delete the sensor in OSeM
                if deletion!=200: # if the sensor deletion was not successful, maybe it is not present in OSeM
                    # the following line checks if the sensor id is present in OSeM. If not, we do not have to delete it because it does not exists anymore
                    sensor_id_present_in_osem = osem_sensor_id_for_sensor in  osem_access.get_sensor_ids_of_sensebox(osem_sensebox_id_for_sensor) 
                    print("Deletion status is ", deletion, ', checking if sensor id is still present in sensebox: ', sensor_id_present_in_osem)
            except NoInternetConnection: # if no internet connection is available on serverside, the request will timeout
                flash("Action currently not available, no internet connection")
                
            if deletion==200 or ( deletion!=408 and not sensor_id_present_in_osem): # if the deletion was successful or the sensor does not even exist in OSeM, we can safely delete it from our database
                db.session.query(Sensor).filter(Sensor.belongs_to_station_id==station_id, Sensor.station_slot==slot).delete()  # delete the sensor from our database
                db.session.commit() # write changes to the database
                update_payload_formatter_for_ttn_enddevice(station_id) # update the payload formatter in TTN
            else: # if the deletion of the sensor failed
                flash("Could not delete sensor in OpenSenseMap")
                print("Deletion of sensor in OSeM failed with status code", deletion) #
            return redirect(url_for('update_station', id=station_id)) # send the user back to their station overview
        else:
            return Response("Sensor slot not found for this station", status=404)
    else:
        return Response('not yours, sorry', status=403)


@app.route('/register', methods=['GET','POST'])
def register():
    # This route lets users create their accounts
    form = RegisterForm() # init the RegisterForm
    if form.validate_on_submit(): # if the form is submitted and valid
        hashed_password = bcrypt.generate_password_hash(form.password.data) # take the submitted password and create a hash    
        new_user = User(username=form.username.data, password=hashed_password) # create a new User row with the submitted name and the password hash
        db.session.add(new_user) # add row to database
        db.session.commit() # write changes to database
        flash('You were successfully registered') # tell the user the registration was successful
        return redirect(url_for('login')) # redirect to login page
    else: # if the form is invalid (e.g. username or password too short)
        if User.query.filter_by(username=form.username.data).first(): # if a user with that username exists
            flash("This username is taken") # tell the user
    return render_template('register.html',form=form) # redirect to registration page by default


@app.route('/logout', methods=['GET','POST'])
@login_required # in order to log out you have to be logged in first
def logout():
    # This route lets users log out
    logout_user()
    return redirect(url_for('login'))

def configure_api_access():
    # This function reads config data from a file and sets them for the whole application
    global osem_access 
    global ttn_access
    global ttn_app_id
    config = configparser.ConfigParser()
    
    config.read('flask_app_configuration.ini') # read the config file

    try:
        ttn_access = TtnAccess( # finally we can create our TtnAccess object to do TTN operations
            full_account_key=config["TTN"]["full_account_key"], # set the key for TTN access
            username=config["TTN"]["username"] # set the username for TTN access
        ) 
        ttn_access.add_webhook_to_ttn_app( # add the webhook in TTN, so that the data will be forwarded to OpenSenseMap
            app_id=config["TTN"]["app_id"], # set the TTN AppId
            webhook_id='ugb-osem-webhook'
        )        
    except KeyError: # a KeyError exception will be thrown if the config file is corrupt or is not found 
        print("[ERROR] Flask configuration file not existent or missing required parameters, check correct filename and structure")
    except NoInternetConnection: # if the application has no internet connection on startup, the webhook cannot be set
        print("[ERROR] No internet connection, could not configure API access")
    try:
        osem_access = OsemAccess(  # create the OsemAccess object
            config["OSEM"]["email"], # OpenSenseMap email
            config["OSEM"]["password"] # OpenSenseMap password
        ) 
    except NoInternetConnection: # if the application has no internet connection, the OsemAccess object will not be able to sign in
        print("[ERROR] OsemAccess could not sign in, no internet connection")
        osem_access = OsemAccess(config["OSEM"]["email"], config["OSEM"]["password"], auto_sign_in=False) # create the object without auto-signin

def configure_db_access():
    # This function configures the datasource for displaying recent sensor data
    global persistence_object
    config = configparser.ConfigParser()
    
    config.read('flask_app_configuration.ini')
    try:
        persistence_object = Persistence({
                "url": config["PERSISTENCE"]["url"],
                "token": config["PERSISTENCE"]["token"],
                "org": config["PERSISTENCE"]["org"],
                "debug": False,
                "table": config["PERSISTENCE"]["table"]
        })
    except KeyError:
        print("[ERROR] Datasource config is not valid")

if __name__ == '__main__':
    configure_api_access()
    configure_db_access()
    app.run(debug=False, host='0.0.0.0')