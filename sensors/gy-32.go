package sensors

import (
	"math/rand/v2"
	"time"
)

type GY32 struct {
	Address byte
}

func (g *GY32) Name() string {
	return "GY32"
}

func (g *GY32) Read() (*SensorData, error) {
	// Simulate reading from I2C - replace with actual I2C library
	light := 100.0 + rand.Float64()*400.0

	return &SensorData{
		SensorType: "gy32",
		Fields: map[string]float64{
			"light": light,
		},
		Timestamp: time.Now(),
	}, nil
}
