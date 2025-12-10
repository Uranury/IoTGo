# Clone the repo (if from GitHub)
git clone <your-repo-url>
cd IoTGo

# Install system dependencies first
sudo apt-get update
sudo apt-get install -y liblgpio-dev python3-dev swig

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python packages
pip install -r requirements.txt

# Run the application
python3 main.py
```

## Your Project Structure Should Look Like:
```
IoTGo/
├── main.py
├── sensors.py
├── requirements.txt
├── .env (your environment variables)
├── .gitignore
├── static/
│   └── index.html
└── README.md (optional but recommended)