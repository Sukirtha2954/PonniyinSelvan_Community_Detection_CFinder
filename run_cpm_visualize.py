import os
import math
import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt
import numpy as np
from networkx.algorithms.community import k_clique_communities
import itertools
import colorsys
import argparse
from collections import Counter
from matplotlib.patches import Polygon

# -----------------------
DEFAULT_THRESHOLD = 4      # keep edges with weight >= threshold (tune this)
K_VALUES = [3, 4]          # clique sizes to try; try multiple (k=3,4,5..)
OUT_DIR = "cpm_output"
INTERACTIONS_CSV = "C:/Users/Sukirtha/Desktop/Community_Detection/ps_interactions.csv"
CHARACTERS_CSV = "C:/Users/Sukirtha/Desktop/Community_Detection/ps_characters.csv"
SEED = 42
# -----------------------

def ensure_outdir():
    os.makedirs(OUT_DIR, exist_ok=True)

def read_data(interactions_path):
    df = pd.read_csv(interactions_path)
    expected_cols = {"source", "target"}
    if not expected_cols.issubset(set(df.columns)):
        raise ValueError(f"{interactions_path} must contain columns: source,target[,weight]")
    # if weight missing, assume weight 1
    if "weight" not in df.columns:
        df["weight"] = 1
    return df

def build_threshold_graph(df_edges, threshold=DEFAULT_THRESHOLD):
    G = nx.Graph()
    # add weighted edges but only include those >= threshold
    for _, row in df_edges.iterrows():
        u = str(row["source"])
        v = str(row["target"])
        w = float(row.get("weight", 1))
        if w >= threshold:
            if G.has_edge(u,v):
                G[u][v]["weight"] += w
            else:
                G.add_edge(u, v, weight=w)
    # also ensure all nodes from characters file are present (optional)
    return G

def palette(n):
    """Generate n distinct colors (HSV -> RGB)"""
    if n <= 0:
        return []
    hues = np.linspace(0, 1, n+1)[:-1]
    colors = [colorsys.hsv_to_rgb(h, 0.6, 0.9) for h in hues]
    return colors

# -----------------------
# New helper functions for improved visualization & labels
# -----------------------
def get_community_label_map(communities, characters_df):
    """
    For each community (iterable of sets), pick the majority 'faction' value from characters_df.
    Returns dict: community_id -> label string (e.g. "Chola (size=11)").
    If no faction info, fallback to "c{cid} (size=N)".
    """
    label_map = {}
    # build a quick map name->faction
    faction_map = {}
    if characters_df is not None:
        for _, r in characters_df.iterrows():
            faction_map[str(r["name"])] = str(r.get("faction", "") or "")
    for cid, comm in enumerate(communities):
        factions = [faction_map.get(n, "") for n in comm if n in faction_map]
        if factions:
            most = Counter(factions).most_common(1)[0]
            label = f"{most[0]} (size={len(comm)})"
        else:
            label = f"c{cid} (size={len(comm)})"
        label_map[cid] = label
    return label_map

def _convex_hull(points):
    """
    Simple 2D convex hull using monotone chain (Andrew's algorithm).
    Points: list of (x,y) or numpy arrays. Converts to tuples so they are hashable.
    Returns hull as list of (x,y). If <=2 points, returns them.
    """
    # convert numpy arrays (or any sequence) -> tuples so they can be hashed
    pts = [tuple(p) for p in points]

    # sort and dedupe
    pts = sorted(set(pts))
    if len(pts) <= 2:
        return pts

    # cross product
    def cross(o, a, b):
        return (a[0]-o[0])*(b[1]-o[1]) - (a[1]-o[1])*(b[0]-o[0])

    lower = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)

    upper = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)

    hull = lower[:-1] + upper[:-1]
    return hull

