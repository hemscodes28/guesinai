import re

with open('c:/Users/Hemkumar Ramesh/Desktop/Guesin/templates/index.html', 'r', encoding='utf-8') as f:
    index_html = f.read()

with open('c:/Users/Hemkumar Ramesh/Desktop/Guesin/templates/reforestation.html', 'r', encoding='utf-8') as f:
    ref_html = f.read()

# 1. Extract pieces from reforestation.html
css = re.search(r'<style>(.*?)</style>', ref_html, re.DOTALL).group(1)
body_match = re.search(r'<body>(.*?)<script>', ref_html, re.DOTALL)
if body_match:
    body = body_match.group(1)
else:
    body = re.search(r'<body>(.*?)</body>', ref_html, re.DOTALL).group(1)
script = re.search(r'<script>(.*?)</script>', ref_html, re.DOTALL).group(1)

# 2. Namespace CSS
css = css.replace('body {', '#reforestation-page {')
css = css.replace('body::before {', '#reforestation-page::before {')
css = css.replace('* {', '#reforestation-page * {')
css = css.replace('.card', '.ref-card')
css = css.replace('.spinner', '.ref-spinner')
# Add a comment to mark the start of reforestation styles
css = '\n        /* ========================================== */\n        /* REFORESTATION PAGE STYLES                  */\n        /* ========================================== */\n' + css

# 3. Namespace HTML
body = body.replace('class="card', 'class="ref-card')
body = body.replace('class="spinner', 'class="ref-spinner')
body = body.replace('href="/"', 'href="#" onclick="showPage(\'dashboard-page\'); return false;"')

# Wrap body in page-view div
body = '    <!-- ========================================== -->\n    <!-- REFORESTATION VIEW                         -->\n    <!-- ========================================== -->\n    <div id="reforestation-page" class="page-view">\n' + body + '    </div>\n'

# 4. Namespace JS
# rename map -> refMap, markerLayer -> refMarkerLayer
script = script.replace('const map = L.map', 'const refMap = L.map')
script = script.replace('map.', 'refMap.')
script = script.replace('let markerLayer = L.layerGroup().addTo(map);', 'let refMarkerLayer = L.layerGroup().addTo(refMap);')
script = script.replace('let markerLayer = L.layerGroup().addTo(refMap);', 'let refMarkerLayer = L.layerGroup().addTo(refMap);')
script = script.replace('markerLayer.', 'refMarkerLayer.')

map_init = '''
let refMap = null;
let refMarkerLayer = null;

function initRefMapIfNeeded() {
    if (refMap) return;
    refMap = L.map('reforestation-map', {
        center: [-2.145, -59.000],
        zoom: 11,
        zoomControl: true,
        attributionControl: true
    });
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
        attribution: '© OpenStreetMap © CARTO',
        subdomains: 'abcd',
        maxZoom: 19
    }).addTo(refMap);
    refMarkerLayer = L.layerGroup().addTo(refMap);
}
'''
# Remove the old map init
script = re.sub(r'const refMap = L\.map.*?addTo\(refMap\);', map_init, script, flags=re.DOTALL)
script = script.replace('let refMarkerLayer = L.layerGroup().addTo(refMap);', '')
script = '\n        // ═══════════════════════════════════════════════════════════════\n        // REFORESTATION MODULE LOGIC\n        // ═══════════════════════════════════════════════════════════════\n' + script


# 5. Modify index.html

# Insert CSS before </style>
index_html = index_html.replace('</style>', css + '\n    </style>')

# Replace openReforestation link in the dashboard card
index_html = index_html.replace('href="/reforestation" target="_blank"', 'href="#" onclick="openReforestation(); return false;"')

# Remove the old reforestation modal
index_html = re.sub(r'<!-- ════════════════════════════════════════════════════════════ -->\s*<!-- REFORESTATION & AGRI-DOCTOR DIAGNOSTIC REPORTS MODAL         -->.*?</div>\s*</div>\s*</div>', '', index_html, flags=re.DOTALL)

# Remove old reforestation logic from JS
index_html = re.sub(r'// ═══════════════════════════════════════════════════════════════\s*// REFORESTATION & AGRI-DOCTOR DIAGNOSTICS.*?function clearReforestationOverlay\(\) \{\s*// Overwritten during toggleReforestationOverlay\s*\}', '', index_html, flags=re.DOTALL)

# Insert the new openReforestation that shows the page
new_open_ref = '''
        function openReforestation() {
            showPage('reforestation-page');
            initRefMapIfNeeded();
            // Invalidate size to fix leaflet map rendering inside a hidden div
            setTimeout(() => {
                if (refMap) {
                    refMap.invalidateSize();
                }
            }, 100);
        }
'''
script += new_open_ref

# Insert the new body before <!-- Javascript Logical Code -->
index_html = index_html.replace('    <!-- Javascript Logical Code -->', body + '\n    <!-- Javascript Logical Code -->')

# Insert the new JS logic before </script> at the end of the file
index_html = index_html.replace('</script>\n</body>', script + '\n    </script>\n</body>')

with open('c:/Users/Hemkumar Ramesh/Desktop/Guesin/scratch/index_merged.html', 'w', encoding='utf-8') as f:
    f.write(index_html)
print('Done merging!')
