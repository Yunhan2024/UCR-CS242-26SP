/**
 * map.js — World map visualization using Leaflet.js.
 * Shows movie counts per production country as a choropleth.
 */

let map = null;
let geoLayer = null;
let countryData = {};  // { "US": 52340, "GB": 12345, ... }

const GEOJSON_URL =
    "https://raw.githubusercontent.com/datasets/geo-countries/master/data/countries.geojson";

// ── Color scale based on movie count ─────────────────

function getColor(count) {
    if (count > 10000) return "#1a237e";
    if (count > 5000)  return "#283593";
    if (count > 2000)  return "#3949ab";
    if (count > 1000)  return "#5c6bc0";
    if (count > 500)   return "#7986cb";
    if (count > 100)   return "#9fa8da";
    if (count > 10)    return "#c5cae9";
    if (count > 0)     return "#e8eaf6";
    return "#1a1d27";  // no movies
}

function style(feature) {
    const code = feature.properties.ISO_A2;
    const count = countryData[code] || 0;
    return {
        fillColor: getColor(count),
        weight: 1,
        opacity: 0.7,
        color: "#2e3245",
        fillOpacity: 0.85,
    };
}

// ── Interaction ──────────────────────────────────────

function onEachFeature(feature, layer) {
    const code = feature.properties.ISO_A2;
    const name = feature.properties.ADMIN || feature.properties.NAME || code;
    const count = countryData[code] || 0;

    layer.bindTooltip(`<strong>${name}</strong><br/>${count.toLocaleString()} movies`, {
        sticky: true,
    });

    layer.on("click", () => {
        const infoDiv = document.getElementById("countryInfo");
        infoDiv.classList.remove("hidden");
        infoDiv.innerHTML =
            `<strong>${name} (${code})</strong> — ${count.toLocaleString()} movies. ` +
            `<a href="#" id="countryFilterLink">Search movies from ${name}</a>`;

        // When the user clicks "Search movies from X", filter the search
        document.getElementById("countryFilterLink").addEventListener("click", (e) => {
            e.preventDefault();
            filterByCountry(code, name);
        });
    });

    layer.on("mouseover", (e) => {
        e.target.setStyle({ weight: 2, fillOpacity: 1 });
    });

    layer.on("mouseout", (e) => {
        if (geoLayer) geoLayer.resetStyle(e.target);
    });
}


// ── Filter search results by country ─────────────────

async function filterByCountry(countryCode, countryName) {
    const query = document.getElementById("queryInput").value.trim() || "*";
    const topK = parseInt(document.getElementById("topK").value, 10);
    const indexType = document.querySelector('input[name="indexType"]:checked').value;

    // Switch to results tab
    document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
    document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));
    document.querySelector('[data-tab="results"]').classList.add("active");
    document.getElementById("tab-results").classList.add("active");

    const resultsContainer = document.getElementById("resultsContainer");
    const searchMeta = document.getElementById("searchMeta");

    resultsContainer.innerHTML = `<p class="placeholder-text"><span class="spinner"></span> Searching movies from ${countryName}…</p>`;

    try {
        const resp = await fetch("/api/search", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                query: query,
                index_type: indexType,
                top_k: topK,
                country: countryCode,
            }),
        });
        const data = await resp.json();

        searchMeta.innerHTML =
            `Movies from <strong>${countryName}</strong>: ${data.result_count} results — ` +
            `<span class="time">${data.time_ms} ms</span>`;
        searchMeta.classList.remove("hidden");

        if (data.results.length === 0) {
            resultsContainer.innerHTML = `<p class="placeholder-text">No results found for ${countryName}.</p>`;
        } else {
            resultsContainer.innerHTML = data.results
                .map((r, i) => {
                    // Reuse renderCard from app.js (it's global)
                    return typeof renderCard === "function"
                        ? renderCard(r, i + 1)
                        : `<div class="result-card"><p>${r.title}</p></div>`;
                })
                .join("");
        }
    } catch (err) {
        resultsContainer.innerHTML = `<p class="placeholder-text" style="color:var(--red);">Error: ${err.message}</p>`;
    }
}


// ── Initialize map ───────────────────────────────────

function initMap() {
    if (map) return;  // already initialized

    map = L.map("mapContainer", {
        center: [20, 0],
        zoom: 2,
        minZoom: 2,
        maxZoom: 6,
        worldCopyJump: true,
    });

    // Dark tile layer to match the UI theme
    L.tileLayer(
        "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
        {
            attribution: '&copy; <a href="https://carto.com/">CARTO</a>',
            subdomains: "abcd",
            maxZoom: 19,
        }
    ).addTo(map);
}


// ── Load country data + GeoJSON ──────────────────────

async function loadMap() {
    const statusEl = document.getElementById("mapStatus");
    statusEl.textContent = "Loading country data…";

    initMap();

    try {
        // 1) Fetch movie counts from our API
        const countResp = await fetch("/api/countries");
        if (countResp.ok) {
            const countJson = await countResp.json();
            countryData = {};
            for (const c of countJson.countries) {
                countryData[c.country_code] = c.count;
            }
            statusEl.textContent = `Loaded ${Object.keys(countryData).length} countries from index.`;
        } else {
            // If ES is unavailable, still show the map with no data
            statusEl.textContent = "Could not load country data (ES unavailable). Map shown without data.";
        }
    } catch {
        statusEl.textContent = "Could not connect to backend. Showing empty map.";
    }

    // 2) Fetch GeoJSON boundaries
    try {
        statusEl.textContent += " Loading map boundaries…";
        const geoResp = await fetch(GEOJSON_URL);
        const geoJson = await geoResp.json();

        if (geoLayer) {
            map.removeLayer(geoLayer);
        }

        geoLayer = L.geoJSON(geoJson, {
            style: style,
            onEachFeature: onEachFeature,
        }).addTo(map);

        statusEl.textContent = `Map ready — ${Object.keys(countryData).length} countries with data.`;

        // Add a legend
        addLegend();
    } catch (err) {
        statusEl.textContent = "Failed to load GeoJSON: " + err.message;
    }
}


// ── Legend ────────────────────────────────────────────

function addLegend() {
    // Remove existing legend if any
    const existing = document.querySelector(".map-legend");
    if (existing) existing.remove();

    const legend = L.control({ position: "bottomright" });
    legend.onAdd = function () {
        const div = L.DomUtil.create("div", "map-legend");
        const grades = [0, 10, 100, 500, 1000, 2000, 5000, 10000];
        div.innerHTML = "<strong>Movies</strong><br/>";
        for (let i = 0; i < grades.length; i++) {
            const from = grades[i];
            const to = grades[i + 1];
            div.innerHTML +=
                `<i style="background:${getColor(from + 1)};width:14px;height:14px;display:inline-block;margin-right:4px;border-radius:2px;"></i> ` +
                `${from}${to ? "–" + to : "+"}<br/>`;
        }
        div.style.cssText =
            "background:rgba(15,17,23,0.9);color:#e4e6f0;padding:8px 10px;border-radius:6px;font-size:12px;line-height:1.6;";
        return div;
    };
    legend.addTo(map);
}


// ── Event listener ───────────────────────────────────

document.getElementById("loadMapBtn").addEventListener("click", loadMap);
