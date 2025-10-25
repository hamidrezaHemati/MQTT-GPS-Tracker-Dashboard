'use strict';
// Initial gpsPoint from Flask
let map;
let deviceMarkers = {};
let deviceColors = {};
let currentIMEI = null;
let activeDevices = new Set(); // Track all active devices
let locationUpdateInterval = null; // Single interval for all devices
let statusConsoleInterval = null;
let rfidInterval = null;
let smsInterval = null;

// Available colors
const availableColors = [
    "red", "blue", "green", "orange", "yellow",
    "violet", "grey", "black"
];

function initMap() {
    const streets = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '© OpenStreetMap'
    });
    const satellite = L.tileLayer('https://{s}.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', {
    maxZoom: 20,
    subdomains:['mt0','mt1','mt2','mt3'],
    attribution: '© Google'
    });
    const terrain = L.tileLayer('https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png', {
    maxZoom: 17,
    attribution: '© OpenTopoMap'
    });

    map = L.map('map', {
    center: [35.729015, 51.824891],
    zoom: 16,
    layers: [streets]
    });

    const baseMaps = {
    "Streets": streets,
    "Satellite": satellite,
    "Terrain": terrain
    };
    L.control.layers(baseMaps).addTo(map);
}

function getPinIcon(color) {
    return L.icon({
    iconUrl: `https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-${color}.png`,
    shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
    iconSize: [25, 41],
    iconAnchor: [12, 41],
    popupAnchor: [1, -34],
    shadowSize: [41, 41]
    });
}

function getDeviceColor(imei) {
    if (!deviceColors[imei]) {
    const colorIndex = Object.keys(deviceColors).length % availableColors.length;
    deviceColors[imei] = availableColors[colorIndex];
    }
    return deviceColors[imei];
}

async function updateDeviceLocation(imei) {
    try {
    const res = await fetch(`/device_location/${imei}`);
    const data = await res.json();
    if (data.success) {
        const pos = [data.lat, data.lon];
        const color = getDeviceColor(imei);
        if (!deviceMarkers[imei]) {
        deviceMarkers[imei] = L.marker(pos, { icon: getPinIcon(color) })
            .addTo(map)
            .bindPopup(`🚛 ${imei}`);
        } else {
        deviceMarkers[imei].setLatLng(pos);
        }
    }
    } catch (err) {
    console.error("Error updating location:", err);
    }
}

// Update ALL active devices in a single interval
function updateAllDeviceLocations() {
    activeDevices.forEach(imei => {
    updateDeviceLocation(imei);
    });
}

// Start a single interval that updates all devices
function startLocationUpdates() {
    if (locationUpdateInterval) return; // Already running
    
    locationUpdateInterval = setInterval(() => {
    updateAllDeviceLocations();
    }, 2000); // every 2s
}

// Add device to tracking
function addDeviceToTracking(imei) {
    activeDevices.add(imei);
    updateDeviceLocation(imei); // Immediate update
    startLocationUpdates(); // Ensure interval is running
}

document.addEventListener("DOMContentLoaded", () => {
    initMap();
});

function rfidConfigModal() { document.getElementById("rfid-modal").style.display = "block"; }
function rfidConfigConfigModal() { document.getElementById("rfid-modal").style.display = "none"; }
function openLockModal() { document.getElementById("lock-modal").style.display = "block"; }
function closeLockModal() { document.getElementById("lock-modal").style.display = "none"; }
function openConfigModal() { document.getElementById("wit-modal").style.display = "block"; }
function closeConfigModal() { document.getElementById("wit-modal").style.display = "none"; }
function gyroConfigModal() { document.getElementById("gyro-modal").style.display = "block"; }
function closeGyroConfigModal() { document.getElementById("gyro-modal").style.display = "none"; }
function addPhoneConfigModal() { document.getElementById("add-phone-modal").style.display = "block"; }
function closeAddPhoneModal() { document.getElementById("add-phone-modal").style.display = "none"; }

