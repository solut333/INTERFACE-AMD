#!/usr/bin/python3
import json
from hardware_controller import HardwareManager
import os

def apply_saved_config():
    script_dir = os.path.dirname(os.path.realpath(__file__))
    config_file = os.path.join(script_dir, "config.json")

    try:
        with open(config_file, 'r') as f:
            settings = json.load(f)
    except FileNotFoundError:
        print("Arquivo de configuração não encontrado.")
        return

    manager = HardwareManager()
    if not manager.controller:
        print("Hardware não compatível.")
        return

    fan_speed = settings.get("fan_speed")
    core_offset = settings.get("core_clock_offset")
    mem_offset = settings.get("mem_clock_offset")
    power_limit = settings.get("power_limit")

    if fan_speed is not None:
        manager.controller.set_fan_speed(fan_speed)
        print(f"Velocidade da ventoinha definida para {fan_speed}%")

    if core_offset is not None:
        manager.controller.set_core_clock_offset(core_offset)
        print(f"Offset do clock do núcleo definido para {core_offset} MHz")

    if mem_offset is not None:
        manager.controller.set_mem_clock_offset(mem_offset)
        print(f"Offset do clock da memória definido para {mem_offset} MHz")

    if power_limit is not None:
        manager.controller.set_power_limit(power_limit)
        print(f"Limite de energia definido para {power_limit}W")

if __name__ == "__main__":
    apply_saved_config()
