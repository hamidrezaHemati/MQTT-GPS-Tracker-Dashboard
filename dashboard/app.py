import threading
from flask import Flask, render_template, jsonify, make_response, request
import paho.mqtt.client as mqtt
from datetime import datetime
from collections import deque
from flask import request, redirect, url_for, session, flash
from flask_bcrypt import Bcrypt
import json, threading
import csv, os
import json

app = Flask(__name__, static_folder='static')

mqtt_server_ip = '89.219.105.47'
mqtt_server_port = 1883

# Get absolute path to the folder this script is in
script_dir = os.path.dirname(os.path.abspath(__file__))
csv_path = os.path.join(script_dir, "mqtt_messages.csv")

# === Ensure CSV has a header row ===
if not os.path.exists(csv_path):
    with open(csv_path, mode="w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["HH", "MM", "SS", "lat", "lon", "Alt", "Batt","Lock","Temp","RSSI","Cnt","Queued"])

message_history = deque(maxlen=50)

CLIENT_ID = "dashboard_mqtt_hub"

# Globals for MQTT client and current config
client = None
current_config = {"ip": None, "port": None, "topic": None}

# global event and result container
connect_event = threading.Event()
connect_result = {"success": False, "msg": ""}

def on_connect(c, userdata, flags, rc):
    if rc == 0:
        print("✅ Connected to MQTT Broker!")
        c.subscribe(current_config["topic"])
        connect_result["success"] = True
        connect_result["msg"] = "Connected successfully"
    else:
        print(f"❌ Failed to connect: {rc}")
        connect_result["success"] = False
        connect_result["msg"] = f"Failed to connect, return code {rc}"
    connect_event.set()

def on_message(client, userdata, msg):
    payload_str = msg.payload.decode().strip()
    
    # Remove braces if present
    if payload_str.startswith("{") and payload_str.endswith("}"):
        payload_str = payload_str[1:-1].strip()

    # Split into list by comma
    parts = [p.strip() for p in payload_str.split(",")]

    # Map to named variables
    HH, MM, SS = parts[0], parts[1], parts[2]
    lat, lon, Alt = parts[3], parts[4], parts[5]
    Batt, Lock, Temp = parts[6], parts[7], parts[8]
    RSSI, Cnt, Queued = parts[9], parts[10], parts[11]

    try:
        payload_json = json.loads(payload_str)
        if isinstance(payload_json, dict):
            lat = payload_json.get("lat")
            lon = payload_json.get("lon")
    except json.JSONDecodeError:
        pass  # payload is not JSON; lat/lon remain None

    # Store for webpage log
    message = {
        "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "topic": msg.topic,
        "HH": HH,
        "MM": MM,
        "SS": SS,
        "lat": float(lat),
        "lon": float(lon),
        "Alt": float(Alt),
        "Batt": int(Batt),
        "Lock Status": Lock,
        "Temprature": float(Temp),
        "RSSI": int(RSSI),
        "Cnt": int(Cnt),
        "isQueued": int(Queued)
    }
    if lat is not None and lon is not None:
        message["lat"] = lat
        message["lon"] = lon

    message_history.appendleft(message)
    
    print(f"📥 Logged MQTT message: {message}")
    
    # Append to CSV
    with open(csv_path, mode="a", newline="") as file:
        writer = csv.writer(file)
        writer.writerow([
            HH, MM, SS, lat, lon, Alt, Batt, Lock, Temp, RSSI, Cnt, Queued
        ])

    
def start_mqtt(ip, port, topic):
    global client, current_config, connect_event, connect_result

    if client:
        try:
            client.loop_stop()
            client.disconnect()
        except Exception as e:
            print(f"❌ Error stopping old client: {e}")

    client = mqtt.Client(CLIENT_ID)
    client.on_connect = on_connect
    client.on_message = on_message

    current_config = {"ip": ip, "port": port, "topic": topic}

    # Reset the event and connection result before connect attempt
    connect_event.clear()
    connect_result = {"success": False, "msg": ""}

    try:
        client.connect(ip, int(port), 60)
        client.loop_start()
    except Exception as e:
        print(f"❌ MQTT connection error: {e}")
        return False, f"Connection error: {e}"

    # Wait for on_connect callback (max 5 seconds)
    connected = connect_event.wait(timeout=5)

    if not connected:
        # Timeout waiting for connection
        return False, "Connection timed out"

    return connect_result["success"], connect_result["msg"]


@app.route('/')
def index():
    gps_point = [35.776215087404076, 51.47687022102022]
    if message_history:
        current_msg = message_history[0]
        if 'lat' in current_msg and 'lon' in current_msg:
            gps_point = [current_msg['lat'], current_msg['lon']]
    return render_template("index.html", gps_point=gps_point)


@app.route('/data')
def data():
    response = make_response(jsonify(list(message_history)))
    response.headers['Cache-Control'] = 'no-store'
    return response


@app.route('/connect', methods=['POST'])
def connect():
    data = request.get_json()
    IMEA = data.get("IMEA")

    if not (IMEA):
        return jsonify({"status": "error", "message": "Your device IMEA code is required"}), 400
    
    topic = f'truck/{IMEA}/status'
    success, msg = start_mqtt(mqtt_server_ip, mqtt_server_port, topic)
    status = "connected" if success else "error"
    return jsonify({"status": status, "message": msg})


if __name__ == "__main__":
    # No MQTT thread here because connection is initiated on-demand from web
    app.run(debug=True)
