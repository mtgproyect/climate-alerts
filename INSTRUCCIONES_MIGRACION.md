# Subir Climate Alerts

## 1. Copiar el paquete

Descomprimir este ZIP y copiar todo su contenido dentro de la copia local de:

```text
mtgproyect/climate-alerts
```

No copiar el ZIP como archivo. Copiar sus carpetas y archivos interiores.

## 2. Workflow anterior

Si el repositorio contiene un workflow de esqueleto, eliminarlo.

Debe quedar:

```text
.github/workflows/actualizar-alertas.yml
```

## 3. Subir con GitHub Desktop

Mensaje:

```text
Activar servicio modular de alertas SMN
```

Después:

```text
Commit to main
Push origin
```

## 4. GitHub Pages

Configurar:

```text
Settings
→ Pages
→ Deploy from a branch
→ main
→ /docs
→ Save
```

## 5. Primera ejecución manual

```text
Actions
→ Actualizar alertas SMN
→ Run workflow
```

La primera ejecución puede tardar algunos minutos porque debe vincular las
10.601 localidades con los polígonos.

Resultado esperado:

```text
Sincronizar polígonos de alerta  ✓
Vincular 10.601 localidades      ✓
Consultar alertas oficiales      ✓
Validar publicación              ✓
Guardar actualización            ✓
```

Después esperar:

```text
pages build and deployment
```

## 6. Verificar

Página:

```text
https://mtgproyect.github.io/climate-alerts/
```

Manifiesto:

```text
https://mtgproyect.github.io/climate-alerts/manifiesto.json
```

Mapeo:

```text
https://mtgproyect.github.io/climate-alerts/localidades_alerta.min.json
```

El manifiesto debe informar aproximadamente:

```text
total_localities: 10601
alert_areas: al menos 150
mapped_localities: la mayoría del catálogo
```

## 7. Todavía no configurar cron

Primero realizar dos o tres pruebas manuales y verificar distintas localidades.
Luego configurar cron-job.org.
