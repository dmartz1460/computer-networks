.PHONY: build run-server run-client test clean

SERVER_SOURCES := $(wildcard src/server/*.java)
SERVER_CLASSES := build/server

build:
	mkdir -p $(SERVER_CLASSES)
	javac -d $(SERVER_CLASSES) $(SERVER_SOURCES)

run-server: build
	java -cp $(SERVER_CLASSES) server.BulletinServer --port 5000

run-client:
	python src/client/bulletin_client.py

test: build
	python -m unittest discover -s test -p "test_*.py"

clean:
	rm -rf build
