import argparse
import cv2
import logging
import platform
from mjpeg_stream import MjpegStream

def configure_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger(__name__)

def get_windows_cameras(logger):
    from win32com.client import Dispatch
    devices = []
    try:
        wmi = Dispatch("WbemScripting.SWbemLocator")
        service = wmi.ConnectServer(".", "root\\cimv2")
        items = service.ExecQuery("SELECT * FROM Win32_PnPEntity WHERE (PNPClass = 'Image' OR PNPClass = 'Camera')")
        
        for item in items:
            devices.append({
                'name': item.Name,
                'device_id': item.DeviceID
            })
            logger.info(f"Found camera device: {item.Name}")
    except Exception as e:
        logger.error(f"Error enumerating camera devices: {str(e)}")
    return devices

def test_camera(index, logger):
    try:
        cap = cv2.VideoCapture(index, cv2.CAP_DSHOW if platform.system() == "Windows" else cv2.CAP_ANY)
        if cap.isOpened():
            ret, _ = cap.read()
            cap.release()
            return ret
    except Exception as e:
        logger.debug(f"Error testing camera {index}: {str(e)}")
    return False

def find_camera_by_name(camera_name, logger):
    if platform.system() != "Windows":
        logger.warning("Finding camera by name is only supported on Windows")
        return None
        
    devices = get_windows_cameras(logger)
    for device in devices:
        if camera_name.lower() in device['name'].lower():
            # Try to find an available index
            for i in range(5):  # Usually no more than 5 devices
                if test_camera(i, logger):
                    logger.info(f"Found matching camera '{device['name']}' at index {i}")
                    return i
    return None

def get_first_available_camera(logger):
    for i in range(5):
        if test_camera(i, logger):
            return i
    return None

def parse_arguments():
    parser = argparse.ArgumentParser(description='MJPEG Stream Demonstration')
    device_group = parser.add_mutually_exclusive_group()
    device_group.add_argument('--device', type=int, help='Camera device index')
    device_group.add_argument('--device-name', type=str, help='Camera device name (only supported on Windows)')
    parser.add_argument('--resolution', type=str, default='640x480', help='Video resolution (e.g., 640x480)')
    parser.add_argument('--quality', type=int, default=100, help='JPEG quality (1-100)')
    parser.add_argument('--fps', type=int, default=30, help='Target FPS')
    parser.add_argument('--host', type=str, default='localhost', help='Server address')
    parser.add_argument('--port', type=int, default=8000, help='Server port')
    args = parser.parse_args()

    if args.quality < 1 or args.quality > 100:
        raise ValueError("Quality must be between 1 and 100.")
    if args.fps <= 0:
        raise ValueError("FPS must be greater than 0.")
    try:
        width, height = map(int, args.resolution.split('x'))
    except ValueError:
        raise ValueError("Resolution must be in the format WIDTHxHEIGHT (e.g., 640x480).")

    args.width = width
    args.height = height

    return args

def main():
    logger = configure_logging()
    args = parse_arguments()
    device_index = None
    
    if args.device_name:
        device_index = find_camera_by_name(args.device_name, logger)
        if device_index is None:
            logger.error(f"No available camera found with a name containing '{args.device_name}'")
            return
    elif args.device is not None:
        if test_camera(args.device, logger):
            device_index = args.device
        else:
            logger.warning(f"The specified device index {args.device} is not available")
    
    if device_index is None:
        device_index = get_first_available_camera(logger)
        if device_index is None:
            logger.error("No available camera devices were found")
            return
        logger.info(f"Using the first available camera device (index: {device_index})")

    # Initialize the camera
    try:
        cap = cv2.VideoCapture(device_index, cv2.CAP_DSHOW)
            
        if not cap.isOpened():
            logger.error(f"Unable to open camera {device_index}")
            return

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
        cap.set(cv2.CAP_PROP_FRAME_COUNT, args.fps)
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M','J','P','G'))
        actual_width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        actual_height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        if actual_width != args.width or actual_height != args.height:
            logger.warning(f"Actual resolution ({actual_width}x{actual_height}) does not match requested resolution ({args.width}x{args.height})")

        ret, _ = cap.read()
        if not ret:
            logger.error("Unable to read video frames from the camera")
            cap.release()
            return

    except Exception as e:
        logger.error(f"Error initializing the camera: {str(e)}")
        if 'cap' in locals():
            cap.release()
        return

    # Create and start the video stream
    try:
        stream = MjpegStream(
            name="stream",
            size=(int(actual_width), int(actual_height)),
            quality=args.quality,
            fps=args.fps,
            host=args.host,
            port=args.port,
            device_name=args.device_name or f"Camera {device_index}",
            log_requests=False
        )
        stream.start()
        logger.info(f"Video stream started: http://{args.host}:{args.port}/stream")

        while True:
            ret, frame = cap.read()
            if not ret:
                logger.error("Unable to read video frames")
                break

            stream.set_frame(frame)

    except KeyboardInterrupt:
        logger.info("User interrupt")
    finally:
        logger.info("Cleaning up resources...")
        stream.stop()
        cap.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()