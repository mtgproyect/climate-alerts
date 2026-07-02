# Cron externo de Climate Alerts

Configurar después de varias ejecuciones manuales correctas.

## Token granular

Crear un token exclusivo:

```text
Nombre:
climate-alerts-cron

Repository access:
Only selected repositories
→ climate-alerts

Repository permissions:
Actions
→ Read and write
```

No guardar el token en GitHub ni en los archivos del proyecto.

## Trabajo

Nombre:

```text
ClimateProyectar - Alertas cada 5 minutos
```

URL:

```text
https://api.github.com/repos/mtgproyect/climate-alerts/actions/workflows/actualizar-alertas.yml/dispatches
```

Método:

```text
POST
```

Horario:

```cron
*/5 * * * *
```

Zona horaria:

```text
America/Argentina/Buenos_Aires
```

Cuerpo:

```json
{
  "ref": "main"
}
```

Encabezados:

```text
Accept: application/vnd.github+json
Authorization: Bearer TOKEN_DE_ALERTAS
X-GitHub-Api-Version: 2026-03-10
Content-Type: application/json
User-Agent: cron-job-org-climateproyectar
```

La prueba correcta devuelve:

```text
HTTP 204
```

El workflow solo crea un commit cuando cambian las alertas, los polígonos o
el mapeo de localidades.
