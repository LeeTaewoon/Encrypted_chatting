import socket
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_OAEP
import threading
import time
import queue
import sys
import select

# 메시지 큐 생성
message_queue = queue.Queue()

def receive_messages(client_socket, private_key):
    while True:
        try:
            # 메시지 수신
            data = client_socket.recv(2048)
            if not data:
                break
            message = data.decode()
            message_queue.put(message)  # 메시지를 큐에 저장

            # 암호화된 메시지인지 확인하고 복호화
            if ":" in message:
                sender_id, encrypted_message_hex = message.split(":", 1)
                encrypted_message = bytes.fromhex(encrypted_message_hex)

                # 개인 키로 복호화
                rsa_cipher = PKCS1_OAEP.new(RSA.import_key(private_key))
                try:
                    decrypted_message = rsa_cipher.decrypt(encrypted_message)
                    print(f"\n{sender_id}: {decrypted_message.decode()}\nyou: ", end="")
                except Exception as e:
                    print(f"\n복호화 실패: {e}")
        except Exception as e:
            #print(f"메시지 수신 중 오류: {e}")
            break

def non_blocking_input(prompt):
    """비차단 입력 대기 함수"""
    print(prompt, end='', flush=True)
    while True:
        if sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
            return input()

def client():
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.connect(('localhost', 14576))

    # RSA 키 생성
    key = RSA.generate(2048)
    private_key = key.export_key().decode()
    public_key = key.publickey().export_key().decode()

    # 서버에 공개 키 전송
    print(client_socket.recv(2048).decode())
    client_socket.send(public_key.encode())
    print("공개 키 전송 완료")

    # 메시지 수신 스레드 시작
    threading.Thread(target=receive_messages, args=(client_socket, private_key), daemon=True).start()

    receiver_id = None  # 처음에는 수신자 ID가 없음
    first_connection = True  # 처음 연결 시에만 ID 목록을 출력하도록 설정

    while True:
        # 수신된 메시지 출력
        while not message_queue.empty():
            message_queue.get()

        # 연결된 클라이언트 ID 요청
        client_socket.send("GET_CLIENT_IDS".encode())
        while message_queue.empty():
            time.sleep(0.1)  # 메시지가 올 때까지 대기
        available_ids = message_queue.get()

        # 서버로부터 받은 ID 확인
        if available_ids == "NO_OTHER_CLIENTS":
            print("현재 다른 연결된 클라이언트가 없습니다.")
            time.sleep(5)  # 5초 대기 후 재시도
            continue

        if first_connection:
            # 첫 연결 시에만 ID 목록 출력
            print(f"서버로부터 받은 ID 목록: {available_ids}")
            first_connection = False  # 이후부터는 출력하지 않음

        # 수신자 ID 선택
        if receiver_id is None:
            receiver_id_input = non_blocking_input("수신자 ID를 선택하세요: ")
            if receiver_id_input not in available_ids.split(","):
                print("잘못된 ID입니다. 다시 시도하세요.")
                continue
            receiver_id = int(receiver_id_input)

            # 서버에 수신자의 공개 키 요청
            client_socket.send(f"SET_RECEIVER_ID:{receiver_id}".encode())
            while message_queue.empty():
                time.sleep(0.1)  # 메시지가 올 때까지 대기
            confirmation = message_queue.get()
            print(confirmation)

        # 수신자의 공개 키 가져오기
        client_socket.send(f"GET_PUBLIC_KEY:{receiver_id}".encode())
        while message_queue.empty():
            time.sleep(0.1)  # 메시지가 올 때까지 대기
        receiver_public_key_pem = message_queue.get()

        if receiver_public_key_pem.startswith("ERROR"):
            print(f"오류: {receiver_public_key_pem}")
            continue

        # 메시지 암호화 및 전송
        message = input("you: ").encode()
        rsa_cipher = PKCS1_OAEP.new(RSA.import_key(receiver_public_key_pem))
        encrypted_message = rsa_cipher.encrypt(message)
        client_socket.send(f"{receiver_id}:{encrypted_message.hex()}".encode())



if __name__ == "__main__":
    client()