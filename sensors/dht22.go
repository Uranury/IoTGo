package sensors

import (
	"time"

	"github.com/MichaelS11/go-dht"
)

type DHT22 struct {
	Pin  string
	Dht  *dht.DHT
	Stop chan struct{}
}

func NewDHT22(pin string) (*DHT22, error) {
	d := &DHT22{
		Pin:  pin,
		Stop: make(chan struct{}),
	}

	// Initialize the DHT sensor
	var err error
	d.Dht, err = dht.NewDHT(pin, dht.Fahrenheit, "")
	if err != nil {
		return nil, err
	}

	return d, nil
}

func (d *DHT22) Name() string {
	return "DHT22"
}

func (d *DHT22) Read() (*SensorData, error) {
	// Read humidity and temperature
	humidity, temperature, err := d.Dht.ReadRetry(11)
	if err != nil {
		return nil, err
	}

	// Convert Fahrenheit to Celsius
	temperatureC := (temperature - 32) * 5 / 9

	return &SensorData{
		SensorType: "dht22",
		Fields: map[string]float64{
			"temperature": temperatureC,
			"humidity":    humidity,
		},
		Timestamp: time.Now(),
	}, nil
}

func (d *DHT22) Close() {
}
