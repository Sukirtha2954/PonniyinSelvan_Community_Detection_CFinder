"""
run_plotly_network.py

Generates an interactive HTML network visualization using Plotly.

Usage:
    pip install pandas networkx plotly
    python run_plotly_network.py --interactions ps_interactions.csv --characters ps_characters.csv --threshold 4 --k 3 --out ps_network_plotly.html
"""

import argparse, os
import pandas as pd
import networkx as nx
import numpy as np
from networkx.algorithms.community import k_clique_communities
import plotly.graph_objects as go
import plotly.express as px
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
        u = str(r['source'])
        v = str(r['target'])
        w = float(r.get('weight', 1.0))
        if w >= threshold:
            if G.has_edge(u,v):
                G[u][v]['weight'] += w
            else:
                G.add_edge(u, v, weight=w)
    return G

def detect_communities(G, k=3):
    cs = list(k_clique_communities(G, k))
    return [set(c) for c in cs]

def build_node_info(G, chars_df, node_comm_map):
    # faction map
    faction_map = {}
    if chars_df is not None:
        for _, r in chars_df.iterrows():
            faction_map[str(r['name'])] = str(r.get('faction','') or '')
    degrees = dict(G.degree(weight='weight'))
    info = {}
    for n in G.nodes():
        info[n] = {
            'degree': degrees.get(n,0),
            'faction': faction_map.get(n, ''),
            'communities': node_comm_map.get(n, [])
        }
    return info

def color_palette(n):
    # use plotly qualitative palette, repeat if needed
    base = px.colors.qualitative.Plotly
    if n <= len(base):
        return base[:n]
    # repeat with slight variations if more needed
    cols = []
    for i in range(n):
        cols.append(base[i % len(base)])
    return cols

def make_plotly_html(G, chars_df, communities, out_html, title="Network (CPM)"):
    # compute positions
    pos = nx.spring_layout(G, seed=42, k=0.45, iterations=200)
    # community map node->list
    node_comm_map = {}
    for cid, comm in enumerate(communities):
        for n in comm:
            node_comm_map.setdefault(n, []).append(cid)
    node_info = build_node_info(G, chars_df, node_comm_map)

    # Color nodes by their primary community (or by faction if you prefer)
    num_comms = max(1, len(communities))
    comm_colors = color_palette(num_comms)
    # fallback faction colors
    factions = sorted(set([node_info[n]['faction'] for n in G.nodes() if node_info[n]['faction']]))
    faction_cols = {f: c for f, c in zip(factions, color_palette(max(1,len(factions))))}

    node_x = []
    node_y = []
    node_text = []
    node_size = []
    node_color = []

    maxdeg = max([d for _,d in G.degree(weight='weight')]) if G.number_of_nodes()>0 else 1

    for n in G.nodes():
        x,y = pos[n]
        node_x.append(x)
        node_y.append(y)
        info = node_info[n]
        # tooltip text: name, faction, degree, communities
        name_pretty = n.replace('_',' ')
        text = f"<b>{name_pretty}</b><br>Faction: {info['faction'] or 'Unknown'}<br>Degree: {info['degree']}<br>Communities: {info['communities']}"
        node_text.append(text)
        # size scaled
        size = 8 + (info['degree'] / maxdeg) * 30
        node_size.append(size)
        # color pick: if node in communities, choose color of largest community assignment
        if node_comm_map.get(n):
            primary = node_comm_map[n][0]
            node_color.append(comm_colors[primary % len(comm_colors)])
        else:
            # fallback to faction color or grey
            node_color.append(faction_cols.get(info['faction'], "#B0B0B0"))

    # build edge traces
    edge_x = []
    edge_y = []
    edge_width = []
    edge_text = []
    for u,v,data in G.edges(data=True):
        x0,y0 = pos[u]
        x1,y1 = pos[v]
        edge_x += [x0, x1, None]
        edge_y += [y0, y1, None]
        w = data.get('weight', 1)
        edge_width.append(w)
        edge_text.append(f"{u} - {v}: {w}")

    # Edge trace (single trace with constant color, width ~ normalized)
    edge_trace = go.Scatter(
        x=edge_x, y=edge_y,
        line=dict(width=0.5, color='#888'),
        hoverinfo='none',
        mode='lines'
    )

    # Node trace
    node_trace = go.Scatter(
        x=node_x, y=node_y,
        mode='markers',
        hoverinfo='text',
        text=node_text,
        marker=dict(
            showscale=False,
            color=node_color,
            size=node_size,
            line=dict(width=1, color='#222')
        )
    )

    # Build legend entries per community (as scatter points off-plot)
    legend_traces = []
    for cid in range(len(communities)):
        legend_traces.append(go.Scatter(
            x=[None], y=[None],
            mode='markers',
            marker=dict(size=12, color=comm_colors[cid]),
            name=f"c{cid} (size={len(communities[cid])})"
        ))

    # Compose figure
    fig = go.Figure(data=[edge_trace, node_trace] + legend_traces,
                    layout=go.Layout(
                        title=title,
                        title_x=0.5,
                        showlegend=True,
                        hovermode='closest',
                        margin=dict(b=20,l=5,r=5,t=40),
                        annotations=[],
                        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                        height=900
                    ))
    # save HTML
    fig.write_html(out_html, include_plotlyjs='cdn')
    print("Saved plotly HTML:", out_html)

def main(interactions, characters, threshold, k, out):
    df, chars = read_inputs(interactions, characters)
    G = build_graph(df, threshold=threshold)
    print("Graph:", G.number_of_nodes(), "nodes,", G.number_of_edges(), "edges (thresholded).")
    communities = detect_communities(G, k=k)
    print(f"Found {len(communities)} communities (k={k}).")
    for cid,comm in enumerate(communities):
        # print brief summary
        print(f" {cid}: size={len(comm)} - sample: {list(comm)[:6]}")

    make_plotly_html(G, chars, communities, out, title=f"CPM (k={k}) Network")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--interactions", default="ps_interactions.csv")
    parser.add_argument("--characters", default="ps_characters.csv")
    parser.add_argument("--threshold", type=float, default=4.0)
    parser.add_argument("--k", type=int, default=3)
    parser.add_argument("--out", default="ps_network_plotly.html")
    args = parser.parse_args()
    main(args.interactions, args.characters, args.threshold, args.k, args.out)