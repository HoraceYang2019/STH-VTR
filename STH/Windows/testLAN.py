import subprocess

class LANConnection:
    def __init__(self, interface_name, ip_address, subnet_mask, gateway):
        self.interface_name = interface_name
        self.ip_address = ip_address
        self.subnet_mask = subnet_mask
        self.gateway = gateway

    def connect(self):
        try:
            subprocess.run(f'netsh interface ip set address "{self.interface_name}" static {self.ip_address} {self.subnet_mask} {self.gateway}', check=True)
            print(f"Configured LAN network on interface {self.interface_name} with IP {self.ip_address}")
        except subprocess.CalledProcessError as e:
            print(f"Failed to configure LAN network: {e}")

# Example usage:
lan = LANConnection(interface_name='ST_route', ip_address='10.0.0.103', subnet_mask='255.255.255.0', gateway='10.0.1.1')
lan.connect()
