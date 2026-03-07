/**
 * map.js — World map visualization using Leaflet.js.
 * Shows movie counts per origin country as a choropleth.
 */

let map = null;
let geoLayer = null;
let countryData = {};  // { "US": 52340, "GB": 12345, ... }

// GeoJSON source — uses ISO Alpha-3 as feature.id ("USA", "GBR", etc.)
const GEOJSON_URL =
    "https://raw.githubusercontent.com/johan/world.geo.json/master/countries.geo.json";

// ── ISO Alpha-3 → Alpha-2 mapping ───────────────────
// Our data uses 2-letter codes (US, GB), GeoJSON uses 3-letter (USA, GBR).
const A3_TO_A2 = {
    "AFG":"AF","ALB":"AL","DZA":"DZ","AND":"AD","AGO":"AO","ATG":"AG","ARG":"AR",
    "ARM":"AM","AUS":"AU","AUT":"AT","AZE":"AZ","BHS":"BS","BHR":"BH","BGD":"BD",
    "BRB":"BB","BLR":"BY","BEL":"BE","BLZ":"BZ","BEN":"BJ","BTN":"BT","BOL":"BO",
    "BIH":"BA","BWA":"BW","BRA":"BR","BRN":"BN","BGR":"BG","BFA":"BF","BDI":"BI",
    "KHM":"KH","CMR":"CM","CAN":"CA","CPV":"CV","CAF":"CF","TCD":"TD","CHL":"CL",
    "CHN":"CN","COL":"CO","COM":"KM","COG":"CG","COD":"CD","CRI":"CR","CIV":"CI",
    "HRV":"HR","CUB":"CU","CYP":"CY","CZE":"CZ","DNK":"DK","DJI":"DJ","DMA":"DM",
    "DOM":"DO","ECU":"EC","EGY":"EG","SLV":"SV","GNQ":"GQ","ERI":"ER","EST":"EE",
    "ETH":"ET","FJI":"FJ","FIN":"FI","FRA":"FR","GAB":"GA","GMB":"GM","GEO":"GE",
    "DEU":"DE","GHA":"GH","GRC":"GR","GRD":"GD","GTM":"GT","GIN":"GN","GNB":"GW",
    "GUY":"GY","HTI":"HT","HND":"HN","HUN":"HU","ISL":"IS","IND":"IN","IDN":"ID",
    "IRN":"IR","IRQ":"IQ","IRL":"IE","ISR":"IL","ITA":"IT","JAM":"JM","JPN":"JP",
    "JOR":"JO","KAZ":"KZ","KEN":"KE","KIR":"KI","PRK":"KP","KOR":"KR","KWT":"KW",
    "KGZ":"KG","LAO":"LA","LVA":"LV","LBN":"LB","LSO":"LS","LBR":"LR","LBY":"LY",
    "LIE":"LI","LTU":"LT","LUX":"LU","MKD":"MK","MDG":"MG","MWI":"MW","MYS":"MY",
    "MDV":"MV","MLI":"ML","MLT":"MT","MHL":"MH","MRT":"MR","MUS":"MU","MEX":"MX",
    "FSM":"FM","MDA":"MD","MCO":"MC","MNG":"MN","MNE":"ME","MAR":"MA","MOZ":"MZ",
    "MMR":"MM","NAM":"NA","NRU":"NR","NPL":"NP","NLD":"NL","NZL":"NZ","NIC":"NI",
    "NER":"NE","NGA":"NG","NOR":"NO","OMN":"OM","PAK":"PK","PLW":"PW","PAN":"PA",
    "PNG":"PG","PRY":"PY","PER":"PE","PHL":"PH","POL":"PL","PRT":"PT","QAT":"QA",
    "ROU":"RO","RUS":"RU","RWA":"RW","KNA":"KN","LCA":"LC","VCT":"VC","WSM":"WS",
    "SMR":"SM","STP":"ST","SAU":"SA","SEN":"SN","SRB":"RS","SYC":"SC","SLE":"SL",
    "SGP":"SG","SVK":"SK","SVN":"SI","SLB":"SB","SOM":"SO","ZAF":"ZA","ESP":"ES",
    "LKA":"LK","SDN":"SD","SUR":"SR","SWZ":"SZ","SWE":"SE","CHE":"CH","SYR":"SY",
    "TWN":"TW","TJK":"TJ","TZA":"TZ","THA":"TH","TLS":"TL","TGO":"TG","TON":"TO",
    "TTO":"TT","TUN":"TN","TUR":"TR","TKM":"TM","TUV":"TV","UGA":"UG","UKR":"UA",
    "ARE":"AE","GBR":"GB","USA":"US","URY":"UY","UZB":"UZ","VUT":"VU","VEN":"VE",
    "VNM":"VN","YEM":"YE","ZMB":"ZM","ZWE":"ZW","SSD":"SS","PSE":"PS","XKX":"XK",
    "-99":"",
};

function getAlpha2(feature) {
    // Try converting Alpha-3 id to Alpha-2
    const a3 = feature.id || "";
    if (A3_TO_A2[a3]) return A3_TO_A2[a3];
    // Fallback: check properties
    return feature.properties?.ISO_A2 || a3;
}

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
    return "#1a1d27";
}

function style(feature) {
    const code = getAlpha2(feature);
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
    const code = getAlpha2(feature);
    const name = feature.properties.name || feature.properties.ADMIN || code;
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
    if (map) return;

    map = L.map("mapContainer", {
        center: [20, 0],
        zoom: 2,
        minZoom: 2,
        maxZoom: 6,
        worldCopyJump: true,
    });

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

    // 1) Fetch movie counts from our API
    try {
        const countResp = await fetch("/api/countries");
        if (countResp.ok) {
            const countJson = await countResp.json();
            countryData = {};
            for (const c of countJson.countries) {
                countryData[c.country_code] = c.count;
            }
            statusEl.textContent = `Loaded ${Object.keys(countryData).length} countries.`;
        } else {
            statusEl.textContent = "Could not load country data. Map shown without data.";
        }
    } catch {
        statusEl.textContent = "Could not connect to backend. Showing empty map.";
    }

    // 2) Fetch GeoJSON boundaries
    try {
        statusEl.textContent += " Loading map boundaries…";
        const geoResp = await fetch(GEOJSON_URL);

        if (!geoResp.ok) {
            throw new Error(`GeoJSON fetch failed: ${geoResp.status}`);
        }

        const geoJson = await geoResp.json();

        if (geoLayer) {
            map.removeLayer(geoLayer);
        }

        geoLayer = L.geoJSON(geoJson, {
            style: style,
            onEachFeature: onEachFeature,
        }).addTo(map);

        // Count matches
        let matched = 0;
        geoJson.features.forEach(f => {
            const code = getAlpha2(f);
            if (countryData[code]) matched++;
        });

        statusEl.textContent = `Map ready — ${matched} of ${geoJson.features.length} countries matched with movie data.`;

        addLegend();
    } catch (err) {
        console.error("[map] GeoJSON error:", err);
        statusEl.textContent = "Failed to load map boundaries: " + err.message;
    }
}


// ── Legend ────────────────────────────────────────────

function addLegend() {
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