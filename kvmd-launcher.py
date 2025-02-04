import multiprocessing
import os
import sys
from kvmd.apps.kvmd import main as kvmd_main

import fileinput

# 文件路径
file_path = '_internal/kvmd_data/etc/kvmd/kvmd_data/etc/kvmd/override.yaml'

# 使用fileinput.input进行原地编辑


def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def replace_streamer_command(override_config_path):
    lines_to_replace = [
        "            - \"C:/Users/mofen/miniconda3/python.exe\"\n",
        "            - \"ustreamer-win/ustreamer-win.py\"\n"
    ]
    new_line = "            - \"ustreamer-win.exe\"\n"

    with open(override_config_path, 'r', encoding='utf-8') as file:
        lines = file.readlines()

    with open(override_config_path, 'w', encoding='utf-8') as file:
        i = 0
        while i < len(lines):
            if lines[i] in lines_to_replace:
                if i + 1 < len(lines) and lines[i + 1] == lines_to_replace[1]:
                    file.write(new_line)
                    i += 2
                    continue
            file.write(lines[i])
            i += 1

def start():
    main_config_path = resource_path('kvmd_data/etc/kvmd/main.yaml')
    override_config_path = resource_path('kvmd_data/etc/kvmd/override.yaml')
    flag_path = resource_path('kvmd_data/run_flag')

    

    if not os.path.exists(flag_path):
        with fileinput.input(override_config_path, inplace=True) as file:
            for line in file:
                updated_line = line.replace('kvmd_data/', '_internal/kvmd_data/')
                print(updated_line, end='')
        with open(flag_path, 'w') as flag_file:
            flag_file.write("1")

        replace_streamer_command(override_config_path)

    custom_argv = [
        'kvmd',
        '-c',main_config_path,
        '--run'
    ]
    kvmd_main(argv=custom_argv)

if __name__ == '__main__':
    multiprocessing.freeze_support()
    start()