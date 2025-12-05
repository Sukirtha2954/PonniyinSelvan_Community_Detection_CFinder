# Ponniyin Selvan — Social Network Analysis & Community Detection
### *Interactive Draggable Graph • Community Detection • Network Science for Literature*

This project performs **social network analysis** on the characters of *Ponniyin Selvan* using data-driven graph algorithms.  
It extracts relationships between characters, detects communities using the **Clique Percolation Method (CPM)**, and visualizes everything using a **fully interactive, draggable network** built with **vis-network**.

Users can:

- Drag & rearrange nodes freely  
-  Search characters  
-  Filter by **factions** & **communities**  
-  Visualize nodes colored by faction  
-  Save custom layouts (local or downloadable JSON)  
-  Load previously saved layouts  
-  Explore narrative structure through network science  

---

##  Features

### **1. Community Detection (CPM)**  
The project applies **k-Clique Percolation** (`k = 3,4`) to identify overlapping communities—groups of characters frequently interacting in the narrative.

Example detected clusters:

| Community | Description |
|----------|-------------|
| Chola | Royal family, allies, Vandiyathevan’s network |
| Pandya | Conspirators, assassins, supporting figures |
| Pazhuvettarayar | Inner political circle |
| Kadambur | Chieftains & political alliances |

---

### **2. Interactive Graph Visualization (vis-network)**

✔ Draggable nodes  
✔ Zoom & pan  
✔ Hover details  
✔ Nodes colored by **faction** (Chola, Pandya, External, etc.)  
✔ Node size reflects **degree centrality**  
✔ Edge thickness reflects **interaction strength**  

---

### **3. Filters & Controls**

The left control panel includes:

- Faction filters (Chola / Pandya / External / Religious / Others)
- Community filters (from CPM)
- Search bar (focuses on selected character)
- Reset view
- **Save layout (localStorage)**
- **Load layout (localStorage)**
- **Download positions (JSON)** → can be committed  
- **Upload positions (JSON)** → restores layout exactly  

---

### **4. Layout Persistence**

You can preserve custom layouts in two ways:

#### **A. Local Storage Save/Load**  
One click stores node positions in the browser.

#### **B. Download / Upload JSON**  
Exports all node coordinates to a file:

This JSON can be shared, restored, or tracked in GitHub.

---

##  Project Structure
Community_Detection/
│
├── ps_interactions.csv # Character interactions (edges)
├── ps_characters.csv # Character metadata (faction)
├── ps_communities.csv # Optional static communities
│
├── run_cpm_visualize.py # Matplotlib static CPM visualization
├── run_plotly_network.py # Plotly dynamic visualization
├── export_vis_draggable.py #  Main interactive graph generator
│
├── ps_network_vis.html # Output: interactive visualization
├── ps_positions.json # Optional: saved layout file
│
└── cpm_output/ # Auto-generated community CSVs

---

##  Usage

### **Generate the interactive graph**

```bash
python export_vis_draggable.py \
    --interactions ps_interactions.csv \
    --characters ps_characters.csv \
    --threshold 4 \
    --k 3 \
    --out ps_network_vis.html
```
