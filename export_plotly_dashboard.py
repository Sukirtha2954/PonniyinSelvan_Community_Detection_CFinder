#!/usr/bin/env python3
"""
export_plotly_dashboard.py

Creates a single self-contained HTML dashboard with:
 - interactive Plotly network (CPM communities)
 - left control panel (faction filters, community filters, search)
 - right legend

Usage:
    pip install pandas networkx
    python export_plotly_dashboard.py --interactions ps_interactions.csv --characters ps_characters.csv --threshold 4 --k 3 --out ps_network_dashboard.html
"""

import argparse, os, json
import pandas as pd
import networkx as nx
import numpy as np
from networkx.algorithms.community import k_clique_communities
from collections import Counter

def read_inputs(inter_csv, char_csv=None):
    df = pd.read_csv(inter_csv)
    if 'weight' not in df.columns:
        df['weight'] = 1.0
    chars = None
    if char_csv and os.path.exists(char_csv):
        chars = pd.read_csv(char_csv)
    return df, chars

def build_graph(df_edges, threshold=1.0):
    G = nx.Graph()
    for _, r in df_edges.iterrows():
        u = str(r['source']); v = str(r['target']); w = float(r.get('weight', 1.0))
        if w >= threshold:
            if G.has_edge(u,v):
                G[u][v]['weight'] += w
            else:
                G.add_edge(u,v, weight=w)
    return G

def detect_communities(G, k=3):
    cs = list(k_clique_communities(G, k))
    return [set(c) for c in cs]

def build_positions(G):
    pos = nx.spring_layout(G, seed=42, k=0.45, iterations=200)
    return {n: (float(pos[n][0]), float(pos[n][1])) for n in G.nodes()}

def build_node_edge_json(G, chars_df, communities, pos):
    # node info
    faction_map = {}
    if chars_df is not None:
        for _, r in chars_df.iterrows():
            faction_map[str(r['name'])] = str(r.get('faction','') or '')
    node_comm = {}
    for cid, comm in enumerate(communities):
        for n in comm:
            node_comm.setdefault(n, []).append(cid)

    nodes = []
    degrees = dict(G.degree(weight='weight'))
    maxdeg = max(degrees.values()) if degrees else 1
    # create color palette for communities
    base_colors = ["#636EFA","#EF553B","#00CC96","#AB63FA","#FFA15A","#19D3F3","#FF6692","#B6E880","#FF97FF","#FECB52"]
    for n in G.nodes():
        nodes.append({
            "id": n,
            "label": n.replace("_"," "),
            "faction": faction_map.get(n,"Unknown"),
            "degree": int(degrees.get(n,0)),
            "communities": node_comm.get(n, []),
            "x": pos[n][0],
            "y": pos[n][1],
            "size": 8 + (degrees.get(n,0)/maxdeg)*28 if maxdeg>0 else 10
        })

    edges = []
    for u,v,data in G.edges(data=True):
        edges.append({"source": u, "target": v, "weight": float(data.get('weight',1.0))})
    return nodes, edges

def community_labels(communities, chars_df):
    # majority faction label as before
    label_map = {}
    faction_map = {}
    if chars_df is not None:
        for _, r in chars_df.iterrows():
            faction_map[str(r['name'])] = str(r.get('faction','') or '')
    for cid, comm in enumerate(communities):
        factions = [faction_map.get(n,"") for n in comm if n in faction_map]
        if factions:
            most = Counter(factions).most_common(1)[0]
            label = f"{most[0]} (size={len(comm)})"
        else:
            label = f"c{cid} (size={len(comm)})"
        label_map[cid] = label
    return label_map

