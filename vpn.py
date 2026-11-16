import subprocess
import os
import threading

class Vpn():
    def __init__(self):
        rdm_auth_path = os.urandom(16).hex()
        self.auth_path = f"/dev/shm/auth_file_{rdm_auth_path}.txt"

        self.process = None

        self.condition = threading.Condition()

        self.state = "disconnected"
        self.last_error = None

        self.stop_thread_request = False
        
        self.thread = None

    def get_state(self):
        with self.condition:
            return self.state
        
    def get_last_error(self):
        with self.condition:
            return self.last_error

    def connect(self, timeout, user, password, config_file):
        with self.condition:
            if (self.state != "disconnected" or self.process is not None or
                (self.thread is not None and self.thread.is_alive())):
                raise Exception("VPN already in use")
            
            self.stop_thread_request = False
            self.state = "connecting"
            self.last_error = None

            self.thread = threading.Thread(target=self.connection_worker, args=(user, password, config_file))
            self.thread.start()

            if not self.condition.wait_for(lambda: self.state != "connecting", timeout=timeout):
                self.last_error = "timeout"
                self.stop_thread_request = True
                self.terminate_process()

        if self.last_error != None or self.state != "connected":
            self.join_timeout()

        if self.last_error == "unexpected_error":
            raise Exception("Unexpected error during VPN connection")

        with self.condition:
            return self.last_error if self.last_error is not None else self.state

    def disconnect(self): 
        with self.condition:
            if self.state == "disconnected":
                return
            self.stop_thread_request = True
            self.terminate_process()
        self.join_timeout()

    def connection_worker(self, user, password, config_file):
        try:
            #creat auth file in /dev/shm (RAM)
            with self.condition:
                fd = os.open(self.auth_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, "w") as f:
                    f.write(f"{user}\n{password}\n")

                if self.stop_thread_request:
                    self.clean_state()
                    self.condition.notify()
                    return
                
                self.process = subprocess.Popen(
                    [
                        "sudo",
                        "openvpn",
                        "--config", config_file,
                        "--auth-user-pass", self.auth_path,
                    ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                )

            while True:
                line = self.process.stdout.readline()
                with self.condition:
                    if self.stop_thread_request:
                        break
                    if not line:
                        if self.state == "connecting":
                            self.last_error = "process_exited"
                        if self.state == "connected":
                            self.last_error = "connection_lost"
                        break

                    # Détection états
                    if "AUTH_FAILED" in line:
                        self.last_error = "auth_failed"
                        break
                
                    if "Cannot resolve host address" in line:
                        self.last_error = "network_error"
                        break
                        
                    if "Initialization Sequence Completed" in line:
                        self.state = "connected"
                        self.delete_auth() 
                        self.condition.notify()

            with self.condition:
                self.terminate_process()
                self.clean_state()
                self.condition.notify()

        except Exception:
            with self.condition:
                self.last_error = "unexpected_error"
                try:
                    self.terminate_process()
                finally:
                    self.clean_state()
                    self.condition.notify()


    def terminate_process(self):
        self.state = "disconnecting"
        self.delete_auth()
        if self.process is None:
            return
        self.process.terminate()
        try:
            self.process.wait(timeout=5)
        except Exception:
            self.process.kill()
            self.process.wait(timeout=5)  
        
    def clean_state(self):
        self.delete_auth()
        self.process = None
        self.state = "disconnected"

    def delete_auth(self):
        if os.path.exists(self.auth_path):
            os.remove(self.auth_path)

    def join_timeout(self, timeout=10):
        self.thread.join(timeout)
        if self.thread.is_alive():
            raise Exception("VPN thread did not terminate in time")
