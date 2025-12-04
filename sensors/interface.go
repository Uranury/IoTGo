package sensors

import "time"

type SensorData struct {
	SensorType string             `json:"sensor_type"`
	Fields     map[string]float64 `json:"fields"`
	Timestamp  time.Time          `json:"timestamp"`
}

// Sensor interface that all sensors must implement
type Sensor interface {
	Read() (*SensorData, error)
	Name() string
}
