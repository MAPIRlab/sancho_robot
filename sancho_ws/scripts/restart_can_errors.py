#!/usr/bin/env python3
import can
import time
import logging
import sys

# Configuración de logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(levelname)s: %(message)s')

# CAN IDs según manual
ID_STATUS      = 0x211  # System Status Feedback
ID_MOTION_FB   = 0x221  # Motion Control Feedback (e-stop bit)
ID_CLEAR_ERROR = 0x423  # Clear system errors
ID_SET_CMD     = 0x421  # Set Command Control Mode

# Mensajes CAN predefinidos
msg_clear_error = can.Message(arbitration_id=ID_CLEAR_ERROR, data=[0x00], is_extended_id=False)
msg_set_cmd     = can.Message(arbitration_id=ID_SET_CMD,     data=[0x01], is_extended_id=False)

def open_bus(channel='can0', bitrate=500000):
    """Intenta abrir el bus CAN y devuelve el objeto Bus."""
    try:
        bus = can.interface.Bus(channel=channel, bustype='socketcan', bitrate=bitrate)
        logging.info(f"Bus CAN '{channel}' abierto a {bitrate} bps")
        return bus
    except can.CanError as e:
        logging.error(f"No se pudo abrir el bus CAN '{channel}': {e}")
        sys.exit(1)

def wait_for_bus_up(bus, timeout=5.0):
    """Espera hasta que lleguen tramas o expira el timeout."""
    start = time.time()
    logging.info("Esperando tráfico CAN...")
    while time.time() - start < timeout:
        msg = bus.recv(timeout=1.0)
        if msg:
            logging.info("Tráfico CAN detectado.")
            return
    logging.error("No llega tráfico CAN en %.1f s, verifica conexiones.", timeout)
    sys.exit(1)

def check_emergency_released(bus):
    """Espera a que el e-stop se libere (bit de e-stop = 0)."""
    logging.info("Comprobando que el e-stop esté liberado...")
    while True:
        msg = bus.recv(timeout=1.0)
        if msg and msg.arbitration_id == ID_MOTION_FB:
            estop = bool(msg.data[7] & 0x80)  # bit7 = e-stop
            if not estop:
                logging.info("E-stop liberado.")
                return
            logging.debug("E-stop aún presionado, esperando...")
        time.sleep(0.1)

def send_and_confirm(bus, msg, expect_id, check_fn, retries=5, delay=0.2):
    """Envía msg y espera confirmación vía expect_id usando check_fn(data)."""
    for attempt in range(1, retries+1):
        logging.info("Enviando comando %s (intento %d/%d)...", hex(msg.arbitration_id), attempt, retries)
        bus.send(msg)
        start = time.time()
        while time.time() - start < delay*10:
            resp = bus.recv(timeout=delay)
            if resp and resp.arbitration_id == expect_id and check_fn(resp.data):
                logging.info("Confirmación recibida para ID %s.", hex(expect_id))
                return True
        logging.warning("No se confirma ID %s, reintentando...", hex(expect_id))
    logging.error("No se confirmó el comando ID %s tras %d intentos.", hex(expect_id), retries)
    sys.exit(1)

def main():
    bus = open_bus()
    wait_for_bus_up(bus)
    check_emergency_released(bus)

    # 1) Limpiar errores
    send_and_confirm(
        bus,
        msg_clear_error,
        expect_id=ID_STATUS,
        check_fn=lambda data: data[0] == 0x00,  # system normal
    )

    # 2) Volver a modo Command Control
    send_and_confirm(
        bus,
        msg_set_cmd,
        expect_id=ID_STATUS,
        check_fn=lambda data: data[1] == 0x01,  # control mode = CAN command
    )

    logging.info("Recuperación completa. El robot está en estado normal y listo para operar.")

if __name__ == "__main__":
    main()
