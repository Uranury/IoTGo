package sensors

import (
	"math/rand/v2"
	"time"
)

type BMP280 struct {
	Address byte
}

func (b *BMP280) Name() string {
	return "BMP280"
}

func (b *BMP280) Read() (*SensorData, error) {
	// Simulate reading from I2C - replace with actual I2C library
	pressure := 1000.0 + rand.Float64()*50.0
	temperature := 20.0 + rand.Float64()*10.0

	return &SensorData{
		SensorType: "bmp280",
		Fields: map[string]float64{
			"pressure":    pressure,
			"temperature": temperature,
		},
		Timestamp: time.Now(),
	}, nil
}
