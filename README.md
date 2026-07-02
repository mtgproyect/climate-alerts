# Climate Alerts

Servicio modular de alertas meteorológicas oficiales para ClimateProyectar.

## Cobertura

```text
10.601 localidades
polígonos oficiales del mapa público de alertas
alertas amarillas, naranjas y rojas
consulta independiente por localidad
```

## Primera ejecución

La primera ejecución realiza tres tareas:

```text
1. Descarga una sola vez los polígonos comprobados del proyecto anterior.
2. Calcula la relación de las 10.601 localidades con sus áreas.
3. Consulta las alertas activas del SMN.
```

Después de esa primera ejecución:

- los polígonos quedan guardados en este repositorio;
- el mapeo localidad → área se regenera solamente si cambia el catálogo
  o los polígonos;
- los ciclos normales consultan principalmente el endpoint de alertas.

## Archivos públicos

```text
docs/alertas.json
docs/manifiesto.json
docs/localidades_alerta.min.json
docs/areas_alerta.geojson
docs/localidades.min.json
```

## Página

```text
https://mtgproyect.github.io/climate-alerts/
```

Incluye:

- resumen nacional;
- mapa de alertas;
- filtros por fecha y fenómeno;
- búsqueda entre 10.601 localidades;
- alertas específicas para la localidad seleccionada.

## Automatización

El workflow solo usa:

```text
workflow_dispatch
```

La frecuencia se administra externamente desde cron-job.org.

Endpoint:

```text
https://api.github.com/repos/mtgproyect/climate-alerts/actions/workflows/actualizar-alertas.yml/dispatches
```