HTML_TEMPLATE = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>CPM Network Dashboard</title>
  <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
  <style>
    body { margin:0; font-family: Arial, sans-serif; }
    #container { display: grid; grid-template-columns: 260px 1fr 220px; grid-gap:10px; height: 100vh; }
    .panel { padding:10px; background:#f7f9fc; box-shadow: 0 1px 2px rgba(0,0,0,0.05); overflow:auto; }
    #controls { font-size:14px; }
    h2{ margin:6px 0 10px 0; font-size:16px }
    label { display:block; margin:6px 0; }
    #graph { background:#eef5fa; }
    .legend-item { display:flex; align-items:center; margin:6px 0; }
    .swatch { width:14px;height:14px;margin-right:8px;border-radius:3px; }
    input[type="text"]{ width:100%; padding:6px; margin-bottom:8px; box-sizing:border-box }
    .small { font-size:12px; color:#444; margin-top:4px;}
    .muted { color:#666; font-size:12px }
    footer { font-size:12px; color:#666; margin-top:12px }
  </style>
</head>
<body>
  <div id="container">
    <div id="controls" class="panel">
      <h2>Controls</h2>
      <div>
        <strong>Search node</strong>
        <input id="search" type="text" placeholder="Search name and press Enter">
      </div>
      <div style="margin-top:10px">
        <strong>Filter by faction</strong>
        <div id="faction-checkboxes"></div>
      </div>
      <div style="margin-top:10px">
        <strong>Filter by community</strong>
        <div id="community-checkboxes"></div>
      </div>
      <div class="small muted">Tip: toggle filters to highlight groups.</div>
      <footer>CPM Dashboard — export generated</footer>
    </div>

    <div id="graph" class="panel">
      <div id="plotly-div" style="width:100%; height:100%"></div>
    </div>

    <div id="legend" class="panel">
      <h2>Legend</h2>
      <div id="comm-legend"></div>
      <hr>
      <div><strong>Factions</strong></div>
      <div id="faction-legend"></div>
    </div>
  </div>

<script>
const nodes = {nodes_json};
const edges = {edges_json};
const comm_labels = {comm_labels_json};
const factions_list = {factions_json};

// build maps
const nodeMap = {};
nodes.forEach(n => nodeMap[n.id] = n);

// base edge traces (lines)
const edgeX = [], edgeY = [];
edges.forEach(e => {
  edgeX.push(nodeMap[e.source].x);
  edgeX.push(nodeMap[e.target].x);
  edgeX.push(null);
  edgeY.push(nodeMap[e.source].y);
  edgeY.push(nodeMap[e.target].y);
  edgeY.push(null);
});

const edgeTrace = {
  x: edgeX, y: edgeY, mode:'lines', line:{color:'#888', width:0.6}, hoverinfo:'none', name:'edges'
};

// create node trace
function makeNodeTrace(filteredIds=null) {
  const x = [], y = [], text = [], marker = {size:[], color:[], line:{width:1, color:'#222'}}, ids=[];
  nodes.forEach(n => {
    if (filteredIds && filteredIds.indexOf(n.id) < 0) return;
    x.push(n.x); y.push(n.y);
    const comms = n.communities;
    const comms_display = comms.length ? comms.join(",") : "";
    text.push("<b>"+n.label+"</b><br>Faction: "+n.faction+"<br>Degree: "+n.degree+"<br>Communities: "+comms_display);
    marker.size.push(n.size);
    // color by primary community if exists else by faction color placeholder
    let color = '#B0B0B0';
    if (n.communities && n.communities.length>0) {
      color = colorPalette[n.communities[0] % colorPalette.length];
    } else {
      // faction fallback: index in factions_list
      const fidx = factions_list.indexOf(n.faction);
      if (fidx>=0) color = factionColors[fidx % factionColors.length];
    }
    marker.color.push(color);
    ids.push(n.id);
  });
  return {x,y,mode:'markers', text, hoverinfo:'text', marker, ids};
}

// small palettes
const colorPalette = ["#636EFA","#EF553B","#00CC96","#AB63FA","#FFA15A","#19D3F3","#FF6692","#B6E880","#FF97FF","#FECB52"];
const factionColors = ["#4C9F70","#2F8AC8","#C85A7A","#8C6EFF","#E99E3A","#6FB7E6"];

// build faction list and community list
const factions = Array.from(new Set(nodes.map(n=>n.faction))).sort();
const communities = Object.keys(comm_labels).map(c => ({id: parseInt(c), label: comm_labels[c]}));

// populate faction checkboxes & legend
const factionBox = document.getElementById('faction-checkboxes');
const factionLegend = document.getElementById('faction-legend');
factions.forEach((f,i) => {
  const id = "f_f_" + i;
  const wrapper = document.createElement('div');
  wrapper.innerHTML = `<label><input type="checkbox" id="${id}" checked data-faction="${f}"> ${f}</label>`;
  factionBox.appendChild(wrapper);
  const sw = document.createElement('div'); sw.className='legend-item';
  sw.innerHTML = `<div class="swatch" style="background:${factionColors[i % factionColors.length]}"></div><div>${f}</div>`;
  factionLegend.appendChild(sw);
});

// populate community checkboxes & legend
const commBox = document.getElementById('community-checkboxes');
const commLegend = document.getElementById('comm-legend');
communities.forEach((c,i) => {
  const id = "c_c_" + c.id;
  const wrapper = document.createElement('div');
  wrapper.innerHTML = `<label><input type="checkbox" id="${id}" checked data-comm="${c.id}"> ${c.label}</label>`;
  commBox.appendChild(wrapper);
  const sw = document.createElement('div'); sw.className='legend-item';
  sw.innerHTML = `<div class="swatch" style="background:${colorPalette[c.id % colorPalette.length]}"></div><div>${c.label}</div>`;
  commLegend.appendChild(sw);
});

// Plotly initial draw
const nodeTrace0 = makeNodeTrace(); // all nodes
const data = [edgeTrace, nodeTrace0].concat(communities.map((c,i)=>({
  x:[null], y:[null], mode:'markers', marker:{size:12,color:colorPalette[c.id % colorPalette.length]}, name:`c${c.id} (${c.label})`
})));

const layout = {
  showlegend:true, hovermode:'closest',
  margin:{l:10,r:10,t:40,b:10},
  xaxis:{showgrid:false, zeroline:false, showticklabels:false},
  yaxis:{showgrid:false, zeroline:false, showticklabels:false}
};

Plotly.newPlot('plotly-div', data, layout, {displayModeBar:true, responsive:true});

// filtering logic
function applyFilters() {
  const activeFactions = Array.from(document.querySelectorAll('#faction-checkboxes input:checked')).map(i=>i.dataset.faction);
  const activeComms = Array.from(document.querySelectorAll('#community-checkboxes input:checked')).map(i=>parseInt(i.dataset.comm));
  // compute allowed nodes
  const allowed = nodes.filter(n => {
    if (activeFactions.length && activeFactions.indexOf(n.faction) < 0) return false;
    // community filter: keep node if it belongs to ANY selected community
    if (activeComms.length) {
      if (!n.communities || n.communities.length==0) return false;
      const inter = n.communities.filter(x => activeComms.includes(x));
      return inter.length>0;
    }
    return true;
  }).map(n=>n.id);
  // rebuild node trace
  const newNodeTrace = makeNodeTrace(allowed);
  Plotly.restyle('plotly-div', {
    x: [newNodeTrace.x],
    y: [newNodeTrace.y],
    text: [newNodeTrace.text],
    'marker.size': [newNodeTrace.marker.size],
    'marker.color': [newNodeTrace.marker.color]
  }, [1]); // index 1 is node trace
}

// hook checkbox events
document.querySelectorAll('#faction-checkboxes input, #community-checkboxes input').forEach(el=>{
  el.addEventListener('change', ()=>applyFilters());
});

// search handler (enter key)
document.getElementById('search').addEventListener('keydown', function(e){
  if (e.key === 'Enter') {
    const q = this.value.trim().toLowerCase();
    if (!q) { applyFilters(); return; }
    // find node id by label contains q
    const found = nodes.filter(n => n.label.toLowerCase().indexOf(q) >= 0);
    const ids = found.map(f => f.id);
    if (ids.length) {
      // highlight: show only matched nodes and their neighbors
      const neighborIds = new Set(ids);
      edges.forEach(ed=>{
        if (ids.includes(ed.source)) neighborIds.add(ed.target);
        if (ids.includes(ed.target)) neighborIds.add(ed.source);
      });
      const newNodeTrace = makeNodeTrace(Array.from(neighborIds));
      Plotly.restyle('plotly-div', {
        x: [newNodeTrace.x],
        y: [newNodeTrace.y],
        text: [newNodeTrace.text],
        'marker.size': [newNodeTrace.marker.size],
        'marker.color': [newNodeTrace.marker.color]
      }, [1]);
    } else {
      alert('No node found for: ' + q);
    }
  }
});

</script>
</body>
</html>
"""

def main(interactions, characters, threshold, k, out):
    df, chars = read_inputs(interactions, characters)
    G = build_graph(df, threshold=threshold)
    print("Graph:", G.number_of_nodes(), "nodes,", G.number_of_edges(), "edges (thresholded).")
    comms = detect_communities(G, k=k)
    print("Found", len(comms), "communities (k={})".format(k))
    pos = build_positions(G)
    nodes, edges = build_node_edge_json(G, chars, comms, pos)
    comm_labels = community_labels(comms, chars)
    factions = sorted(list({n['faction'] for n in nodes}))

    # dump JSON into template
    html = HTML_TEMPLATE.replace("{nodes_json}", json.dumps(nodes))\
                        .replace("{edges_json}", json.dumps(edges))\
                        .replace("{comm_labels_json}", json.dumps(comm_labels))\
                        .replace("{factions_json}", json.dumps(factions))

    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print("Saved dashboard:", out)
    print("Open it in a browser to interact (double-click the file).")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--interactions", default="ps_interactions.csv")
    parser.add_argument("--characters", default="ps_characters.csv")
    parser.add_argument("--threshold", type=float, default=4.0)
    parser.add_argument("--k", type=int, default=3)
    parser.add_argument("--out", default="ps_network_dashboard.html")
    args = parser.parse_args()
    main(args.interactions, args.characters, args.threshold, args.k, args.out)
