
---

# IoTGo

A lightweight IoT data collector built with Python. It reads sensor values (e.g., DHT22), exposes them over HTTP, and serves a minimal dashboard.

## Setup

### 1. Clone the repository

```bash
git clone <your-repo-url>
cd IoTGo
```

### 2. Install system dependencies

```bash
sudo apt-get update
sudo apt-get install -y liblgpio-dev python3-dev swig
```

### 3. Create and activate a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 4. Install Python requirements

```bash
pip install -r requirements.txt
```

### 5. Run the application

```bash
python3 main.py
```

## Project Structure

```
IoTGo/
├── main.py
├── sensors.py
├── requirements.txt
├── .env
├── .gitignore
├── static/
│   └── index.html
└── README.md
```

---