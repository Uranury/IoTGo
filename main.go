package main

import (
	"log"
	"math/rand"
	"net/http"
	"os"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/gorilla/websocket"
	influxdb2 "github.com/influxdata/influxdb-client-go/v2"
	"github.com/influxdata/influxdb-client-go/v2/api"
	"github.com/joho/godotenv"
)

var (
	upgrader = websocket.Upgrader{
		CheckOrigin: func(r *http.Request) bool { return true },
	}
	influxClient influxdb2.Client
	writeAPI     api.WriteAPI
	clients      = make(map[*websocket.Conn]bool)
)

// SensorData is the unified data structure for all sensors
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

// DHT11 sensor implementation
type DHT11 struct {
	pin int
}

func (d *DHT11) Name() string {
	return "DHT11"
}

func (d *DHT11) Read() (*SensorData, error) {
	// Simulate reading from GPIO - replace with actual GPIO library
	temperature := 20.0 + rand.Float64()*10.0
	humidity := 40.0 + rand.Float64()*40.0

	return &SensorData{
		SensorType: "dht11",
		Fields: map[string]float64{
			"temperature": temperature,
			"humidity":    humidity,
		},
		Timestamp: time.Now(),
	}, nil
}

// BMP280 sensor implementation
type BMP280 struct {
	address byte
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

// GY32 (BH1750) light sensor implementation
type GY32 struct {
	address byte
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

func main() {
	if err := godotenv.Load(); err != nil {
		log.Println("No .env file found, using environment variables")
	}

	// Get environment variables with defaults
	influxURL := getEnv("INFLUX_URL", "http://localhost:8086")
	influxToken := getEnv("INFLUX_TOKEN", "")
	influxOrg := getEnv("INFLUX_ORG", "")
	influxBucket := getEnv("INFLUX_BUCKET", "")

	// Initialize InfluxDB client
	influxClient = influxdb2.NewClient(influxURL, influxToken)
	writeAPI = influxClient.WriteAPI(influxOrg, influxBucket)
	defer influxClient.Close()

	// Initialize all sensors
	sensors := []Sensor{
		&DHT11{pin: 4},
		&BMP280{address: 0x76},
		&GY32{address: 0x23},
	}

	// Initialize Gin
	r := gin.Default()

	// Serve static files from the "static" directory
	r.Static("/static", "./static")

	// Serve index.html at root
	r.GET("/", func(c *gin.Context) {
		c.File("./static/index.html")
	})

	// WebSocket endpoint
	r.GET("/ws", handleWebSocket)

	// Start sensor reading goroutine
	go readAllSensors(sensors)

	log.Println("Server starting on :8080")
	log.Println("Monitoring sensors:", len(sensors))
	for _, sensor := range sensors {
		log.Printf("  - %s", sensor.Name())
	}

	r.Run(":8080")
}

func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	log.Println("Environment variable %s not set", key)
	return defaultValue
}

// readAllSensors reads from all sensors periodically
func readAllSensors(sensors []Sensor) {
	ticker := time.NewTicker(2 * time.Second)
	defer ticker.Stop()

	for range ticker.C {
		for _, sensor := range sensors {
			data, err := sensor.Read()
			if err != nil {
				log.Printf("Error reading %s: %v", sensor.Name(), err)
				continue
			}

			log.Printf("%s: %+v", sensor.Name(), data.Fields)

			// Write to InfluxDB
			writeToInflux(data)

			// Broadcast to WebSocket clients
			broadcastToClients(data)
		}
	}
}

func writeToInflux(data *SensorData) {
	p := influxdb2.NewPointWithMeasurement("sensor_data").
		AddTag("sensor", data.SensorType).
		SetTime(data.Timestamp)

	// Add all fields dynamically
	for key, value := range data.Fields {
		p.AddField(key, value)
	}

	writeAPI.WritePoint(p)
}

func handleWebSocket(c *gin.Context) {
	conn, err := upgrader.Upgrade(c.Writer, c.Request, nil)
	if err != nil {
		log.Println("WebSocket upgrade error:", err)
		return
	}
	defer conn.Close()

	clients[conn] = true
	defer delete(clients, conn)

	log.Printf("Client connected. Total clients: %d", len(clients))

	// Keep connection alive
	for {
		if _, _, err := conn.ReadMessage(); err != nil {
			log.Printf("Client disconnected. Total clients: %d", len(clients)-1)
			break
		}
	}
}

func broadcastToClients(data *SensorData) {
	for client := range clients {
		if err := client.WriteJSON(data); err != nil {
			log.Println("WebSocket write error:", err)
			client.Close()
			delete(clients, client)
		}
	}
}
