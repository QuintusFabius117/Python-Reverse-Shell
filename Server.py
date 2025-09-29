import socket



host = '0.0.0.0'
port = 10112

# Get all connected up

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind((host, port))
server.listen()
print(f'Listening on {host}:{port}')
client, address = server.accept()
print(f'Connected to {address}')

def send():
    while True:
        command = input("$ > ") # Open with $ > whateveryouinput
        if not command: # If you just press enter without text
            continue
        client.send(command.encode()) # Sends off whatever you typed

        if command.lower() == 'exit': # Breaks
            break

        data = client.recv(65536).decode() # Recieves printed message from client
        print(data, end="") # end prevents unnecessary \n new lines from printing

send()
