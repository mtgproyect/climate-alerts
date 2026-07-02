(() => {
  "use strict";

  const URLS = {
    alerts: "./alertas.json",
    manifest: "./manifiesto.json",
    localities: "./localidades.min.json",
    localityMapping: "./localidades_alerta.min.json",
    areas: "./areas_alerta.geojson",
  };

  const state = {
    alerts: null,
    manifest: null,
    localities: [],
    localityById: new Map(),
    mapping: null,
    areas: null,
    map: null,
    areasLayer: null,
    selectedLocality: null,
    selectedMarker: null,
    selectedDate: "",
    selectedEvent: "",
  };

  const elements = {
    metricStatus: document.getElementById("metric-status"),
    metricAlerts: document.getElementById("metric-alerts"),
    metricAreas: document.getElementById("metric-areas"),
    metricLevel: document.getElementById("metric-level"),
    search: document.getElementById("locality-search"),
    suggestions: document.getElementById("locality-suggestions"),
    localityResult: document.getElementById("locality-result"),
    dateFilter: document.getElementById("date-filter"),
    eventFilter: document.getElementById("event-filter"),
    alertsList: document.getElementById("alerts-list"),
    mapStatus: document.getElementById("map-status"),
    publicationTime: document.getElementById("publication-time"),
  };

  const dateFormatter = new Intl.DateTimeFormat("es-AR", {
    dateStyle: "full",
    timeZone: "America/Argentina/Buenos_Aires",
  });

  const dateTimeFormatter = new Intl.DateTimeFormat("es-AR", {
    dateStyle: "medium",
    timeStyle: "medium",
    timeZone: "America/Argentina/Buenos_Aires",
  });

  const escapeHtml = (value) => String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");

  const normalizeText = (value) => String(value ?? "")
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .toLowerCase()
    .trim();

  const loadJson = async (url) => {
    const response = await fetch(
      `${url}?t=${Date.now()}`,
      { cache: "no-store" },
    );

    if (!response.ok) {
      throw new Error(`${url}: HTTP ${response.status}`);
    }

    return response.json();
  };

  const unpackLocalities = (value) => {
    if (
      Array.isArray(value?.columns)
      && Array.isArray(value?.records)
    ) {
      return value.records.map((record) => Object.fromEntries(
        value.columns.map((column, index) => [
          column,
          index < record.length ? record[index] : null,
        ]),
      ));
    }

    if (Array.isArray(value?.localities)) {
      return value.localities;
    }

    if (Array.isArray(value)) {
      return value;
    }

    return [];
  };

  const levelName = (level) => (
    state.alerts?.levels?.[String(level)]
    || `Nivel ${level}`
  );

  const levelClass = (level) => ({
    3: "level-yellow",
    4: "level-orange",
    5: "level-red",
  })[Number(level)] || "";

  const levelColor = (level) => ({
    3: "#f4d63e",
    4: "#ff932e",
    5: "#ee4242",
  })[Number(level)] || "#52677c";

  const eventName = (event) => (
    event?.name
    || state.alerts?.phenomena?.[String(event?.id)]
    || `Evento ${event?.id ?? "sin identificar"}`
  );

  const activeAlerts = () => {
    const alerts = Array.isArray(state.alerts?.alerts)
      ? state.alerts.alerts
      : [];

    return alerts.filter((alert) => {
      if (
        state.selectedDate
        && String(alert.date) !== state.selectedDate
      ) {
        return false;
      }

      if (state.selectedEvent) {
        return (alert.events || []).some(
          (event) => String(event.id) === state.selectedEvent,
        );
      }

      return true;
    });
  };

  const buildAreaLevelMap = () => {
    const result = new Map();

    activeAlerts().forEach((alert) => {
      const areaId = Number(alert.area_id);
      const previous = result.get(areaId) || 1;
      result.set(
        areaId,
        Math.max(previous, Number(alert.level) || 1),
      );
    });

    return result;
  };

  const renderMetrics = () => {
    const status = state.alerts?.status || "sin_datos";
    elements.metricStatus.textContent = ({
      con_alertas: "Con alertas",
      sin_alertas: "Sin alertas",
      sin_datos: "Sin datos",
      pending: "Pendiente",
    })[status] || status;

    elements.metricAlerts.textContent = String(
      state.alerts?.active_count ?? 0,
    );
    elements.metricAreas.textContent = String(
      state.alerts?.affected_area_count ?? 0,
    );

    const maximumLevel = Number(
      state.alerts?.max_level ?? 1,
    );

    elements.metricLevel.textContent = levelName(maximumLevel);
    elements.metricLevel.className = levelClass(maximumLevel);

    elements.publicationTime.textContent = state.alerts?.generated_at
      ? `Publicación: ${dateTimeFormatter.format(
          new Date(state.alerts.generated_at),
        )}`
      : "La publicación todavía no fue generada.";
  };

  const renderFilters = () => {
    const alerts = Array.isArray(state.alerts?.alerts)
      ? state.alerts.alerts
      : [];

    const dates = [...new Set(
      alerts
        .map((alert) => alert.date)
        .filter(Boolean),
    )].sort();

    elements.dateFilter.innerHTML = [
      '<option value="">Todas</option>',
      ...dates.map((date) => (
        `<option value="${escapeHtml(date)}">`
        + `${escapeHtml(dateFormatter.format(new Date(
          `${date}T12:00:00-03:00`,
        )))}`
        + "</option>"
      )),
    ].join("");

    const eventMap = new Map();

    alerts.forEach((alert) => {
      (alert.events || []).forEach((event) => {
        eventMap.set(
          String(event.id),
          eventName(event),
        );
      });
    });

    const events = [...eventMap.entries()].sort(
      (left, right) => left[1].localeCompare(
        right[1],
        "es",
      ),
    );

    elements.eventFilter.innerHTML = [
      '<option value="">Todos</option>',
      ...events.map(([id, name]) => (
        `<option value="${escapeHtml(id)}">`
        + `${escapeHtml(name)}</option>`
      )),
    ].join("");
  };

  const renderAlertsList = () => {
    const alerts = activeAlerts();

    if (!alerts.length) {
      elements.alertsList.innerHTML = (
        '<div class="empty-state">'
        + "No hay alertas activas para los filtros seleccionados."
        + "</div>"
      );
      return;
    }

    elements.alertsList.innerHTML = alerts.map((alert) => {
      const events = Array.isArray(alert.events)
        ? alert.events
        : [];

      return `
        <article class="alert-card level-${Number(alert.level)}">
          <h3 class="${levelClass(alert.level)}">
            ${escapeHtml(levelName(alert.level))}
          </h3>
          <div class="alert-meta">
            <span>Área ${escapeHtml(alert.area_id)}</span>
            <span>${alert.date
              ? escapeHtml(dateFormatter.format(new Date(
                  `${alert.date}T12:00:00-03:00`,
                )))
              : "Fecha no informada"}</span>
          </div>
          <div class="event-tags">
            ${events.length
              ? events.map((event) => (
                  `<span class="event-tag">`
                  + `${escapeHtml(eventName(event))}`
                  + "</span>"
                )).join("")
              : '<span class="event-tag">Fenómeno no informado</span>'}
          </div>
        </article>
      `;
    }).join("");
  };

  const areaIdFromFeature = (feature) => Number(
    feature?.properties?.gid
    ?? feature?.properties?.area_id
    ?? feature?.id,
  );

  const refreshMap = () => {
    if (!state.map || !state.areas) {
      return;
    }

    const areaLevels = buildAreaLevelMap();

    if (state.areasLayer) {
      state.areasLayer.remove();
    }

    state.areasLayer = L.geoJSON(state.areas, {
      style: (feature) => {
        const level = areaLevels.get(
          areaIdFromFeature(feature),
        ) || 1;

        return {
          color: level >= 3
            ? levelColor(level)
            : "#52677c",
          weight: level >= 3 ? 1.5 : 0.45,
          fillColor: level >= 3
            ? levelColor(level)
            : "#34495d",
          fillOpacity: level >= 3 ? 0.52 : 0.06,
        };
      },
      onEachFeature: (feature, layer) => {
        const areaId = areaIdFromFeature(feature);
        const level = areaLevels.get(areaId) || 1;

        layer.bindPopup(
          `<strong>Área ${escapeHtml(areaId)}</strong><br>`
          + `${escapeHtml(levelName(level))}`,
        );
      },
    }).addTo(state.map);

    elements.mapStatus.textContent = (
      `${activeAlerts().length} registros activos `
      + "para los filtros seleccionados."
    );
  };

  const initializeMap = () => {
    if (!window.L) {
      elements.mapStatus.textContent = (
        "No se pudo cargar la biblioteca del mapa. "
        + "El listado de alertas sigue disponible."
      );
      return;
    }

    state.map = L.map("alert-map", {
      zoomControl: true,
      minZoom: 3,
    }).setView([-38.4, -64.2], 4);

    L.tileLayer(
      "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
      {
        maxZoom: 18,
        attribution: (
          "&copy; OpenStreetMap contributors"
        ),
      },
    ).addTo(state.map);

    refreshMap();
  };

  const alertRecordsForLocality = (localityId) => {
    const areaIds = (
      state.mapping?.by_locality_id?.[String(localityId)]
      || []
    ).map(Number);

    const areaSet = new Set(areaIds);

    return {
      areaIds,
      alerts: (state.alerts?.alerts || []).filter(
        (alert) => areaSet.has(Number(alert.area_id)),
      ),
    };
  };

  const renderSelectedLocality = (locality) => {
    state.selectedLocality = locality;

    const { areaIds, alerts } = alertRecordsForLocality(
      locality.id,
    );

    const heading = (
      `${escapeHtml(locality.name)}, `
      + `${escapeHtml(locality.province || "")}`
    );

    if (!areaIds.length) {
      elements.localityResult.innerHTML = `
        <h3>${heading}</h3>
        <p>
          Esta localidad no quedó asociada a un polígono de alerta.
          La ausencia de asociación no reemplaza la consulta oficial.
        </p>
      `;
    } else if (!alerts.length) {
      elements.localityResult.innerHTML = `
        <h3>${heading}</h3>
        <p>
          No hay alertas meteorológicas activas para sus áreas:
          ${areaIds.map(escapeHtml).join(", ")}.
        </p>
      `;
    } else {
      const maximumLevel = Math.max(
        ...alerts.map((alert) => Number(alert.level) || 1),
      );

      const names = [...new Set(
        alerts.flatMap((alert) => (
          alert.events || []
        ).map(eventName)),
      )];

      elements.localityResult.innerHTML = `
        <h3 class="${levelClass(maximumLevel)}">
          ${heading}
        </h3>
        <p>
          <strong>${escapeHtml(levelName(maximumLevel))}</strong>
          · ${alerts.length} registro(s) activo(s).
        </p>
        <p>
          ${names.length
            ? escapeHtml(names.join(" · "))
            : "Fenómeno no informado"}
        </p>
        <p>
          Áreas asociadas: ${areaIds.map(escapeHtml).join(", ")}.
        </p>
      `;
    }

    elements.search.value = (
      `${locality.name}, ${locality.province || ""}`
    );
    elements.suggestions.hidden = true;

    if (
      state.map
      && Number.isFinite(Number(locality.lat))
      && Number.isFinite(Number(locality.lon))
    ) {
      if (state.selectedMarker) {
        state.selectedMarker.remove();
      }

      state.selectedMarker = L.marker([
        Number(locality.lat),
        Number(locality.lon),
      ]).addTo(state.map);

      state.selectedMarker.bindPopup(heading).openPopup();
      state.map.setView(
        [Number(locality.lat), Number(locality.lon)],
        7,
      );
    }
  };

  const renderSuggestions = (query) => {
    const normalized = normalizeText(query);

    if (normalized.length < 2) {
      elements.suggestions.hidden = true;
      return;
    }

    const matches = state.localities
      .filter((locality) => locality._search.includes(normalized))
      .slice(0, 9);

    if (!matches.length) {
      elements.suggestions.innerHTML = (
        '<div class="suggestion">Sin coincidencias</div>'
      );
      elements.suggestions.hidden = false;
      return;
    }

    elements.suggestions.innerHTML = matches.map((locality) => `
      <button
        type="button"
        class="suggestion"
        data-locality-id="${escapeHtml(locality.id)}"
      >
        <strong>${escapeHtml(locality.name)}</strong>
        <small>
          ${escapeHtml(locality.department || "")}
          ${locality.department ? " · " : ""}
          ${escapeHtml(locality.province || "")}
        </small>
      </button>
    `).join("");

    elements.suggestions.hidden = false;
  };

  elements.search.addEventListener("input", () => {
    renderSuggestions(elements.search.value);
  });

  elements.suggestions.addEventListener("click", (event) => {
    const button = event.target.closest("[data-locality-id]");

    if (!button) {
      return;
    }

    const locality = state.localityById.get(
      String(button.dataset.localityId),
    );

    if (locality) {
      renderSelectedLocality(locality);
    }
  });

  elements.dateFilter.addEventListener("change", () => {
    state.selectedDate = elements.dateFilter.value;
    renderAlertsList();
    refreshMap();
  });

  elements.eventFilter.addEventListener("change", () => {
    state.selectedEvent = elements.eventFilter.value;
    renderAlertsList();
    refreshMap();
  });

  document.addEventListener("click", (event) => {
    if (!event.target.closest(".search-wrap")) {
      elements.suggestions.hidden = true;
    }
  });

  Promise.all([
    loadJson(URLS.alerts),
    loadJson(URLS.manifest),
    loadJson(URLS.localities),
    loadJson(URLS.localityMapping),
    loadJson(URLS.areas),
  ])
    .then(([
      alerts,
      manifest,
      localitiesValue,
      mapping,
      areas,
    ]) => {
      state.alerts = alerts;
      state.manifest = manifest;
      state.mapping = mapping;
      state.areas = areas;
      state.localities = unpackLocalities(localitiesValue)
        .map((locality) => ({
          ...locality,
          _search: normalizeText(
            `${locality.name || ""} `
            + `${locality.department || ""} `
            + `${locality.province || ""}`,
          ),
        }));

      state.localityById = new Map(
        state.localities.map((locality) => [
          String(locality.id),
          locality,
        ]),
      );

      renderMetrics();
      renderFilters();
      renderAlertsList();
      initializeMap();
    })
    .catch((error) => {
      console.error(error);
      elements.metricStatus.textContent = "Error";
      elements.alertsList.innerHTML = `
        <div class="empty-state">
          No se pudieron cargar los datos: ${escapeHtml(error.message)}
        </div>
      `;
      elements.mapStatus.textContent = (
        "No se pudo preparar el mapa."
      );
    });
})();
