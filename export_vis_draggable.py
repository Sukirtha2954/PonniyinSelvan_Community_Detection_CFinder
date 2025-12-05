# export_vis_draggable.py
# Generates a self-contained vis-network HTML with draggable nodes + controls
import argparse, json, os
import pandas as pd
import networkx as nx
from networkx.algorithms.community import k_clique_communities
from collections import Counter

# color palette / config (unchanged)
FACTION_COLORS = [
    "#1f77b4",  # blue
    "#ff7f0e",  # orange
    "#2ca02c",  # green
    "#d62728",  # red
    "#9467bd",  # purple
    "#8c564b",  # brown
    "#e377c2",  # pink
    "#7f7f7f",  # gray
    "#bcbd22",  # yellow-green
    "#17becf",  # teal
]

VIS_TEMPLATE = """<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Interactive Vis Network (draggable nodes, colored by faction)</title>
  <script type="text/javascript" src="https://unpkg.com/vis-network@9.1.2/dist/vis-network.min.js"></script>
  <style>
    body{font-family:Arial; margin:0}
    #container { display:grid; grid-template-columns: 260px 1fr; height:100vh; gap:6px; }
    .panel { padding:10px; background:#f7f9fc; overflow:auto; }
    /* ENSURE network area has visible height */
    #network {
      background:#fff;
      border:1px solid #ddd;
      width: 100%;
      height: calc(100vh - 24px);   /* ensure visible area */
      min-height: 480px;
    }
    input[type="text"]{width:100%; padding:6px; box-sizing:border-box; margin-bottom:6px}
    .legend-item{display:flex;align-items:center;margin:6px 0}
    .swatch{width:18px;height:14px;margin-right:8px;border-radius:3px}
    .small { font-size:12px; color:#333; margin-top:8px; display:block; }
    .controls-row { margin-top:8px; display:flex; gap:6px; flex-wrap:wrap; }
  </style>
</head>
<body>
<div id="container">
  <div class="panel">
    <h3>Controls</h3>
    <div><input id="search" type="text" placeholder="Search name & press Enter"></div>
    <div><strong>Factions</strong><div id="faction-box"></div></div>
    <div style="margin-top:8px"><strong>Communities</strong><div id="comm-box"></div></div>
    <div class="controls-row">
      <button id="reset-btn">Reset view</button>
      <button id="save-pos-btn">Save positions (local)</button>
      <button id="download-pos-btn">Download positions</button>
      <input id="upload-file" type="file" accept=".json" style="display:none">
      <button id="upload-pos-btn">Upload positions</button>
      <button id="load-pos-btn">Load positions (local)</button>
    </div>
    <div class="small">Drag nodes to reposition. Downloaded JSON is commitable and portable.</div>
  </div>

  <div id="network"></div>
</div>

<script>
// Data injected here
const nodesData = {nodes_json};
const edgesData = {edges_json};
const commLabels = {comm_labels_json};
const factionsList = {factions_json};

// build vis DataSets
const nodes = new vis.DataSet(nodesData);
const edges = new vis.DataSet(edgesData);

const container = document.getElementById('network');
const data = { nodes: nodes, edges: edges };
const options = {
  physics: {
    stabilization: { enabled: true, iterations: 1000, updateInterval: 50 },
    barnesHut: { gravitationalConstant: -2000, springLength: 150, springConstant: 0.01 }
  },
  interaction: { hover: true, dragNodes: true, dragView: true, zoomView: true },
  nodes: {
    shape: 'dot',
    size: 16,
    font: { size: 14 },
    borderWidth: 1
  },
  edges: {
    color: '#999',
    width: 1,
    smooth: { type: 'continuous' }
  }
};
const network = new vis.Network(container, data, options);

// Ensure layout is visible after physics stabilizes
network.once("stabilizationIterationsDone", function () {
  try {
    // stop physics so nodes stay where you place them
    network.setOptions({ physics: false });
  } catch(e){}
  try { network.fit({ animation: { duration: 500 } }); } catch(e){}
});

// also fit after initial draw (safety)
network.once("afterDrawing", function () {
  try { network.fit({ animation: { duration: 400 } }); } catch(e){}
});

// fallback fit after short delay
setTimeout(()=> { try { network.fit({ animation: { duration: 300 } }); } catch(e){} }, 700);

// Populate faction checkboxes and community checkboxes
const fbox = document.getElementById('faction-box');
const cbox = document.getElementById('comm-box');

factionsList.forEach((f, idx) => {
  const id = 'f_' + idx;
  const wrapper = document.createElement('div');
  wrapper.innerHTML = `<label><input type="checkbox" id="${id}" checked data-f="${f}"> ${f}</label>`;
  fbox.appendChild(wrapper);
});
Object.keys(commLabels).forEach(cid => {
  const id = 'c_' + cid;
  const wrapper = document.createElement('div');
  wrapper.innerHTML = `<label><input type="checkbox" id="${id}" checked data-c="${cid}"> ${commLabels[cid]}</label>`;
  cbox.appendChild(wrapper);
});

// filtering
function applyFilters(){
  const activeFactions = Array.from(document.querySelectorAll('#faction-box input:checked')).map(n=>n.dataset.f);
  const activeComms = Array.from(document.querySelectorAll('#comm-box input:checked')).map(n=>n.dataset.c);
  const visible = nodesData
    .filter(n=>{
      if (activeFactions.length && activeFactions.indexOf(n.faction) === -1) return false;
      if (activeComms.length){
        if (!n.communities || n.communities.length===0) return false;
        // keep node if it intersects any active comm
        return n.communities.some(x => activeComms.indexOf(String(x)) !== -1);
      }
      return true;
    })
    .map(n => n.id);
  // update vis by toggling visibility
  nodes.forEach(node => {
    const show = visible.indexOf(node.id) !== -1;
    nodes.update({id: node.id, hidden: !show});
  });
}
document.querySelectorAll('#faction-box input, #comm-box input').forEach(e=>e.addEventListener('change', applyFilters));

// Ensure filters applied once so nodes are not accidentally hidden
applyFilters();

// search
document.getElementById('search').addEventListener('keydown', function(e){
  if (e.key === 'Enter'){
    const q = this.value.trim().toLowerCase();
    if (!q) return;
    const found = nodesData.filter(n => n.label.toLowerCase().includes(q));
    if (!found.length) { alert('No node'); return; }
    const id = found[0].id;
    network.focus(id, {scale:1.5, animation:{duration:500}});
    nodes.update({id: id, color:{border:'#000', background:'#FFFF66'}});
    setTimeout(()=>{ nodes.update({id:id, color:undefined}); }, 3000);
  }
});

// reset
document.getElementById('reset-btn').addEventListener('click', ()=>{ network.fit(); });

// LOCAL storage save/load (existing behavior)
document.getElementById('save-pos-btn').addEventListener('click', ()=>{
  const pos = network.getPositions();
  localStorage.setItem('ps_positions', JSON.stringify(pos));
  alert('Positions saved to localStorage');
});
document.getElementById('load-pos-btn').addEventListener('click', ()=>{
  const raw = localStorage.getItem('ps_positions');
  if (!raw) { alert('No saved positions'); return; }
  try {
    const pos = JSON.parse(raw);
    // set positions and fix nodes at those positions
    Object.keys(pos).forEach(id => nodes.update({id: id, x: pos[id].x, y: pos[id].y, fixed:{x:true, y:true}}));
    // stop physics to keep them where loaded
    network.setOptions({ physics: false });
    network.fit();
    alert('Positions loaded (nodes fixed). Reload to unlock if needed.');
  } catch(e){ alert('Invalid saved positions'); }
});

// DOWNLOAD positions -> saves a JSON file you can commit
document.getElementById('download-pos-btn').addEventListener('click', ()=>{
  try {
    const pos = network.getPositions(); // { nodeId: {x:.., y:..}, ... }
    const dataStr = JSON.stringify(pos, null, 2);
    const blob = new Blob([dataStr], {type: 'application/json'});
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'ps_positions.json';
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  } catch(e){
    alert('Could not download positions: ' + e);
  }
});

// UPLOAD positions -> select a JSON file and load positions into network
document.getElementById('upload-pos-btn').addEventListener('click', ()=>{
  const inp = document.getElementById('upload-file');
  inp.value = null;
  inp.click();
});
document.getElementById('upload-file').addEventListener('change', function(e){
  const f = e.target.files && e.target.files[0];
  if (!f) return;
  const reader = new FileReader();
  reader.onload = function(ev){
    try {
      const pos = JSON.parse(ev.target.result);
      // basic validation: object with numeric x,y for some keys
      // apply positions and fix nodes (optionally you may want them unlocked)
      Object.keys(pos).forEach(id => {
        if (typeof pos[id] === 'object' && 'x' in pos[id] && 'y' in pos[id]) {
          // ensure node exists, else ignore
          try { nodes.update({id: id, x: pos[id].x, y: pos[id].y, fixed:{x:true, y:true}}); } catch(_){}
        }
      });
      // stop physics and fit
      network.setOptions({ physics: false });
      network.fit();
      alert('Positions loaded from file (nodes fixed). Reload to unlock if needed.');
    } catch(err){
      alert('Failed to parse positions file: ' + err);
    }
  };
  reader.readAsText(f);
});

</script>
</body>
</html>
"""

