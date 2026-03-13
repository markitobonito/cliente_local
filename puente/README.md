# Localcito Puente (Bridge)

El puente es el componente central del sistema de transferencia de archivos LAN. Recibe archivos de clientes y los reenvía a todos los demás clientes activos en la red.

## Funcionalidad

- Anuncia su presencia mediante multicast cada 3 segundos
- Escucha mensajes HELLO y ALIVE de clientes
- Mantiene tabla de clientes activos (timeout 10 segundos)
- Recibe archivos vía QUIC en puerto 5000
- Reenvía archivos a todos los clientes excepto el remitente

## Despliegue con Docker

```bash
docker-compose up -d
```

## Requisitos de Red

- Multicast habilitado en la red (239.255.255.250:4000)
- Puerto UDP 5000 abierto para QUIC
- Firewall configurado para permitir tráfico multicast y QUIC

## Logs

Ver logs del contenedor:
```bash
docker-compose logs -f
```

## Troubleshooting

**Clientes no descubren el puente:**
- Verificar que multicast esté habilitado en la red
- Verificar firewall no bloquea puerto 4000 UDP
- Verificar que el puente esté ejecutándose: `docker-compose ps`

**Archivos no se reenvían:**
- Verificar puerto 5000 UDP esté abierto
- Verificar logs del puente para errores de conexión
- Verificar que los clientes estén en la tabla activa (logs cada 10s)
