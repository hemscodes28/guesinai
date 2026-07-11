
// ─── Species Config ───────────────────────────────────────────────────────────
const SPECIES_COLORS = {
    "Brazil Nut":  { bg: "rgba(133,77,14,0.15)", border: "rgba(133,77,14,0.5)", fill: "#854d0e", dot: "#854d0e" },
    "Rubber Tree": { bg: "rgba(22,101,52,0.15)",  border: "rgba(22,101,52,0.5)",  fill: "#166534", dot: "#16a34a" },
    "Açaí Palm":   { bg: "rgba(124,58,237,0.15)", border: "rgba(124,58,237,0.5)", fill: "#7c3aed", dot: "#a78bfa" },
    "Andiroba":    { bg: "rgba(13,148,136,0.15)", border: "rgba(13,148,136,0.5)", fill: "#0d9488", dot: "#2dd4bf" },
    "Mahogany":    { bg: "rgba(220,38,38,0.15)",  border: "rgba(220,38,38,0.5)",  fill: "#dc2626", dot: "#f87171" },
};

const SP_ICONS = {
    "Brazil Nut": "🌰", "Rubber Tree": "🌳", "Açaí Palm": "🌴",
    "Andiroba": "🌿", "Mahogany": "🪵"
};

// ─── Map Init ─────────────────────────────────────────────────────────────────
const map = L.map('reforestation-map', {
    center: [-2.145, -59.000],
    zoom: 11,
    zoomControl: true,
    attributionControl: true
});

L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    attribution: '© OpenStreetMap © CARTO',
    subdomains: 'abcd',
    maxZoom: 19
}).addTo(map);

// ─── State ────────────────────────────────────────────────────────────────────
let analysisResult = null;
let markerLayer = L.layerGroup().addTo(map);
let selectedMarker = null;

// ─── Utilities ────────────────────────────────────────────────────────────────
function toast(msg, type = "info") {
    const el = document.createElement("div");
    el.className = `toast ${type}`;
    el.innerHTML = `<span>${type === "success" ? "✅" : type === "error" ? "❌" : "ℹ️"}</span><span>${msg}</span>`;
    document.getElementById("toast-container").appendChild(el);
    setTimeout(() => el.remove(), 4200);
}

function fmt(n, d = 1) {
    if (n === null || n === undefined || isNaN(n)) return "—";
    return Number(n).toFixed(d);
}

function pct(n) { return `${Math.round((n || 0) * 100)}%`; }

// ─── Main Analysis ────────────────────────────────────────────────────────────
async function runAnalysis() {
    const btn = document.getElementById("analyze-btn");
    btn.disabled = true;
    btn.innerHTML = `<div class="spinner"></div><span>Loading simulation data...</span>`;
    toast("Fetching burned cells from simulation...", "info");

    try {
        // Step 1: Fetch burned cells from simulation
        const gridRes = await fetch("/reforestation/grid-burned");
        if (!gridRes.ok) throw new Error("Failed to fetch simulation data");
        const gridData = await gridRes.json();

        if (!gridData.burned_cells || gridData.burned_cells.length === 0) {
            document.getElementById("no-burned-msg").style.display = "flex";
            toast("No burned cells in simulation. Run the wildfire simulation first.", "error");
            btn.disabled = false;
            btn.innerHTML = `<span>🔬 Analyze Burned Land Now</span>`;
            return;
        }

        document.getElementById("no-burned-msg").style.display = "none";
        btn.innerHTML = `<div class="spinner"></div><span>Running ML model on ${gridData.count} cells...</span>`;
        toast(`Analysing ${gridData.count} burned cells with the Random Forest model...`, "info");

        // Step 2: Run ML analysis
        const analyzeRes = await fetch("/reforestation/analyze", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ burned_cells: gridData.burned_cells })
        });

        if (!analyzeRes.ok) {
            const err = await analyzeRes.json();
            throw new Error(err.detail || "Analysis failed");
        }

        analysisResult = await analyzeRes.json();

        // Render everything
        renderHeroStats(analysisResult);
        renderSpeciesDistribution(analysisResult);
        renderRecoveryTimeline(analysisResult);
        renderDominantSpecies(analysisResult);
        renderFarmerAdvisory(analysisResult);
        plotMapMarkers(analysisResult.recommendations);

        document.getElementById("download-csv-btn").disabled = false;
        toast(`Analysis complete! ${analysisResult.total_burned_cells} cells analyzed.`, "success");

    } catch (err) {
        console.error(err);
        toast(`Error: ${err.message}`, "error");
    } finally {
        btn.disabled = false;
        btn.innerHTML = `<span>🔄 Re-Analyze Burned Land</span>`;
    }
}

