import RPi.GPIO as GPIO

GPIO.setmode(GPIO.BCM)
GPIO.setup(2, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(3, GPIO.IN, pull_up_down=GPIO.PUD_UP)

print("GPIO2:", GPIO.input(2))
print("GPIO3:", GPIO.input(3))

GPIO.cleanup()
