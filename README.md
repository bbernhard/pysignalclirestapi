Small python library for the [Signal Cli REST API](https://github.com/bbernhard/signal-cli-rest-api)

### Quickstart
If you have set up the REST API already, you can start sending and receiving messages in Python!

Intialize the client
```
# Seperated for clarity
SERVER = "http://localhose:8080" # Your server address and port
SERVER_NUMBER ="+123456789" # The phone number you registered with the API


signal = SignalCliRestApi(SERVER,SERVER_NUMBER) 
```

Send a message
```
myMessage = "Hello World" # Your message
myFriendSteve = +987654321 # The number you want to message (must be registered with Signal)

sendMe = signal.send_message(message=myMessage,recipients=myFriendSteve)

```
receive messages
```
myMessages = signal.receive(send_read_receipts=True) # Send read receipts so everyone knows you have seen their message
```
