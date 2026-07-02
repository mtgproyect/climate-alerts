# Integración futura con ClimateProyectar V2

No modificar todavía el sitio principal.

Después de validar el repositorio, agregar la fuente:

```json
{
  "alerts": {
    "enabled": true,
    "manifest": "https://mtgproyect.github.io/climate-alerts/manifiesto.json",
    "alerts": "https://mtgproyect.github.io/climate-alerts/alertas.json",
    "locality_mapping": "https://mtgproyect.github.io/climate-alerts/localidades_alerta.min.json"
  }
}
```

Flujo para una localidad:

```text
locality_id
→ localidades_alerta.min.json
→ area_ids
→ alertas.json
→ alertas activas de esas áreas
```

El frontend debe aclarar que la información proviene del SMN y enlazar siempre
a la página oficial de alertas.
