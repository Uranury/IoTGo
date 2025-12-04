FROM golang:1.25.1-alpine AS builder

WORKDIR /app

# Install build dependencies for CGO
RUN apk add --no-cache gcc musl-dev linux-headers

# Copy go mod files
COPY go.mod go.sum ./
RUN go mod download

# Copy source code
COPY . .

# Build with CGO enabled for GPIO access
RUN CGO_ENABLED=1 GOOS=linux go build -o sensor-app .

# Final stage
FROM alpine:latest

RUN apk --no-cache add ca-certificates

WORKDIR /root/

# Copy the binary from builder
COPY --from=builder /app/sensor-app .

# Copy static files
COPY --from=builder /app/static ./static

EXPOSE 8080

CMD ["./sensor-app"]