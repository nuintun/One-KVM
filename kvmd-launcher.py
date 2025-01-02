from kvmd.apps.kvmd import main as kvmd_main
def start():
    custom_argv = [
        'kvmd',
        '-c', 'kvmd_data/etc/kvmd/main.yaml',
        '--run'
    ]
    kvmd_main(argv=custom_argv)

if __name__ == '__main__':
    start()