package main

import (
	"log"
	"net/http"
	"os"
	"time"

	"github.com/Uranury/IotGo/sensors"
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

func main() {
	if err := godotenv.Load(); err != nil {
		log.Println("No .env file found, using environment variables")
	}

	// Get environment variables with defaults
	influxURL := getEnv("INFLUX_URL", "http://localhost:8086")
	influxToken := getEnv("INFLUX_TOKEN", "")
	influxOrg := getEnv("INFLUX_ORG", "")
	influxBucket := getEnv("INFLUX_BUCKET", "")

	dhtPin := getEnv("DHT_PIN", "4")

	// Initialize InfluxDB client
	influxClient = influxdb2.NewClient(influxURL, influxToken)
	writeAPI = influxClient.WriteAPI(influxOrg, influxBucket)
	defer influxClient.Close()

	dht22, err := sensors.NewDHT22(dhtPin)
	if err != nil {
		log.Fatalf("Failed to initialize DHT22: %v", err)
	}
	defer dht22.Close()

	// Initialize all sensors
	sensors := []sensors.Sensor{
		dht22,
		&sensors.BMP280{Address: 0x76},
		&sensors.GY32{Address: 0x23},
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
func readAllSensors(sensors []sensors.Sensor) {
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

func writeToInflux(data *sensors.SensorData) {
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

func broadcastToClients(data *sensors.SensorData) {
	for client := range clients {
		if err := client.WriteJSON(data); err != nil {
			log.Println("WebSocket write error:", err)
			client.Close()
			delete(clients, client)
		}
	}
}