// ─── Hero Stats ───────────────────────────────────────────────────────────────
function renderHeroStats(data) {
    const s = data.summary;
    document.getElementById("stat-burned").textContent = s.total_burned_cells.toLocaleString();
    document.getElementById("stat-area").textContent = fmt(s.total_deforested_area_ha, 1);
    document.getElementById("stat-carbon").textContent = fmt(s.carbon_recovery_potential_tCO2, 0);

    // Average confidence
    const recs = data.recommendations || [];
    const avgConf = recs.length ? (recs.reduce((a, r) => a + r.confidence, 0) / recs.length) : 0;
    document.getElementById("stat-confidence").textContent = pct(avgConf);
}

// ─── Species Distribution ─────────────────────────────────────────────────────
function renderSpeciesDistribution(data) {
    const dist = data.summary.species_distribution;
    const total = data.total_burned_cells;
    const body = document.getElementById("species-dist-body");
    document.getElementById("total-cells-badge").textContent = `${total} cells`;

    const sorted = Object.entries(dist).sort((a, b) => b[1] - a[1]);
    let html = "";

    for (const [sp, count] of sorted) {
        const cfg = SPECIES_COLORS[sp] || { bg: "rgba(255,255,255,0.05)", border: "rgba(255,255,255,0.1)", fill: "#666", dot: "#888" };
        const icon = SP_ICONS[sp] || "🌱";
        const info = (data.species_info_catalog || {})[sp] || {};
        const frac = count / total;

        html += `
        <div class="species-card" style="background:${cfg.bg}; border-color:${cfg.border};"
             onclick="filterBySpecies('${sp}')">
            <div class="sp-header">
                <div>
                    <div class="sp-name">${icon} ${sp}</div>
                    <div class="sp-category">${info.category || ""}</div>
                </div>
                <div>
                    <div class="sp-count" style="color:${cfg.dot};">${count.toLocaleString()}</div>
                    <div style="font-size:0.7rem; color:var(--slate-400); text-align:right;">${Math.round(frac*100)}%</div>
                </div>
            </div>
            <div class="sp-progress-bar">
                <div class="sp-progress-fill" style="width:0%; background:${cfg.dot};"
                     data-target="${Math.round(frac*100)}"></div>
            </div>
            <div style="margin-top:6px; font-size:0.72rem; color:var(--slate-400);">
                💰 ${info.market_price_range || "—"} &nbsp;·&nbsp; 📅 ${info.harvest_season || "—"}
            </div>
        </div>`;
    }

    body.innerHTML = html;

    // Animate bars after DOM update
    setTimeout(() => {
        body.querySelectorAll(".sp-progress-fill").forEach(el => {
            el.style.width = el.dataset.target + "%";
        });
    }, 50);
}

// ─── Recovery Timeline ────────────────────────────────────────────────────────
function renderRecoveryTimeline(data) {
    const dist = data.summary.species_distribution;
    const total = data.total_burned_cells;
    const catalog = data.species_info_catalog || {};
    const sorted = Object.entries(dist).sort((a, b) => b[1] - a[1]);
    let html = "";

    const timelines = {
        "Açaí Palm":   3, "Rubber Tree": 5, "Andiroba": 6,
        "Brazil Nut":  8, "Mahogany": 15
    };

    for (const [sp, count] of sorted) {
        const info = catalog[sp] || {};
        const icon = SP_ICONS[sp] || "🌱";
        const yrs = timelines[sp] || 5;
        html += `
        <div class="timeline-bar" style="margin-bottom:8px;">
            <span class="timeline-icon">${icon}</span>
            <div style="flex:1;">
                <div style="font-size:0.8rem; font-weight:600; color:#e2e8f0; margin-bottom:2px;">${sp}</div>
                <div style="font-size:0.72rem; color:var(--slate-400);">First yield in <strong style="color:var(--green-400);">${info.growth_time || yrs + " yrs"}</strong></div>
            </div>
            <div style="text-align:right;">
                <div style="font-size:0.8rem; font-weight:700; color:var(--amber-400);">${Math.round(count/total*100)}%</div>
                <div style="font-size:0.68rem; color:var(--slate-400);">of land</div>
            </div>
        </div>`;
    }

    document.getElementById("recovery-timeline").innerHTML = html || `<div class="empty-state"><div class="empty-text">—</div></div>`;
}