// rfid command submit
document.getElementById("rfid-form").addEventListener("submit", async e => {
    e.preventDefault();
    let rfid = document.getElementById("rfid-command").value;
    try {
    await fetch(`/publish/${currentIMEI}/rfid`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ rfid: rfid })
    });
    alert("✅ RFID command sent!");
    rfidConfigConfigModal();
    } catch (err) {
    alert("❌ Failed to send RFID command");
    console.error(err);
    }
});

// Lock command submit
document.getElementById("lock-form").addEventListener("submit", async e => {
    e.preventDefault();
    const command = document.getElementById("lock-command").value;
    try {
    await fetch(`/publish/${currentIMEI}/lock`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ command: command })
    });
    alert("✅ Lock command sent!");
    closeLockModal();
    } catch (err) {
    alert("❌ Failed to send lock command");
    console.error(err);
    }
});

// Config wait submit
document.getElementById("wit-form").addEventListener("submit", async e => {
    e.preventDefault();
    const time = document.getElementById("wit-time").value;
    const value = "wit_on_" + time;
    try {
    await fetch(`/publish/${currentIMEI}/wit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ wait_time: value })
    });
    alert("✅ Config wait time sent!");
    closeConfigModal();
    } catch (err) {
    alert("❌ Failed to send config");
    console.error(err);
    }
});

// gyro Config submit
document.getElementById("gyro-form").addEventListener("submit", async e => {
    e.preventDefault();
    const sensitivity = document.getElementById("gyro-sensitivity").value;
    const value = "gyro_on_" + sensitivity;
    try {
    await fetch(`/publish/${currentIMEI}/gyroscope`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ gyro_sensitivity: value })
    });
    alert("✅ Gyro sensitivity sent!");
    closeGyroConfigModal();
    } catch (err) {
    alert("❌ Failed to send Gyro sensitivity");
    console.error(err);
    }
});

// add phone Config submit
document.getElementById("add-phone-form").addEventListener("submit", async e => {
    e.preventDefault();
    let new_phone_number = document.getElementById("new-phone-number").value.trim();
    new_phone_number = new_phone_number.replace(/\s|-/g, '');
    
    if (!new_phone_number.startsWith("+98")) {
    new_phone_number = new_phone_number.replace(/^0/, '');
    new_phone_number = "+98" + new_phone_number;
    }
    const value = "add_" + new_phone_number;
    try {
    await fetch(`/publish/${currentIMEI}/newPhone`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ new_phone: value })
    });
    alert("✅ Phone number Added!");
    closeAddPhoneModal();
    } catch (err) {
    alert("❌ Failed to send the Phone number");
    console.error(err);
    }
});

// Device console - FIXED to prevent data mixing
function startStatusConsole(IMEI) {
    // Clear existing interval
    if (statusConsoleInterval) {
    clearInterval(statusConsoleInterval);
    statusConsoleInterval = null;
    }
    
    async function fetchDeviceData() {
    // CRITICAL: Only fetch if this IMEI is still the current one
    if (currentIMEI !== IMEI) return;
    
    try {
        const response = await fetch(`/data/${IMEI}/status`);
        const data = await response.json();
        console.log(`fetch status data from ${IMEI}`);
        
        // Double-check IMEI hasn't changed during fetch
        if (currentIMEI !== IMEI) return;
        
        if (data && Object.keys(data).length > 0) {
        const latest = data;  
        document.getElementById("param-time").textContent = `${latest.HH}:${latest.MM}:${latest.SS}`;
        document.getElementById("param-lat").textContent = latest.lat;
        document.getElementById("param-lon").textContent = latest.lon;
        document.getElementById("param-gpsSource").textContent = latest.gpsSource;
        document.getElementById("param-spoofing").textContent = latest.spoofing;
        document.getElementById("param-jamming").textContent = latest.jamming;
        document.getElementById("param-speed").textContent = latest.speed + " KM/h"; 
        document.getElementById("param-traveledDistance").textContent = latest.gpsTravelledDistance + " KM";
        document.getElementById("param-totalTraveledDistance").textContent = latest.totalTravelledDistance + " KM";
        document.getElementById("param-distanceToGeo").textContent = latest.distanceToGeoFence + " M";
        document.getElementById("param-isInGeofence").textContent = latest.isInGeofence;
        document.getElementById("param-batt").textContent = latest.Batt + "%";
        document.getElementById("param-lock").textContent = latest["Lock Status"];
        document.getElementById("param-temp").textContent = latest.Temperature + " °C";
        document.getElementById("param-rssi-status").textContent = latest.RSSI_status;
        updateFlipCounter(latest.Cnt);
        document.getElementById("param-queued").textContent = latest.isQueued;
        } else {
        resetStatusDisplay();
        }
    } catch (err) {
        console.error("Error fetching device data:", err);
    }
    }
    
    fetchDeviceData(); // Immediate fetch
    statusConsoleInterval = setInterval(fetchDeviceData, 2000);
}

function resetStatusDisplay() {
    document.getElementById("param-time").textContent = "--:--:--";
    document.getElementById("param-lat").textContent = "--";
    document.getElementById("param-lon").textContent = "--";
    document.getElementById("param-gpsSource").textContent = "--";
    document.getElementById("param-spoofing").textContent = "--";
    document.getElementById("param-jamming").textContent = "--";
    document.getElementById("param-speed").textContent = "-- KM/H"; 
    document.getElementById("param-traveledDistance").textContent = "-- KM";
    document.getElementById("param-totalTraveledDistance").textContent = "-- KM";
    document.getElementById("param-distanceToGeo").textContent = "-- M";
    document.getElementById("param-isInGeofence").textContent = "--";
    document.getElementById("param-batt").textContent = "--%";
    document.getElementById("param-lock").textContent = "--";
    document.getElementById("param-temp").textContent = "-- °C";
    document.getElementById("param-rssi-status").textContent = "No Signal";
    updateFlipCounter(0);
    document.getElementById("param-queued").textContent = "--";
}

// Device RFID console - FIXED
function startRfidConsole(IMEI) {
    if (rfidInterval) {
    clearInterval(rfidInterval);
    rfidInterval = null;
    }
    
    async function fetchRfidData() {
    if (currentIMEI !== IMEI) return;
    
    try {
        const response = await fetch(`/data/${IMEI}/rfid`);
        console.log("response: ");
        console.log(response);
        const data = await response.json();
        console.log("data: ");
        console.log(data);
        if (currentIMEI !== IMEI) return;
        
        // if (!Array.isArray(data)) {
        //   console.error("RFID data is not an array!", data);
        //   return;
        // }
        
        if (data && Object.keys(data).length > 0) {
        const latest = data;
        document.getElementById("rfid-time").textContent = `${latest.HH}:${latest.MM}:${latest.SS}`;
        document.getElementById("rfid-serial").textContent = latest.rfid_serial;
        document.getElementById("rfid-action").textContent = latest.action_status;
        } else {
        resetRfidDisplay();
        }
    } catch (err) {
        console.error("Error fetching RFID data:", err);
    }
    }
    
    fetchRfidData();
    rfidInterval = setInterval(fetchRfidData, 2000);
}

function resetRfidDisplay() {
    document.getElementById("rfid-time").textContent = "--:--:--";
    document.getElementById("rfid-serial").textContent = "--";
    document.getElementById("rfid-action").textContent = "--";
}

// Device SMS console - FIXED
function startSmsConsole(IMEI) {
    if (smsInterval) {
    clearInterval(smsInterval);
    smsInterval = null;
    }
    
    async function fetchSmsData() {
    if (currentIMEI !== IMEI) return;
    
    try {
        const response = await fetch(`/data/${IMEI}/sms`);
        const data = await response.json();
        
        if (currentIMEI !== IMEI) return;
        
        if (data.length > 0) {
        const latest = data[0];
        document.getElementById("sms-time").textContent = `${latest.HH}:${latest.MM}:${latest.SS}`;
        document.getElementById("sms-phone").textContent = latest.phone_number;
        document.getElementById("sms-action").textContent = latest.action;
        } else {
        resetSmsDisplay();
        }
    } catch (err) {
        console.error("Error fetching SMS data:", err);
    }
    }
    
    fetchSmsData();
    smsInterval = setInterval(fetchSmsData, 2000);
}

function resetSmsDisplay() {
    document.getElementById("sms-time").textContent = "--:--:--";
    document.getElementById("sms-phone").textContent = "--";
    document.getElementById("sms-action").textContent = "--";
}

// Navbar switching
document.querySelectorAll(".ul0 a").forEach(link => {
    link.addEventListener("click", e => {
    e.preventDefault();
    document.querySelectorAll(".ul0 a").forEach(a => a.classList.remove("active"));
    link.classList.add("active");
    const section = link.dataset.section;
    document.querySelectorAll(".section").forEach(s => s.classList.remove("active"));
    document.getElementById(section + "-section").classList.add("active");
    });
});

// Back to devices button
document.getElementById("back-to-devices").addEventListener("click", () => {
    document.getElementById("device-page").classList.remove("active");
    document.getElementById("devices-section").classList.add("active");
});

// Modal open/close
const modal = document.getElementById("device-modal");
document.getElementById("add-device-btn").onclick = () => modal.style.display = "block";
document.querySelector(".close").onclick = () => modal.style.display = "none";
window.onclick = e => { if (e.target === modal) modal.style.display = "none"; };

// Add device form
document.getElementById("add-device-form").addEventListener("submit", async e => {
    e.preventDefault();
    const IMEI = document.getElementById("new-IMEI").value;
    
    try {
    const response = await fetch("/connect", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ IMEI: IMEI })
    });
    const result = await response.json();
    
    if (result.status === "connected") {
        const li = document.createElement("li");
        li.className = "device-card";
        li.innerHTML = `
        <div class="device-card-content">
            <img src="/static/icons/truck.png" class="normal-icon">
            <h4>${IMEI}</h4>
        </div>
        `;
        li.dataset.device = IMEI;
        document.getElementById("device-list").appendChild(li);
        
        // Add to tracking immediately
        addDeviceToTracking(IMEI);
        
        li.addEventListener("click", () => {
        document.querySelectorAll("#device-list li").forEach(li => li.classList.remove("active"));
        li.classList.add("active");
        document.querySelectorAll(".section").forEach(s => s.classList.remove("active"));
        document.getElementById("device-page").classList.add("active");
        document.getElementById("device-title").textContent = `🚛 ${IMEI}`;
        
        // Update currentIMEI BEFORE starting intervals
        currentIMEI = IMEI;
        
        // Start fetching data for THIS device
        startStatusConsole(IMEI);
        startRfidConsole(IMEI);
        });
        
        alert("✅ Connected to device " + IMEI);
        modal.style.display = "none";
        document.getElementById("add-device-form").reset();
    } else {
        alert("❌ " + result.message);
    }
    } catch (err) {
    console.error("Error connecting device:", err);
    alert("⚠️ Failed to connect to server.");
    }
});

let lastCnt = 0;
function updateFlipCounter(newValue) {
    const container = document.getElementById("msg-counter");
    const oldValue = lastCnt;
    if (newValue === oldValue) return;
    
    container.innerHTML = "";
    const digits = String(newValue).split("");
    digits.forEach((d, i) => {
    const span = document.createElement("span");
    span.className = "flip-digit";
    span.textContent = d;
    container.appendChild(span);
    
    if (String(oldValue).padStart(digits.length, "0")[i] !== d) {
        setTimeout(() => span.classList.add("flip"), 50);
        setTimeout(() => span.classList.remove("flip"), 600);
    }
    });
    lastCnt = newValue;
}