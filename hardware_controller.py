import os
import glob
from system_utils import run_command

class HardwareManager:
    def __init__(self):
        self.controller = self._get_controller()

    def _get_controller(self):
        if run_command("which nvidia-smi"):
            print("Placa de vídeo NVIDIA detectada.")
            return NvidiaController()

        for card_path in sorted(glob.glob('/sys/class/drm/card*')):
            try:
                with open(os.path.join(card_path, 'device/vendor'), 'r') as f:
                    if f.read().strip() == '0x1002':
                        hwmon_paths = glob.glob(os.path.join(card_path, 'device/hwmon/hwmon*'))
                        if hwmon_paths:
                            card_name = os.path.basename(card_path)
                            hwmon_path = hwmon_paths[0]
                            print(f"Placa de vídeo AMD detectada em '{card_name}' com hwmon '{os.path.basename(hwmon_path)}'.")
                            return AmdController(card_path, hwmon_path)
            except FileNotFoundError:
                continue
            except Exception as e:
                print(f"Erro ao verificar {card_path}: {e}")

        else:
            print("Nenhuma placa de vídeo compatível detectada.")
            return None

class NvidiaController:
    def set_fan_speed(self, speed_percent):
        run_command("nvidia-settings -a '[gpu:0]/GPUFanControlState=1'")
        run_command(f"nvidia-settings -a '[fan:0]/GPUTargetFanSpeed={speed_percent}'")

    def set_power_limit(self, limit_watts):
        run_command(f"sudo nvidia-smi -pl {limit_watts}")

    def set_core_clock_offset(self, offset_mhz):
        run_command(f"nvidia-settings -a '[gpu:0]/GPUGraphicsClockOffset[3]={offset_mhz}'")

    def set_mem_clock_offset(self, offset_mhz):
        run_command(f"nvidia-settings -a '[gpu:0]/GPUMemoryTransferRateOffset[3]={offset_mhz}'")

    def reset_settings(self):
        print("Restaurando configurações padrão da NVIDIA.")
        self.set_core_clock_offset(0)
        self.set_mem_clock_offset(0)
        
        run_command("nvidia-settings -a '[gpu:0]/GPUFanControlState=0'")
        
        try:
            default_power_limit = run_command("nvidia-smi --query-gpu=power.default_limit --format=csv,noheader,nounits").split('.')[0]
            self.set_power_limit(int(default_power_limit))
        except (ValueError, TypeError, AttributeError):
            print("Não foi possível resetar o limite de energia para o padrão.")

    def get_power_limit_range(self):
        try:
            min_limit = run_command("nvidia-smi --query-gpu=power.min_limit --format=csv,noheader,nounits").split('.')[0]
            max_limit = run_command("nvidia-smi --query-gpu=power.max_limit --format=csv,noheader,nounits").split('.')[0]
            if min_limit and max_limit:
                return int(min_limit), int(max_limit)
        except (ValueError, TypeError, AttributeError):
            return None, None
        return None, None

    def get_gpu_usage(self):
        usage = run_command("nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits")
        return f"{usage}%" if usage else "N/A"

    def get_memory_usage(self):
        try:
            total_mem_str = run_command("nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits")
            used_mem_str = run_command("nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits")
            if total_mem_str and used_mem_str:
                total_mem = int(total_mem_str)
                used_mem = int(used_mem_str)
                return f"{(used_mem / total_mem) * 100:.1f}% ({used_mem}MB / {total_mem}MB)"
        except (ValueError, TypeError):
            return "N/A"
        return "N/A"

    def get_temperature(self):
        temp = run_command("nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader,nounits")
        return int(temp) if temp and temp.isdigit() else None

class AmdController:
    def __init__(self, card_path, hwmon_path):
        self.card_path = card_path
        self.hwmon_path = hwmon_path
        self.device_path = os.path.join(card_path, "device/")

    def set_fan_speed(self, speed_percent):
        pwm_value = int((speed_percent / 100) * 255)
        
        run_command(f"echo 1 | sudo tee {self.hwmon_path}/pwm1_enable")
        run_command(f"echo {pwm_value} | sudo tee {self.hwmon_path}/pwm1")

    def set_core_clock_offset(self, offset_mhz):
        print("Controle de clock para AMD ainda não implementado.")

    def set_mem_clock_offset(self, offset_mhz):
        print("Controle de clock de memória para AMD ainda não implementado.")

    def reset_settings(self):
        print("Restaurando configurações padrão da AMD.")
        run_command(f"echo 2 | sudo tee {self.hwmon_path}/pwm1_enable")

        _min_limit, max_limit = self.get_power_limit_range()
        if max_limit:
            self.set_power_limit(max_limit)

    def get_power_limit_range(self):
        try:
            with open(f"{self.hwmon_path}/power1_cap_max") as f:
                max_limit = int(f.read().strip()) / 1_000_000
            min_limit = 10
            return min_limit, int(max_limit)
        except (FileNotFoundError, ValueError):
            return None, None

    def set_power_limit(self, limit_watts):
        limit_microwatts = int(limit_watts * 1_000_000)
        run_command(f"echo {limit_microwatts} | sudo tee {self.hwmon_path}/power1_cap")

    def get_gpu_usage(self):
        try:
            with open(f"{self.device_path}gpu_busy_percent") as f:
                usage = f.read().strip()
                return f"{usage}%"
        except FileNotFoundError:
            return "N/A"

    def get_memory_usage(self):
        try:
            with open(f"{self.device_path}mem_info_vram_used") as f:
                used_mem = int(f.read().strip()) / (1024**2)
            with open(f"{self.device_path}mem_info_vram_total") as f:
                total_mem = int(f.read().strip()) / (1024**2)
            return f"{(used_mem / total_mem) * 100:.1f}% ({used_mem:.0f}MB / {total_mem:.0f}MB)"
        except (FileNotFoundError, ValueError, ZeroDivisionError):
            return "N/A"

    def get_temperature(self):
        try:
            with open(f"{self.hwmon_path}/temp1_input") as f:
                return int(f.read().strip()) / 1000
        except (FileNotFoundError, ValueError):
            return None