// ─── Dominant Species ─────────────────────────────────────────────────────────
function renderDominantSpecies(data) {
    const sp = data.summary.dominant_recommended_species;
    const info = (data.species_info_catalog || {})[sp] || {};
    const cfg = SPECIES_COLORS[sp] || {};

    const html = `
    <div style="text-align:center; padding: 8px 0 16px 0;">
        <div style="font-size:3rem; margin-bottom:8px;">${info.icon || "🌱"}</div>
        <div style="font-size:1.2rem; font-weight:800; color:#fff; margin-bottom:2px;">${sp}</div>
        <div style="font-size:0.78rem; color:var(--slate-400);">${info.category || ""}</div>
    </div>
    <div class="info-grid">
        <div class="info-item">
            <div class="info-label">💰 Market Price</div>
            <div class="info-value" style="font-size:0.75rem;">${info.market_price_range || "—"}</div>
        </div>
        <div class="info-item">
            <div class="info-label">📅 Harvest Season</div>
            <div class="info-value" style="font-size:0.75rem;">${info.harvest_season || "—"}</div>
        </div>
        <div class="info-item">
            <div class="info-label">⏱️ Time to Yield</div>
            <div class="info-value" style="font-size:0.75rem;">${info.growth_time || "—"}</div>
        </div>
        <div class="info-item">
            <div class="info-label">🌍 CO₂ Capture</div>
            <div class="info-value" style="font-size:0.75rem;">${info.carbon_seq || "—"}</div>
        </div>
    </div>
    <div class="section-title" style="margin-top:12px;">Soil Conditions</div>
    <div style="font-size:0.78rem; color:var(--slate-300); line-height:1.6; background:rgba(255,255,255,0.03); padding:10px; border-radius:8px; border:1px solid var(--border);">${info.conditions || "—"}</div>
    `;

    document.getElementById("dominant-body").innerHTML = html;
}

// ─── Farmer Advisory ─────────────────────────────────────────────────────────
function renderFarmerAdvisory(data) {
    const sp = data.summary.dominant_recommended_species;
    const info = (data.species_info_catalog || {})[sp] || {};
    const total = data.total_burned_cells;
    const area = data.summary.total_deforested_area_ha;
    const carbon = data.summary.carbon_recovery_potential_tCO2;

    const html = `
    <div class="farmer-tip" style="margin-bottom:10px;">
        <span class="tip-icon">👨‍🌾</span>
        <span>${info.farmer_tip || "Consult with local agricultural extension services for planting guidance."}</span>
    </div>
    <div class="section-title">📊 Land Recovery Summary</div>
    <div style="font-size:0.82rem; line-height:1.8; color:var(--slate-300);">
        <div>🔥 <strong style="color:#e2e8f0;">${total.toLocaleString()} cells</strong> burned in this simulation</div>
        <div>🌍 Total deforested area: <strong style="color:var(--amber-400);">${fmt(area, 2)} hectares</strong></div>
        <div>🌿 CO₂ recovery potential: <strong style="color:var(--teal-400);">${fmt(carbon, 0)} tonnes</strong></div>
        <div>⏳ Recovery: <strong style="color:var(--green-400);">${data.summary.recovery_timeline_years}</strong></div>
    </div>
    <div class="section-title" style="margin-top:10px;">🌱 Planting Priority</div>
    <div style="font-size:0.78rem; color:var(--slate-400); line-height:1.6; padding:8px; background:rgba(255,255,255,0.02); border:1px solid var(--border); border-radius:8px;">
        Start with fast-yield species (<strong style="color:var(--green-400);">Açaí Palm, Rubber Tree</strong>) to generate early income, then supplement with slow-growing high-value timber (<strong style="color:var(--amber-400);">Brazil Nut, Mahogany</strong>) for long-term returns and maximum carbon capture.
    </div>`;

    document.getElementById("farmer-advisory").querySelector(".card-body").innerHTML = html;
}

