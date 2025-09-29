import streamlit as st
import pulp
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from collections import Counter
import plotly.graph_objects as go

# =========================
# Globals / constants
# =========================
BIG_M = 10000
EPSILON = 0.001
MIP_TIME_LIMIT_SEC = 45
NO_PROGRESS_MAX = 3
CLONES_PER_TYPE = 5
PER_TYPE_CLONES = {}
debug_log = []

def dbg(msg: str):
    print(msg)
    debug_log.append(msg)

# =========================
# Optional dependency: rectpack (MaxRects)
# =========================
try:
    from rectpack import newPacker
    from rectpack.maxrects import MaxRectsBssf, MaxRectsBaf
    from rectpack.packer import SORT_AREA
    HAS_RECTPACK = True
except Exception:
    HAS_RECTPACK = False
    MaxRectsBssf = MaxRectsBaf = None
    SORT_AREA = None

# =========================
# Streamlit config & sidebar
# =========================
st.set_page_config(page_title="Truck Optimiser", layout="wide")
st.markdown(
    """
    <div style="background-color: #00008B; padding: 20px 10px; border-radius: 8px; text-align: center; border: 1px solid #ddd;">
        <h1 style="color: #FFFFFF; margin-bottom: 5px;">🚚 Truck Optimiser</h1>
        <p style="color: #FFFFFF; font-size: 18px;">Optimise inventory placement in trucks for cost-effective and efficient booking</p>
    </div>
    """,
    unsafe_allow_html=True
)

show_debug = st.sidebar.checkbox("Show debug panel", value=False)

pack_options = ["MaxRects (BSSF)", "MaxRects (BAF)", "Shelf (Greedy)"]
default_idx = (0 if HAS_RECTPACK else 2)
PACK_MODE = st.sidebar.selectbox("Packing algorithm", pack_options, index=default_idx)

if ("MaxRects" in PACK_MODE) and (not HAS_RECTPACK):
    st.sidebar.warning("rectpack not installed — falling back to Shelf (Greedy). Add `rectpack` to requirements.txt.")

# =========================
# Vehicle TYPES
# =========================
vehicle_types = [
    ("Small van",        1.5,  1.2,   1.1,   360,   1.8,    100),
    ("Medium wheel base",3.0,  1.2,   1.9,  1400,   3.6,    130),
    ("Sprinter van",     4.2,  1.2,   1.75,  950,   5.04,   135),
    ("luton van",        4.0,  2.0,   2.0,  1000,   8.0,    160),
    ("7.5T CS",          6.0,  2.88,  2.2,  2600,  17.28,   150),
    ("18T CS",           7.3,  2.88,  2.3,  9800,  21.024,  175),
    ("40ft CS",         13.5,  3.0,   3.0, 28000,  40.5,    185),
    ("20ft FB",          7.3,  2.4,   300, 10500,  17.52,   180),
    ("40ft FB",         13.5,  2.4,   300, 30000,  32.4,    190),
    ("40T Low Loader",  13.5,  2.4,   300, 30000,  32.4,    195),
]

# =========================
# Inputs
# =========================
st.header("Inventory Inputs")
weights, lengths, widths, heights = [], [], [], []

num_individual = st.number_input("Number of Individual Inventory", min_value=0, max_value=200, value=0)
cols = st.columns(5)
for i in range(num_individual):
    with cols[0]:
        weights.append(st.number_input(f"Weight {i+1} (kg)", key=f"wt_{i}", value=100.0))
    with cols[1]:
        lengths.append(st.number_input(f"Length {i+1} (m)", key=f"len_{i}", value=1.0))
    with cols[2]:
        widths.append(st.number_input(f"Width {i+1} (m)", key=f"wid_{i}", value=1.0))
    with cols[3]:
        heights.append(st.number_input(f"Height (m)", key=f"hei_{i}", value=1.0))
    with cols[4]:
        st.markdown("&nbsp;")

st.markdown("---")
st.subheader("Bulk Inventory Entries")
bulk_entries = st.number_input("Number of Bulk Inventory Types", min_value=0, max_value=20, value=0)

for i in range(bulk_entries):
    st.markdown(f"**Bulk Parcel Type {i+1}**")
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        quantity = st.number_input(f"Quantity", min_value=1, value=1, key=f"qty_{i}")
    with c2:
        weight = st.number_input("Weight (kg)", value=100.0, key=f"b_wt_{i}")
    with c3:
        length = st.number_input("Length (m)", value=1.0, key=f"b_len_{i}")
    with c4:
        width = st.number_input("Width (m)", value=1.0, key=f"b_wid_{i}")
    with c5:
        height = st.number_input("Height (m)", value=1.0, key=f"b_hei_{i}")

    for _ in range(quantity):
        weights.append(weight)
        lengths.append(length)
        widths.append(width)
        heights.append(height)

