package sensors

import (
	"fmt"
	"time"

	"periph.io/x/conn/v3/gpio"
	"periph.io/x/conn/v3/gpio/gpioreg"
	"periph.io/x/host/v3"
)

type DHT22 struct {
	Pin     string
	gpioPin gpio.PinIO
}

func NewDHT22(pin string) (*DHT22, error) {
	// Initialize periph.io
	if _, err := host.Init(); err != nil {
		return nil, fmt.Errorf("failed to initialize periph: %w", err)
	}

	// Get the GPIO pin
	p := gpioreg.ByName(pin)
	if p == nil {
		return nil, fmt.Errorf("failed to find pin %s", pin)
	}

	return &DHT22{
		Pin:     pin,
		gpioPin: p,
	}, nil
}

func (d *DHT22) Name() string {
	return "DHT22"
}

func (d *DHT22) Read() (*SensorData, error) {
	temperature, humidity, err := d.readDHT22()
	if err != nil {
		return nil, err
	}

	return &SensorData{
		SensorType: "dht22",
		Fields: map[string]float64{
			"temperature": temperature,
			"humidity":    humidity,
		},
		Timestamp: time.Now(),
	}, nil
}

func (d *DHT22) Close() {
	// No cleanup needed for periph.io
}

// readDHT22 reads temperature and humidity from DHT22 sensor
func (d *DHT22) readDHT22() (temperature, humidity float64, err error) {
	// DHT22 protocol implementation
	data := make([]byte, 5)

	// Send start signal
	if err := d.gpioPin.Out(gpio.Low); err != nil {
		return 0, 0, fmt.Errorf("failed to set pin low: %w", err)
	}
	time.Sleep(1 * time.Millisecond)

	if err := d.gpioPin.Out(gpio.High); err != nil {
		return 0, 0, fmt.Errorf("failed to set pin high: %w", err)
	}
	time.Sleep(30 * time.Microsecond)

	// Switch to input mode
	if err := d.gpioPin.In(gpio.PullUp, gpio.BothEdges); err != nil {
		return 0, 0, fmt.Errorf("failed to set pin to input: %w", err)
	}

	// Read response
	transitions := make([]time.Duration, 0, 100)
	lastTime := time.Now()
	lastLevel := d.gpioPin.Read()

	// Wait for response with timeout
	timeout := time.After(200 * time.Millisecond)
	for {
		select {
		case <-timeout:
			return 0, 0, fmt.Errorf("timeout waiting for sensor response")
		default:
			level := d.gpioPin.Read()
			if level != lastLevel {
				now := time.Now()
				transitions = append(transitions, now.Sub(lastTime))
				lastTime = now
				lastLevel = level

				if len(transitions) >= 83 {
					goto parseData
				}
			}
		}
	}

parseData:
	// Parse the data bits
	if len(transitions) < 83 {
		return 0, 0, fmt.Errorf("insufficient data: got %d transitions, need 83", len(transitions))
	}

	// Skip the first 3 transitions (response signal)
	bitIndex := 0
	for i := 3; i < len(transitions) && bitIndex < 40; i += 2 {
		if i+1 >= len(transitions) {
			break
		}

		// If high pulse is longer than 50us, it's a 1, otherwise 0
		highDuration := transitions[i+1]
		bit := 0
		if highDuration > 50*time.Microsecond {
			bit = 1
		}

		byteIndex := bitIndex / 8
		bitOffset := 7 - (bitIndex % 8)
		data[byteIndex] |= byte(bit << bitOffset)
		bitIndex++
	}

	// Verify checksum
	checksum := data[0] + data[1] + data[2] + data[3]
	if checksum != data[4] {
		return 0, 0, fmt.Errorf("checksum mismatch: expected %d, got %d", data[4], checksum)
	}

	// Calculate humidity (first 2 bytes)
	humidityRaw := uint16(data[0])<<8 | uint16(data[1])
	humidity = float64(humidityRaw) / 10.0

	// Calculate temperature (last 2 bytes)
	temperatureRaw := uint16(data[2]&0x7F)<<8 | uint16(data[3])
	temperature = float64(temperatureRaw) / 10.0

	// Check if temperature is negative
	if data[2]&0x80 != 0 {
		temperature = -temperature
	}

	return temperature, humidity, nil
}