// ─── Plot Map Markers ─────────────────────────────────────────────────────────
function plotMapMarkers(recs) {
    markerLayer.clearLayers();

    for (const rec of recs) {
        const sp = rec.recommended_species;
        const cfg = SPECIES_COLORS[sp] || { dot: "#888" };
        const icon = SP_ICONS[sp] || "🌱";

        const conf = Math.max(6, Math.round(rec.confidence * 16));

        const marker = L.circleMarker([rec.latitude, rec.longitude], {
            radius: conf,
            fillColor: cfg.dot,
            color: "rgba(0,0,0,0.3)",
            weight: 1,
            opacity: 1,
            fillOpacity: 0.75
        });

        marker.on("click", () => showCellDetail(rec, data));
        marker.bindTooltip(`${icon} ${sp} (${Math.round(rec.confidence * 100)}%)`, { sticky: true, className: "dark-tooltip" });
        marker.addTo(markerLayer);
    }

    // Fit map to markers
    if (recs.length > 0) {
        const lats = recs.map(r => r.latitude);
        const lons = recs.map(r => r.longitude);
        map.fitBounds([
            [Math.min(...lats) - 0.02, Math.min(...lons) - 0.02],
            [Math.max(...lats) + 0.02, Math.max(...lons) + 0.02]
        ]);
    }
}

// Fix: plotMapMarkers needs access to analysisResult for click handler
function plotMapMarkers(recs) {
    markerLayer.clearLayers();

    for (const rec of recs) {
        const sp = rec.recommended_species;
        const cfg = SPECIES_COLORS[sp] || { dot: "#888" };
        const icon = SP_ICONS[sp] || "🌱";
        const conf = Math.max(6, Math.round(rec.confidence * 16));

        const marker = L.circleMarker([rec.latitude, rec.longitude], {
            radius: conf,
            fillColor: cfg.dot,
            color: "rgba(0,0,0,0.3)",
            weight: 1,
            opacity: 1,
            fillOpacity: 0.75
        });

        const recCopy = rec;
        marker.on("click", () => showCellDetail(recCopy));
        marker.bindTooltip(`${icon} ${sp} (${Math.round(rec.confidence * 100)}%)`, {
            sticky: true,
            direction: "top"
        });
        markerLayer.addLayer(marker);
    }

    if (recs.length > 0) {
        const lats = recs.map(r => r.latitude);
        const lons = recs.map(r => r.longitude);
        map.fitBounds([
            [Math.min(...lats) - 0.02, Math.min(...lons) - 0.02],
            [Math.max(...lats) + 0.02, Math.max(...lons) + 0.02]
        ]);
    }
}

// ─── Cell Detail Panel ────────────────────────────────────────────────────────
function showCellDetail(rec) {
    const sp = rec.recommended_species;
    const info = rec.species_info || {};
    const icon = SP_ICONS[sp] || "🌱";
    const cfg = SPECIES_COLORS[sp] || { bg: "rgba(255,255,255,0.05)", border: "rgba(255,255,255,0.1)", dot: "#888" };

    // Probability bars
    let probHtml = "";
    if (rec.top3_predictions) {
        for (const p of rec.top3_predictions) {
            const pCfg = SPECIES_COLORS[p.species] || { dot: "#888" };
            const pIcon = SP_ICONS[p.species] || "🌱";
            probHtml += `
            <div class="prob-bar-row">
                <div class="prob-label">${pIcon} ${p.species.split(" ")[0]}</div>
                <div class="prob-bar-wrap">
                    <div class="prob-bar-fill" style="width:${Math.round(p.probability*100)}%; background:${pCfg.dot};"></div>
                </div>
                <div class="prob-pct">${Math.round(p.probability*100)}%</div>
            </div>`;
        }
    }

    const html = `
    <div style="background:${cfg.bg}; border:1px solid ${cfg.border}; border-radius:10px; padding:12px; margin-bottom:12px;">
        <div style="display:flex; align-items:center; gap:10px; margin-bottom:10px;">
            <span style="font-size:2rem;">${icon}</span>
            <div>
                <div style="font-size:1rem; font-weight:800; color:#fff;">${sp}</div>
                <div style="font-size:0.72rem; color:var(--slate-400);">Grid [${rec.row},${rec.col}] — ${fmt(rec.latitude,4)}°N, ${fmt(rec.longitude,4)}°E</div>
            </div>
        </div>
        <div class="confidence-ring">
            <div style="position:relative; width:52px; height:52px; flex-shrink:0;">
                <svg class="ring-svg" viewBox="0 0 52 52">
                    <circle class="ring-bg" cx="26" cy="26" r="22"/>
                    <circle class="ring-fg" cx="26" cy="26" r="22"
                        style="stroke:${cfg.dot}; stroke-dasharray: ${Math.round(rec.confidence * 138.2)} 138.2;"/>
                </svg>
                <div style="position:absolute; inset:0; display:flex; align-items:center; justify-content:center; font-size:0.7rem; font-weight:700; font-family:'JetBrains Mono',monospace; color:${cfg.dot};">${Math.round(rec.confidence*100)}%</div>
            </div>
            <div>
                <div style="font-size:0.8rem; font-weight:600; color:#fff;">Model Confidence</div>
                <div style="font-size:0.72rem; color:var(--slate-400);">${info.category || ""}</div>
                <div style="font-size:0.72rem; color:var(--slate-400);">💰 ${info.market_price_range || "—"}</div>
            </div>
        </div>
    </div>

    <div class="section-title">🌱 Top Predictions</div>
    ${probHtml}

    <div class="section-title">📊 Site Characteristics</div>
    <div class="info-grid">
        <div class="info-item">
            <div class="info-label">Burn Severity</div>
            <div class="info-value">${fmt(rec.burn_severity_estimated * 100, 1)}%</div>
        </div>
        <div class="info-item">
            <div class="info-label">Deforestation</div>
            <div class="info-value">${fmt(rec.deforestation_percent, 1)}%</div>
        </div>
        <div class="info-item">
            <div class="info-label">Soil Type</div>
            <div class="info-value">${rec.soil_type || "—"}</div>
        </div>
        <div class="info-item">
            <div class="info-label">Drainage</div>
            <div class="info-value">${rec.drainage || "—"}</div>
        </div>
    </div>

    ${info.farmer_tip ? `<div class="farmer-tip" style="margin-top:10px;"><span class="tip-icon">💡</span><span>${info.farmer_tip}</span></div>` : ""}
    `;

    document.getElementById("cell-detail-body").innerHTML = html;
}

