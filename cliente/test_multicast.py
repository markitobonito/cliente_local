#!/usr/bin/env python3
"""
Script de prueba para verificar recepción de multicast en macOS.
"""

import socket
import struct
import sys

MULTICAST_GROUP = '239.255.255.250'
MULTICAST_PORT = 4000

def test_multicast_receive():
    """Prueba si podemos recibir mensajes multicast."""
    print("=" * 60)
    print("Test de Recepción Multicast")
    print("=" * 60)
    print(f"Grupo: {MULTICAST_GROUP}")
    print(f"Puerto: {MULTICAST_PORT}")
    print("")
    
    try:
        # Crear socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        # Bind al puerto
        sock.bind(('', MULTICAST_PORT))
        print(f"✓ Socket bind exitoso en puerto {MULTICAST_PORT}")
        
        # Unirse al grupo multicast
        mreq = struct.pack('4sl', socket.inet_aton(MULTICAST_GROUP), socket.INADDR_ANY)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        print(f"✓ Unido al grupo multicast {MULTICAST_GROUP}")
        
        # Timeout de 10 segundos
        sock.settimeout(10.0)
        print("")
        print("Esperando mensajes multicast (10 segundos)...")
        print("Presiona Ctrl+C para cancelar")
        print("")
        
        message_count = 0
        while True:
            try:
                data, addr = sock.recvfrom(1024)
                message = data.decode('utf-8').strip()
                message_count += 1
                print(f"[{message_count}] Recibido de {addr}: {message}")
            except socket.timeout:
                print("")
                if message_count == 0:
                    print("❌ No se recibieron mensajes multicast")
                    print("")
                    print("Posibles causas:")
                    print("  1. El puente no está enviando mensajes")
                    print("  2. El router está bloqueando multicast")
                    print("  3. macOS no está permitiendo multicast")
                    print("  4. Estás en una red diferente al puente")
                else:
                    print(f"✓ Se recibieron {message_count} mensajes")
                break
    
    except KeyboardInterrupt:
        print("")
        print(f"Cancelado. Se recibieron {message_count} mensajes.")
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
    finally:
        sock.close()

if __name__ == "__main__":
    test_multicast_receive()
