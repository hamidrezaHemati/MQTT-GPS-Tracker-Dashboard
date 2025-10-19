import threading
from flask import Flask, render_template, jsonify, make_response, request, session, redirect, url_for
import paho.mqtt.client as mqtt
from datetime import datetime, timedelta
from collections import deque
import os, json, csv

app = Flask(__name__, static_folder='static')
app.secret_key = "supersecretkey"  # session management

# === MQTT Settings ===

# MQTT_SERVER = os.getenv('MQTT_SERVER', '94.182.137.200')  # Shatel
MQTT_SERVER = os.getenv('MQTT_SERVER', '46.62.161.208')    # Heltzner

# MQTT_PORT = 1883
MQTT_PORT = int(os.getenv('MQTT_PORT', 1883))
CLIENT_ID = "dashboard_mqtt_hub"
KEEPALIVE = 600  # seconds, adjust as needed

# === Credentials ===
USERNAME = "admin"
PASSWORD = "admin"

# === Storage ===
script_dir = os.path.dirname(os.path.abspath(__file__))
status_device_messages = {}   # IMEI -> deque of messages
device_locations = {}  # IMEI -> deque of last N locations
added_devices = []     # list of connected IMEIs
# status_message_history = deque(maxlen=50)

rfid_device_messages = {}   # IMEI -> deque of rfid messages
rfid_message_history = deque(maxlen=100)

sms_device_messages = {}   # IMEI -> deque of sms messages
sms_message_history = deque(maxlen=100)

gyroscope_device_messages = {}   # IMEI -> deque of gyroscope messages
gyroscope_message_history = deque(maxlen=100)

# === MQTT Client ===
client = mqtt.Client(CLIENT_ID)
client_lock = threading.Lock()  # to protect MQTT client usage across threads


# ------------------- MQTT Callbacks -------------------
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("✅ Connected to MQTT Broker")
        # Resubscribe to all devices
        for imei in added_devices:
            topic_status = f"truck/{imei}/status"
            topic_rfid_data = f"truck/{imei}/rfid"
            topic_sms_data = f"truck/{imei}/sms"
            topic_gyroscope_data = f"truck/{imei}/gyroscope"
            client.subscribe(topic_status)
            client.subscribe(topic_rfid_data)
            client.subscribe(topic_sms_data)
            client.subscribe(topic_gyroscope_data)
            print(f"📡 Subscribed to {topic_status} and {topic_rfid_data} and {topic_sms_data} and {topic_gyroscope_data}")
    else:
        print(f"❌ MQTT Connection failed with code {rc}")


def on_disconnect(client, userdata, rc):
    print(f"⚠️ Disconnected from MQTT Broker (rc={rc}), attempting reconnect...")
    try:
        client.reconnect()
    except Exception as e:
        print(f"❌ Reconnect failed: {e}")


def rssi_to_strength(rssi):
    if rssi == 0:
        return "No Signal"
    elif 1 <= rssi <= 6:
        return "Very Weak"
    elif 7 <= rssi <= 12:
        return "Weak"
    elif 13 <= rssi <= 20:
        return "Moderate"
    elif 21 <= rssi <= 26:
        return "Strong"
    elif 27 <= rssi <= 31:
        return "Very Strong"
    else:
        return "Invalid RSSI"
    

