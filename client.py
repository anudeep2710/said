import socket

def main():
    host = "10.113.22.95"  # Change this to match the server's IP if needed
    port = 12345

    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect((host, port))

    print("[CONNECTED] Connected to the server.")

    while True:
        message = input("Enter message to send: ")
        if not message:
            break

        client.send(message.encode("utf-8"))
        response = client.recv(1024).decode("utf-8")
        print(f"[SERVER RESPONSE] {response}")

        cont = input("Do you want to continue? (y/n): ")
        if cont.lower() != "y":
            break

    client.close()
    print("[DISCONNECTED] Connection closed.")

if _name_ == "_main_":
    main()