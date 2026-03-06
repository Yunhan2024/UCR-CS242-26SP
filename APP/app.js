/**
 * app.js — Search logic, result rendering, tabs, and comparison.
 */

// ── DOM references ───────────────────────────────────
const queryInput      = document.getElementById("queryInput");
const searchBtn       = document.getElementById("searchBtn");
const topKSelect      = document.getElementById("topK");
const searchMeta      = document.getElementById("searchMeta");
const resultsContainer = document.getElementById("resultsContainer");
const compareBtn      = document.getElementById("compareBtn");
const compareES       = document.getElementById("compareES");
const compareBERT     = document.getElementById("compareBERT");

// ── Helpers ──────────────────────────────────────────

function getSelectedIndex() {
    return document.querySelector('input[name="indexType"]:checked').value;
}

function getTopK() {
    return parseInt(topKSelect.value, 10);
}

/**
 * Call the /api/search endpoint.
 * @returns {Promise<Object>} response JSON
 */
async function doSearch(query, indexType, topK, country) {
    const body = { query, index_type: indexType, top_k: topK };
    if (country) body.country = country;

    const resp = await fetch("/api/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
    });

    if (!resp.ok) {
        const err = await resp.json();
        throw new Error(err.error || "Search failed.");
    }
    return resp.json();
}


// ── Render a single result card ──────────────────────

function renderCard(result, rank) {
    const genres = (result.genres || [])
        .map(g => {
            const name = typeof g === "string" ? g : (g.name || g);
            return `<span class="badge badge--genre">${name}</span>`;
        })
        .join("");

    // Countries can be: ["US","GB"] (from BERT) or [] (from ES)
    const countries = (result.countries || result.country_names || [])
        .map(c => {
            const code = typeof c === "string" ? c : (c.iso_3166_1 || c.name || c);
            return `<span class="badge badge--country">${code}</span>`;
        })
        .join("");

    const rating = result.rating
        ? `<span class="badge badge--rating">★ ${result.rating}</span>`
        : "";

    const year = result.release_year || "";
    const overview = result.overview || "No overview available.";

    // Build links
    let links = "";
    if (result.imdb_id) {
        links += ` <a href="https://www.imdb.com/title/${result.imdb_id}/" target="_blank" class="result-link">IMDb</a>`;
    }
    if (result.movie_id) {
        links += ` <a href="https://www.themoviedb.org/movie/${result.movie_id}" target="_blank" class="result-link">TMDB</a>`;
    }

    return `
        <div class="result-card">
            <div class="result-card__header">
                <div>
                    <span class="result-card__rank">#${rank}</span>
                    <span class="result-card__title">${result.title}</span>
                    <span class="result-card__year">(${year})</span>
                    ${links}
                </div>
                <span class="result-card__score">Score: ${result.score}</span>
            </div>
            <div class="result-card__meta">
                ${genres} ${countries} ${rating}
            </div>
            <p class="result-card__overview">${overview}</p>
        </div>
    `;
}


// ── Main search handler ──────────────────────────────

async function handleSearch() {
    const query = queryInput.value.trim();
    if (!query) return;

    const indexType = getSelectedIndex();
    const topK = getTopK();

    // Show loading state
    resultsContainer.innerHTML = `<p class="placeholder-text"><span class="spinner"></span> Searching…</p>`;
    searchMeta.classList.add("hidden");

    try {
        const data = await doSearch(query, indexType, topK);

        // Show meta info
        const label = indexType === "bert" ? "BERT + FAISS" : "Elasticsearch";
        searchMeta.innerHTML =
            `Showing <strong>${data.result_count}</strong> results for "<strong>${data.query}</strong>" ` +
            `via <strong>${label}</strong> — <span class="time">${data.time_ms} ms</span>`;
        searchMeta.classList.remove("hidden");

        // Render results
        if (data.results.length === 0) {
            resultsContainer.innerHTML = `<p class="placeholder-text">No results found. Try a different query.</p>`;
        } else {
            resultsContainer.innerHTML = data.results
                .map((r, i) => renderCard(r, i + 1))
                .join("");
        }
    } catch (err) {
        resultsContainer.innerHTML = `<p class="placeholder-text" style="color:var(--red);">Error: ${err.message}</p>`;
    }
}


// ── Comparison handler ───────────────────────────────

async function handleCompare() {
    const query = queryInput.value.trim();
    if (!query) {
        alert("Please enter a query first.");
        return;
    }

    const topK = getTopK();
    compareES.innerHTML = `<p class="placeholder-text"><span class="spinner"></span> Searching ES…</p>`;
    compareBERT.innerHTML = `<p class="placeholder-text"><span class="spinner"></span> Searching BERT…</p>`;

    // Run both searches in parallel
    const [esData, bertData] = await Promise.allSettled([
        doSearch(query, "elasticsearch", topK),
        doSearch(query, "bert", topK),
    ]);

    // Render ES results
    if (esData.status === "fulfilled") {
        const d = esData.value;
        compareES.innerHTML =
            `<p class="search-meta">Found ${d.result_count} results — <span class="time">${d.time_ms} ms</span></p>` +
            d.results.map((r, i) => renderCard(r, i + 1)).join("");
    } else {
        compareES.innerHTML = `<p class="placeholder-text" style="color:var(--red);">ES error: ${esData.reason}</p>`;
    }

    // Render BERT results
    if (bertData.status === "fulfilled") {
        const d = bertData.value;
        compareBERT.innerHTML =
            `<p class="search-meta">Found ${d.result_count} results — <span class="time">${d.time_ms} ms</span></p>` +
            d.results.map((r, i) => renderCard(r, i + 1)).join("");
    } else {
        compareBERT.innerHTML = `<p class="placeholder-text" style="color:var(--red);">BERT error: ${bertData.reason}</p>`;
    }
}


// ── Tab switching ────────────────────────────────────

document.querySelectorAll(".tab").forEach(tabBtn => {
    tabBtn.addEventListener("click", () => {
        // Deactivate all
        document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
        document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));

        // Activate clicked
        tabBtn.classList.add("active");
        const target = document.getElementById("tab-" + tabBtn.dataset.tab);
        if (target) target.classList.add("active");
    });
});


// ── Event listeners ──────────────────────────────────

searchBtn.addEventListener("click", handleSearch);
queryInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") handleSearch();
});
compareBtn.addEventListener("click", handleCompare);