def handle_status_msg(msg, payload, IMEI):
    print(f"Incomming msg from {IMEI}")

    parts = [p.strip() for p in payload.split(",")]
    if len(parts) != 19:
        print(f"⚠️ Invalid payload for {IMEI}: {payload}")
        return
    
    HH, MM, SS = parts[0], parts[1], parts[2]
    lat, lon = float(parts[3]), float(parts[4])
    gpsSource = parts[5]
    gpsTravelledDistance, totalTravelledDistance, speed = float(parts[6]), float(parts[7]), float(parts[8])
    Batt, Lock, Temp = int(parts[9]), parts[10], float(parts[11])
    RSSI, Cnt, Queued = int(parts[12]), int(parts[13]), int(parts[14])
    isInGeofence, distanceToGeoFence = parts[15], int(parts[16])
    spoofingDetection, jammingDetection = parts[17], parts[18]

    RSSI_status = rssi_to_strength(RSSI)
    if gpsSource == "G": gpsSource = "GPS"
    if gpsSource == "B": gpsSource = "BTS"

    if isInGeofence =="Y": isInGeofence = "in Geo-fence"
    if isInGeofence =="N": isInGeofence = "Out of Geo-fence"

    if jammingDetection == 'J': jammingDetection = 'Jamming' 
    if jammingDetection == 'V': jammingDetection = ''

    if spoofingDetection == 'S': spoofingDetection = 'Spoofing' 
    if spoofingDetection == 'V': spoofingDetection = ''


    # Battery formatting
    Batt = f"{Batt*10} ~ {(Batt+1)*10}" if Batt < 10 else "100"
    Lock = {"L": "Locked", "U": "Unlocked"}.get(Lock, "Undefined")

    server_time = datetime.now()                                  # Get server local time
    # iran_time = server_time + timedelta(hours=1, minutes=30)      # Add 1 hour 30 minutes
    message = {
        "timestamp": server_time.strftime('%Y-%m-%d %H:%M:%S'),
        "topic": msg.topic,
        "HH": HH, "MM": MM, "SS": SS,
        "lat": lat, "lon": lon, "gpsSource": gpsSource,
        "gpsTravelledDistance": gpsTravelledDistance, "totalTravelledDistance": totalTravelledDistance, "speed": speed,
        "Batt": Batt, "Lock Status": Lock,
        "Temperature": Temp, "RSSI": RSSI, "RSSI_status": RSSI_status, "Cnt": Cnt, "isQueued": Queued,
        "isInGeofence": isInGeofence, "distanceToGeoFence": distanceToGeoFence,
        "spoofing": spoofingDetection, "jamming": jammingDetection
    }

    # status_message_history.appendleft(message)
    # print(f'Counter: {message['Cnt']}')
    with client_lock: # <-- Lock for thread safety
        # Only one thread at a time can execute this block
        status_device_messages[IMEI].appendleft(message)
        device_locations[IMEI].appendleft({"lat": lat, "lon": lon})

def handle_rfid_msg(msg, payload, IMEI):
    parts = [p.strip() for p in payload.split(",")]
    print(len(parts))
    if len(parts) != 2:
        print(f"⚠️ Invalid RFID payload for {IMEI}: {payload}")
        return
    
    rfid_serial, action_status = parts

    if action_status == "L": action_status = "Lock command"
    if action_status == "U": action_status = "Unlock command"
    if action_status == "N": action_status = "Unkown command" # TODO: Modify this part with DATABASE 
    
    server_time = datetime.now()                                  # Get server local time
    # iran_time = server_time + timedelta(hours=1, minutes=30)      # Add 1 hour 30 minutes
    message = {
        "HH": server_time.strftime('%H'),
        "MM": server_time.strftime('%M'),
        "SS": server_time.strftime('%S'),
        "topic": msg.topic,
        "rfid_serial": rfid_serial, "action_status": action_status
    }
    print(message)

    with client_lock:
        rfid_message_history.appendleft(message)
        rfid_device_messages[IMEI].appendleft(message)

def handle_sms_msg(msg, payload, IMEI):
    parts = [p.strip() for p in payload.split(",")]
    print(len(parts))
    if len(parts) != 2:
        print(f"⚠️ Invalid SMS payload for {IMEI}: {payload}")
        return
    
    phone_number, action = parts[0], parts[1]
    
    server_time = datetime.now()                                  # Get server local time
    iran_time = server_time + timedelta(hours=1, minutes=30)      # Add 1 hour 30 minutes
    message = {
        "HH": server_time.strftime('%H'),
        "MM": server_time.strftime('%M'),
        "SS": server_time.strftime('%S'),
        "topic": msg.topic,
        "phone_number": phone_number, "action": action
    }
    print(message)

    with client_lock:
        sms_message_history.appendleft(message)
        sms_device_messages[IMEI].appendleft(message)

def on_message(client, userdata, msg):
    print("Incomming msg - on message function")
    try:
        topic_parts = msg.topic.split("/")
        IMEI = topic_parts[1] if len(msg.topic.split("/")) == 3 else "unknown"
        topic_suffix = topic_parts[2] if len(msg.topic.split("/")) == 3 else "unknown"
        print(f"on_message - IMEI: {IMEI}, suffix {topic_suffix}")

        payload = msg.payload.decode().strip()

        if IMEI not in status_device_messages:
            print(f"⚠️ Unknown IMEI message: {IMEI}, payload={payload}")
            return

        if payload.startswith("{") and payload.endswith("}"):   # Remove braces
            payload = payload[1:-1].strip()
        
        if topic_suffix == "status":
            print(f"📦 status message from {IMEI}")
            handle_status_msg(msg, payload, IMEI)
        elif topic_suffix == 'rfid':
            print(f"🔑 RFID message from {IMEI}: {payload}")
            handle_rfid_msg(msg, payload, IMEI)
        elif topic_suffix == 'sms':
            print(f"📨 sms message from {IMEI}: {payload}")
            handle_sms_msg(msg, payload, IMEI)
        elif topic_suffix == 'gyroscope':
            print(f"gyroscope message from {IMEI}: {payload}")
        else:
            print(f"⚠️ Unknown message type: {topic_suffix}, payload={payload}")


    except Exception as e:
        print(f"⚠️ Error processing message: {e}")


