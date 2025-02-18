""" Telnet Shell """
# pylint: disable=line-too-long
import time
import base64

from typing import Union
from telnetlib import Telnet


WGET = "(wget http://master.dl.sourceforge.net/project/aqarahub/{0}?viasf=1 " \
       "-O /data/bin/{1} && chmod +x /data/bin/{1})"

CHECK_SOCAT = "(md5sum /data/socat | grep 92b77e1a93c4f4377b4b751a5390d979)"
DOWNLOAD_SOCAT = "(wget -O /data/socat http://pkg.simple-ha.ru/mipsel/socat && chmod +x /data/socat)"
RUN_SOCAT_BT_IRDA = "/data/socat tcp-l:8888,reuseaddr,fork /dev/ttyS2"
RUN_SOCAT_ZIGBEE = "/data/socat tcp-l:8888,reuseaddr,fork /dev/ttyS1"

HA_MASTER2MQTT = "(ha_master -H -r /lib/libha_ir_m2.so -a /lib/libha_auto.so -g /lib/libha_energy.so | awk '/%s/{print $0;fflush()}' | mosquitto_pub -t log/ha_master -l &)"
HA_BLE2MQTT = "(ha_ble | awk '{print $0;fflush();}' | mosquitto_pub -t log/ha_ble -l &)"


class TelnetShell(Telnet):
    """ Telnet Shell """
    _aqara_property = False
    _suffix = "# "
    # pylint: disable=unsubscriptable-object

    def __init__(self, host: str, password=None, device_name=None):
        super().__init__(host, timeout=5)
        login_name = 'admin'
        if (device_name and any(
                name in device_name for name in ['g2h', 'e1', 'g3'])):
            self._aqara_property = True
            login_name = 'root'
        self.read_until(b"login: ", timeout=10)
        if (device_name and any(
                name in device_name for name in ['e1', 'g3'])):
            self._suffix = "/ # "
            if any(name in device_name for name in ['e1', 'g3']):
                password = '\n'
        if password:
            command = "{}\n".format(login_name)
            self.write(command.encode())
            self.read_until(b"Password: ", timeout=10)
            self.run_command(password)
        else:
            self.run_command(login_name)
        if device_name and 'e1' in device_name:
            self.read_until(b"\r\n/ # ", timeout=30)
        self.run_command("stty -echo")
        if 'g3' in device_name:
            self.run_command("cd /")
#        self._suffix = "# "
#        self.run_command("export PS1='# '")

    def run_command(self, command: str, as_bytes=False) -> Union[str, bytes]:
        """Run command and return it result."""
        # pylint: disable=broad-except
        try:
            self.write(command.encode() + b"\n")
            suffix = "\r\n{}".format(self._suffix)
            raw = self.read_until(suffix.encode(), timeout=30)
        except Exception:
            raw = b''
        return raw if as_bytes else raw.decode()

    def check_bin(self, filename: str, md5: str, url=None) -> bool:
        """Check binary md5 and download it if needed."""
        # used * for development purposes
        if url:
            self.run_command(WGET.format(url, filename))
            return self.check_bin(filename, md5)
        elif md5 in self.run_command("md5sum /data/bin/{}".format(filename)):
            return True
        else:
            return False

    def run_basis_cli(self, command: str, as_bytes=False) -> Union[str, bytes]:
        """Run command and return it result."""
        command = "basis_cli " + command
        self.write(command.encode() + b"\n")
        self.read_until(self._suffix.encode())
        self.read_until(self._suffix.encode())

    def file_exist(self, filename: str) -> bool:
        """ check file exit """
        raw = self.run_command("ls -al {}".format(filename))
        time.sleep(.1)
        if "No such" not in str(raw):
            return True
        return False

    def run_public_mosquitto(self):
        """ run mosquitto as public """
        if self.file_exist("/data/bin/mosquitto"):
            self.run_command("killall mosquitto")
            time.sleep(.5)
            self.run_command("/data/bin/mosquitto -d")
            time.sleep(.5)

    def check_public_mosquitto(self) -> bool:
        """ get processes list """
        raw = self.run_command("mosquitto")
        if "Binding listener to interface" in raw:
            return False
        return True

    def get_running_ps(self) -> str:
        """ get processes list """
        return self.run_command("ps")

    def redirect_ha_master2mqtt(self, pattern: str):
        """ redirect ha_master logs to mqtt """
        self.run_command("killall ha_master")
        time.sleep(.1)
        self.run_command(HA_MASTER2MQTT % pattern)

    def redirect_ha_ble2mqtt(self):
        """ redirect ha_ble logs to mqtt """
        self.run_command("killall ha_ble")
        time.sleep(.1)
        self.run_command(HA_BLE2MQTT)

    def read_file(self, filename: str, as_base64=False, with_newline=True):
        """ read file content """
        # pylint: disable=broad-except
        try:
            if as_base64:
                command = "cat {} | base64\n".format(filename)
                self.write(command.encode())
                raw = self.read_until(self._suffix.encode()).decode()
                if not with_newline:
                    raw = self.read_until(self._suffix.encode()).decode()
                return base64.b64decode(raw)
            command = "cat {}\n".format(filename)
            self.write(command.encode())
            ret = self.read_until(self._suffix.encode()).decode()
            if not with_newline:
                ret = self.read_until(self._suffix.encode()).decode()
            if ret.endswith(self._suffix):
                ret = "".join(ret.rsplit(self._suffix, 1))
            return ret.strip("\n")
        except Exception:
            return ''

    def get_prop(self, property_value: str):
        """ get property """
        # pylint: disable=broad-except
        try:
            if self._aqara_property:
                command = "agetprop {}\n\r".format(property_value)
            else:
                command = "getprop {}\n\r".format(property_value)
            ret = self.run_command(command)
            if ret.endswith(self._suffix):
                ret = "".join(ret.rsplit(self._suffix, 1))
            if ret.startswith(self._suffix):
                ret = ret.replace(self._suffix, "", 1)
            return ret.replace("\r", "").replace("\n", "")
        except Exception:
            return ''

    def set_prop(self, property_value: str, value: str):
        """ set property """
        if self._aqara_property:
            command = "asetprop {} {}\n".format(property_value, value)
        else:
            command = "setprop {} {}\n".format(property_value, value)
        self.write(command.encode() + b"\n")
        self.read_until(self._suffix.encode())
        self.read_until(self._suffix.encode())

    def get_version(self):
        """ get gateway version """
        return self.get_prop("ro.sys.fw_ver")

    def set_audio_volume(self, value):
        """ set gateway audio volume """
        if value > 100:
            value = 100
        command = "-sys -v {}".format(value)
        raw = self.run_basis_cli(command)
        return raw[raw.find(">>>") + 4:]

    def get_token(self):
        """ get gateway token """
        filename = "/data/miio/device.token"
        if self.file_exist(filename):
            return self.read_file(filename).rstrip().encode().hex()
        return None