def draw_overlapping_communities(G, communities, k, outpath, node_attr_df=None):
    """
    Improved visualization:
      - draws convex hulls for each community
      - labels communities using majority faction (if node_attr_df provided)
      - labels only high-degree nodes to avoid clutter
    """
    # compute layout with more iterations for stability
    pos = nx.spring_layout(G, seed=SEED, k=0.45, iterations=200)

    plt.figure(figsize=(14,10))
    ax = plt.gca()
    ax.set_facecolor("white")
    ax.set_title(f"CPM (k={k}) — {len(communities)} communities — colored hulls & labels", fontsize=16)

    # lightly draw edges first
    nx.draw_networkx_edges(G, pos, alpha=0.2, width=0.8, edge_color="#999999")

    # compute degree-based node sizes
    degrees = dict(G.degree(weight="weight"))
    deg_vals = np.array([degrees.get(n,0) for n in G.nodes()])
    # avoid zero-range
    if len(deg_vals) == 0:
        deg_vals = np.array([1])
    min_deg, max_deg = deg_vals.min(), deg_vals.max()
    # linear scaling to [120, 900]
    def scale(d):
        if max_deg == min_deg:
            return 300
        return 120 + (d-min_deg)/(max_deg-min_deg) * (900-120)

    node_sizes = {n: scale(degrees.get(n,0)) for n in G.nodes()}

    # draw a faint base node layer
    nx.draw_networkx_nodes(G, pos, nodelist=list(G.nodes()), node_size=[node_sizes[n] for n in G.nodes()],
                           node_color="#EEEEEE", edgecolors="#333333", linewidths=0.4, alpha=0.9)

    # palette
    colors = palette(max(1, len(communities)))

    # load character df for labels
    char_df = node_attr_df if node_attr_df is not None else None
    comm_label_map = get_community_label_map(communities, char_df)

    # draw convex hulls and overlay community nodes
    for cid, comm in enumerate(communities):
        nodes = list(comm)
        if not nodes:
            continue
        pts = [pos[n] for n in nodes if n in pos]
        if not pts:
            continue
        # hull polygon
        hull = _convex_hull(pts)
        if len(hull) >= 3:
            poly = Polygon(hull, closed=True, facecolor=colors[cid % len(colors)], edgecolor=None, alpha=0.20, zorder=0)
            ax.add_patch(poly)
        else:
            # draw a circle around small community centroid
            xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
            cx, cy = (sum(xs)/len(xs), sum(ys)/len(ys))
            r = 0.12 + 0.06 * math.log1p(len(nodes))
            circ = plt.Circle((cx,cy), r, color=colors[cid % len(colors)], alpha=0.15, zorder=0)
            ax.add_patch(circ)

        # overlay community nodes (semi-transparent)
        nx.draw_networkx_nodes(G, pos, nodelist=nodes, node_size=[node_sizes[n] for n in nodes],
                               node_color=[colors[cid % len(colors)]], alpha=0.55, linewidths=0.6)

        # community centroid label
        xs = [pos[n][0] for n in nodes]; ys = [pos[n][1] for n in nodes]
        cx, cy = (sum(xs)/len(xs), sum(ys)/len(ys))
        label_text = comm_label_map.get(cid, f"c{cid} (size={len(nodes)})")
        ax.text(cx, cy, label_text, fontsize=10, fontweight="bold",
                ha="center", va="center", bbox=dict(facecolor="white", alpha=0.7, boxstyle="round"))

    # label only higher-degree nodes to reduce clutter
    deg_thresh = max(2, int(np.percentile(list(degrees.values()), 75)))
    label_nodes = [n for n, d in degrees.items() if d >= deg_thresh]
    label_dict = {n: n.replace("_"," ") for n in label_nodes}
    nx.draw_networkx_labels(G, pos, labels=label_dict, font_size=9, font_weight="normal", verticalalignment='center')

    # create legend for community labels (small colored squares)
    import matplotlib.patches as mpatches
    legend_patches = []
    for cid in range(len(communities)):
        legend_patches.append(mpatches.Patch(color=colors[cid % len(colors)], label=comm_label_map.get(cid, f"c{cid}")))
    ax.legend(handles=legend_patches, bbox_to_anchor=(1.02, 1.0), loc='upper left', borderaxespad=0.1)

    plt.axis('off')
    plt.tight_layout()
    plt.savefig(outpath, dpi=220, bbox_inches="tight")
    plt.close()
    print(f"Saved improved visualization: {outpath}")

