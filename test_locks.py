import threading
from time import sleep

i = 1

lock = threading.Lock()


def update_data():
    global i
    while True:
        with lock:
            i += 1
            sleep(10)
        sleep(0.1)


update_data_thread = threading.Thread(target=update_data, args=(), daemon=True)

update_data_thread.start()

while True:
    with lock:
        print(i)
        sleep(0.1)
    sleep(0.1)