def read_inputs(interactions, characters):
    df = pd.read_csv(interactions)
    if 'weight' not in df.columns:
        df['weight'] = 1.0
    chars = None
    if characters and os.path.exists(characters):
        chars = pd.read_csv(characters)
    return df, chars

def build_graph(df, threshold=1.0):
    G = nx.Graph()
    for _, r in df.iterrows():
        u,v,w = str(r['source']), str(r['target']), float(r.get('weight',1.0))
        if w >= threshold:
            if G.has_edge(u,v): G[u][v]['weight'] += w
            else: G.add_edge(u,v, weight=w)
    return G

def detect_communities(G, k=3):
    cs = list(k_clique_communities(G, k))
    return [set(c) for c in cs]

def prepare_json(G, chars_df, communities):
    """
    Prepare nodes/edges JSON. Nodes are colored by faction (first-class).
    """
    faction_map = {}
    if chars_df is not None:
        for _,r in chars_df.iterrows():
            faction_map[str(r['name'])] = str(r.get('faction','') or '')
    # build community membership
    node_comm = {}
    for cid,comm in enumerate(communities):
        for n in comm: node_comm.setdefault(n, []).append(cid)
    degrees = dict(G.degree(weight='weight'))
    maxdeg = max(degrees.values()) if degrees else 1

    # determine unique factions and map to colors
    all_factions = sorted(list({faction_map.get(n,"Unknown") for n in G.nodes()}))
    # build mapping to FACTION_COLORS
    faction_to_color = {}
    for i,f in enumerate(all_factions):
        faction_to_color[f] = FACTION_COLORS[i % len(FACTION_COLORS)]

    nodes = []
    for n in G.nodes():
        f = faction_map.get(n,"Unknown")
        nodes.append({
            "id": n,
            "label": n.replace("_"," "),
            "faction": f,
            "communities": node_comm.get(n, []),
            "value": int(5 + (degrees.get(n,0)/maxdeg)*25),
            "color": {"background": faction_to_color.get(f, "#B0B0B0"), "border": "#333333"}
        })

    edges = [{"id":str(i), "from":u, "to":v, "value":float(d.get('weight',1.0))} for i,(u,v,d) in enumerate(G.edges(data=True))]

    # community labels (majority faction inside each community)
    label_map = {}
    for cid,comm in enumerate(communities):
        factions = [faction_map.get(n,"") for n in comm if n in faction_map]
        if factions:
            most = Counter(factions).most_common(1)[0]
            label_map[cid] = f"{most[0]} (size={len(comm)})"
        else:
            label_map[cid] = f"c{cid} (size={len(comm)})"

    factions = sorted(list({n['faction'] for n in nodes}))
    return nodes, edges, label_map, factions

def main(args):
    df, chars = read_inputs(args.interactions, args.characters)
    G = build_graph(df, threshold=args.threshold)
    print("Graph:", G.number_of_nodes(), "nodes,", G.number_of_edges(), "edges")
    communities = detect_communities(G, k=args.k)
    print("Found", len(communities), "communities (k=%d)"%args.k)
    nodes, edges, comm_labels, factions = prepare_json(G, chars, communities)
    html = VIS_TEMPLATE.replace("{nodes_json}", json.dumps(nodes)).replace("{edges_json}", json.dumps(edges)).replace("{comm_labels_json}", json.dumps(comm_labels)).replace("{factions_json}", json.dumps(factions))
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(html)
    print("Wrote", args.out)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--interactions", default="ps_interactions.csv")
    parser.add_argument("--characters", default="ps_characters.csv")
    parser.add_argument("--threshold", type=float, default=4.0)
    parser.add_argument("--k", type=int, default=3)
    parser.add_argument("--out", default="ps_network_vis.html")
    args = parser.parse_args()
    main(args)