# -----------------------
# rest of functions remain same (save_communities, main)
# -----------------------
def save_communities(communities, k):
    rows = []
    node_map = {}
    for cid, comm in enumerate(communities):
        for node in comm:
            rows.append({"community_id": int(cid), "member": node})
            node_map.setdefault(node, []).append(int(cid))
    dfc = pd.DataFrame(rows)
    dfc.to_csv(os.path.join(OUT_DIR, f"cpm_communities_k{k}.csv"), index=False)
    # node -> communities
    df_node = pd.DataFrame([{"node": n, "communities": str(node_map.get(n, []))} for n in sorted(set(node_map.keys()))])
    df_node.to_csv(os.path.join(OUT_DIR, f"node_community_map_k{k}.csv"), index=False)
    print(f"Saved community CSVs for k={k} in {OUT_DIR}")

def main(interactions_path=INTERACTIONS_CSV, characters_path=CHARACTERS_CSV, threshold=DEFAULT_THRESHOLD, k_values=K_VALUES):
    ensure_outdir()
    print("Reading interactions...")
    df = read_data(interactions_path)
    # Build thresholded graph
    print(f"Building thresholded graph with weight >= {threshold} ...")
    G = build_threshold_graph(df, threshold=threshold)
    print(f"Graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges (after thresholding)")

    # Attempt to read characters file for attributes (optional)
    node_attr_df = None
    if os.path.exists(characters_path):
        try:
            node_attr_df = pd.read_csv(characters_path)
            print(f"Loaded character attributes from {characters_path}")
        except Exception:
            node_attr_df = None

    # For each k, run CPM
    for k in k_values:
        print(f"\nRunning k-clique communities (k={k}) ...")
        communities_gen = list(k_clique_communities(G, k))
        communities = [set(c) for c in communities_gen]
        print(f"Found {len(communities)} communities for k={k}")

        # Save communities
        save_communities(communities, k)

        # Improved Visualize
        outpath = os.path.join(OUT_DIR, f"cpm_k{k}.png")
        # print community labels to console
        comm_labels = get_community_label_map(communities, node_attr_df)
        print("Community labels (auto):")
        for cid, lab in comm_labels.items():
            print(f"  {cid}: {lab}")

        draw_overlapping_communities(G, communities, k, outpath, node_attr_df=node_attr_df)

    # Additionally save the thresholded graph as GEXF for Gephi if user needs it
    try:
        gexf_path = os.path.join(OUT_DIR, "ps_graph_thresholded.gexf")
        nx.write_gexf(G, gexf_path)
        print(f"Saved GEXF graph for Gephi: {gexf_path}")
    except Exception as e:
        print("Could not save GEXF:", e)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--interactions", default=INTERACTIONS_CSV, help="path to interactions csv")
    parser.add_argument("--characters", default=CHARACTERS_CSV, help="optional characters csv")
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD, help="weight threshold (include edges with weight >= threshold)")
    parser.add_argument("--k", nargs="+", type=int, default=K_VALUES, help="one or more k values for k-clique CPM")
    parser.add_argument("--outdir", default=OUT_DIR, help="output folder")
    args = parser.parse_args()

    # apply CLI args
    OUT_DIR = args.outdir
    INTERACTIONS_CSV = args.interactions
    CHARACTERS_CSV = args.characters
    DEFAULT_THRESHOLD = args.threshold
    K_VALUES = args.k

    main(interactions_path=INTERACTIONS_CSV, characters_path=CHARACTERS_CSV, threshold=DEFAULT_THRESHOLD, k_values=K_VALUES)