# ------------------- MQTT Start -------------------
def start_mqtt():
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    client.connect(MQTT_SERVER, MQTT_PORT, KEEPALIVE)

    # Start MQTT loop in a separate thread
    mqtt_thread = threading.Thread(target=client.loop_forever, daemon=True)
    mqtt_thread.start()


# ------------------- Flask Routes -------------------
@app.route("/", methods=["GET", "POST"])
def login():
    return redirect(url_for("dashboard"))
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if username == USERNAME and password == PASSWORD:
            session["logged_in"] = True
            return redirect(url_for("dashboard"))
        return render_template("login.html", error="Invalid username or password")
    return render_template("login.html")

@app.route("/dashboard")
def dashboard():
    gps_point = [35.7762, 51.4768]
    # if status_message_history:
    #     gps_point = [status_message_history[0]['lat'], status_message_history[0]['lon']]
    return render_template("index.html", gps_point=gps_point)

@app.route('/data/<IMEI>/status')
def status_data_for_device(IMEI):
    msgs = list(status_device_messages.get(IMEI, []))
    latest = msgs[0] if msgs else None
    return make_response(jsonify(latest), 200) if latest else jsonify({})

@app.route('/data/<IMEI>/rfid')
def rfid_data_for_device(IMEI):
    msgs = list(rfid_device_messages.get(IMEI, []))
    latest = msgs[0] if msgs else None
    return make_response(jsonify(latest), 200) if latest else jsonify({})

@app.route('/data/<IMEI>/sms')
def sms_data_for_device(IMEI):
    msgs = list(sms_device_messages.get(IMEI, []))
    return make_response(jsonify(msgs), 200)

@app.route("/device_location/<IMEI>")
def device_location(IMEI):
    if IMEI in device_locations and device_locations[IMEI]:
        latest = device_locations[IMEI][0]
        return jsonify({
            "success": True, 
            "lat": latest["lat"], 
            "lon": latest["lon"]})
    return jsonify({"success": False, "msg": "No location yet"})

@app.route('/connect', methods=['POST'])
def connect_device():
    data = request.get_json()
    IMEI = data.get("IMEI")
    if not IMEI:
        return jsonify({"status": "error", "message": "IMEI required"}), 400

    topic_status = f"truck/{IMEI}/status"
    topic_rfid_data = f"truck/{IMEI}/rfid"
    topic_sms_data = f"truck/{IMEI}/sms"
    topic_gyroscope_data = f"truck/{IMEI}/gyroscope"

    with client_lock:
        client.subscribe(topic_status)
        client.subscribe(topic_rfid_data)
        client.subscribe(topic_sms_data)
        client.subscribe(topic_gyroscope_data)

        added_devices.append(IMEI)
        device_locations[IMEI] = deque(maxlen=100)
        status_device_messages[IMEI] = deque(maxlen=100)
        rfid_device_messages[IMEI] = deque(maxlen=100)
        sms_device_messages[IMEI] = deque(maxlen=100)
    return jsonify({"status": "connected", "message": f"Subscribed to topics"})


@app.route("/publish/<IMEI>/<cmd_type>", methods=["POST"])
def publish_command(IMEI, cmd_type):
    data = request.get_json()
    topic_map = {
        "lock": f"truck/{IMEI}/command/lock",
        "wit": f"truck/{IMEI}/command/config/wit",
        "rfid": f"truck/{IMEI}/command/config/rfid",
        "gyroscope": f"truck/{IMEI}/command/config/gyroscope",
        "newPhone": f"truck/{IMEI}/command/config/phoneNumber"
    }
    topic = topic_map.get(cmd_type)
    if not topic:
        return jsonify({"success": False, "msg": "Unknown command"}), 400

    msg_value = data.get("command") or data.get("wait_time") or data.get("rfid") or data.get("gyro_sensitivity") or data.get("new_phone")
    msg = '{' + str(msg_value) + '}'

    with client_lock:
        if IMEI in added_devices:
            client.publish(topic, msg)
            return jsonify({"success": True, "msg": f"Published {msg} to {topic}"})
        return jsonify({"success": False, "msg": "IMEI not connected"}), 400
    

# ------------------- Main -------------------
if __name__ == "__main__":
    start_mqtt()
    app.run(host="0.0.0.0", port=80, debug=False)  # debug=False for production