areas = [lengths[i] * widths[i] for i in range(len(weights))]
total_weight = sum(weights)
total_area = sum(areas)

# =========================
# 🚛 3D Truck Packing Optimiser
# =========================

def extreme_point_packing(parcel_data, truck_dims):
    return generate_mock_3d_layout(parcel_data, truck_dims)

def layer_based_packing(parcel_data, truck_dims):
    return generate_mock_3d_layout(parcel_data, truck_dims)

def skyline_3d_packing(parcel_data, truck_dims):
    return generate_mock_3d_layout(parcel_data, truck_dims)

def guillotine_3d_packing(parcel_data, truck_dims):
    return generate_mock_3d_layout(parcel_data, truck_dims)

def generate_mock_3d_layout(parcel_data, truck_dims):
    layout = []
    x_cursor, y_cursor, z_cursor = 0, 0, 0
    max_x, max_y, max_z = truck_dims
    spacing = 0.1

    for idx, parcel in enumerate(parcel_data):
        l, w, h = parcel["length"], parcel["width"], parcel["height"]
        if x_cursor + l > max_x:
            x_cursor = 0
            y_cursor += w + spacing
        if y_cursor + w > max_y:
            y_cursor = 0
            z_cursor += h + spacing
        if z_cursor + h > max_z:
            break
        layout.append({
            "id": idx + 1,
            "x": x_cursor,
            "y": y_cursor,
            "z": z_cursor,
            "length": l,
            "width": w,
            "height": h
        })
        x_cursor += l + spacing
    return layout

def visualize_3d_layout(layout, truck_dims, method_name):
    fig = go.Figure()
    for parcel in layout:
        fig.add_trace(go.Mesh3d(
            x=[parcel["x"], parcel["x"] + parcel["length"], parcel["x"] + parcel["length"], parcel["x"],
               parcel["x"], parcel["x"] + parcel["length"], parcel["x"] + parcel["length"], parcel["x"]],
            y=[parcel["y"], parcel["y"], parcel["y"] + parcel["width"], parcel["y"] + parcel["width"],
               parcel["y"], parcel["y"], parcel["y"] + parcel["width"], parcel["y"] + parcel["width"]],
            z=[parcel["z"], parcel["z"], parcel["z"], parcel["z"],
               parcel["z"] + parcel["height"], parcel["z"] + parcel["height"], parcel["z"] + parcel["height"], parcel["z"] + parcel["height"]],
            color='lightblue',
            opacity=0.5,
            name=f"Parcel {parcel['id']}",
            showscale=False
        ))
    fig.update_layout(
        title=f"3D Packing Layout ({method_name})",
        scene=dict(
            xaxis_title='Length (m)',
            yaxis_title='Width (m)',
            zaxis_title='Height (m)',
            xaxis=dict(range=[0, truck_dims[0]]),
            yaxis=dict(range=[0, truck_dims[1]]),
            zaxis=dict(range=[0, truck_dims[2]])
        ),
        margin=dict(l=0, r=0, b=0, t=40)
    )
    st.plotly_chart(fig)

st.markdown("## 🚛 3D Truck Packing Optimiser")

packing_algorithms_3d = {
    "Extreme Point Heuristic": extreme_point_packing,
    "Layer-Based Packing": layer_based_packing,
    "Skyline 3D": skyline_3d_packing,
    "Guillotine 3D": guillotine_3d_packing
}

selected_algo = st.selectbox("Select 3D Packing Algorithm", list(packing_algorithms_3d.keys()))
selected_truck = st.selectbox("Select Truck Type", [v[0] for v in vehicle_types])

if st.button("Run 3D Packing"):
    truck_spec = next(v for v in vehicle_types if v[0] == selected_truck)
    truck_dims = (truck_spec[1], truck_spec[2], truck_spec[3])  # length, width, height

    parcel_data = [
        {"length": lengths[i], "width": widths[i], "height": heights[i], "weight": weights[i]}
        for i in range(len(weights))
    ]

    layout = packing_algorithms_3d[selected_algo](parcel_data, truck_dims)
    visualize_3d_layout(layout, truck_dims, selected_algo)