// ─── Filter by Species ────────────────────────────────────────────────────────
function filterBySpecies(sp) {
    if (!analysisResult) return;
    toast(`Highlighting ${sp} plots on map`, "info");

    markerLayer.clearLayers();
    for (const rec of analysisResult.recommendations) {
        const isSp = rec.recommended_species === sp;
        const cfg = SPECIES_COLORS[rec.recommended_species] || { dot: "#888" };
        const icon = SP_ICONS[rec.recommended_species] || "🌱";
        const conf = Math.max(5, Math.round(rec.confidence * 14));

        const marker = L.circleMarker([rec.latitude, rec.longitude], {
            radius: isSp ? conf : 3,
            fillColor: isSp ? cfg.dot : "#334155",
            color: "rgba(0,0,0,0.3)",
            weight: 1,
            opacity: isSp ? 1 : 0.3,
            fillOpacity: isSp ? 0.85 : 0.2
        });

        const recCopy = rec;
        marker.on("click", () => showCellDetail(recCopy));
        if (isSp) marker.bindTooltip(`${icon} ${sp} (${Math.round(rec.confidence * 100)}%)`, { sticky: true, direction: "top" });
        markerLayer.addLayer(marker);
    }
}

// ─── Download CSV ─────────────────────────────────────────────────────────────
function downloadCSV() {
    if (!analysisResult) return;
    const rows = [
        ["Row","Col","Latitude","Longitude","Recommended Species","Confidence","Soil Type","Drainage","Burn Severity %","Deforestation %"]
    ];
    for (const r of analysisResult.recommendations) {
        rows.push([
            r.row, r.col,
            fmt(r.latitude, 6), fmt(r.longitude, 6),
            r.recommended_species,
            Math.round(r.confidence * 100) + "%",
            r.soil_type, r.drainage,
            fmt(r.burn_severity_estimated * 100, 1),
            fmt(r.deforestation_percent, 1)
        ]);
    }
    const csv = rows.map(r => r.join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `guesin_reforestation_${new Date().toISOString().slice(0,10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
    toast("CSV exported successfully!", "success");
}

// ─── On load: auto-fetch burned cell count for display ─────────────────────────
window.addEventListener("DOMContentLoaded", async () => {
    try {
        const res = await fetch("/reforestation/grid-burned");
        if (res.ok) {
            const data = await res.json();
            if (data.count > 0) {
                document.getElementById("stat-burned").textContent = data.count.toLocaleString();
                document.getElementById("stat-area").textContent = fmt(data.count * 0.09, 1);
                toast(`Found ${data.count} burned cells ready for analysis`, "info");
            } else {
                document.getElementById("no-burned-msg").style.display = "flex";
            }
        }
    } catch (e) {
        console.log("Could not pre-fetch cell count:", e);
    }
});
