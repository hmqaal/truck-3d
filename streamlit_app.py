import streamlit as st
import pulp
import plotly.graph_objects as go

# =========================
# Streamlit config
# =========================
st.set_page_config(page_title="Truck Optimiser", layout="wide")
st.title("🚛 3D Truck Packing Optimiser")

# =========================
# Vehicle Types
# =========================
vehicle_types = [
    ("Small van",        1.5,  1.2,   1.1,   360,   1.8,    100),
    ("Medium wheel base",3.0,  1.2,   1.9,  1400,   3.6,    130),
    ("Sprinter van",     4.2,  1.2,   1.75,  950,   5.04,   135),
    ("luton van",        4.0,  2.0,   2.0,  1000,   8.0,    160),
    ("7.5T CS",          6.0,  2.88,  2.2,  2600,  17.28,   150),
    ("18T CS",           7.3,  2.88,  2.3,  9800,  21.024,  175),
    ("40ft CS",         13.5,  3.0,   3.0, 28000,  40.5,    185),
    ("20ft FB",          7.3,  2.4,   3.0, 10500,  17.52,   180),
    ("40ft FB",         13.5,  2.4,   3.0, 30000,  32.4,    190),
    ("40T Low Loader",  13.5,  2.4,   3.0, 30000,  32.4,    195),
]

# =========================
# Inventory Inputs
# =========================
st.header("📦 Inventory Inputs")
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
        heights.append(st.number_input(f"Height {i+1} (m)", key=f"hei_{i}", value=1.0))
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

# =========================
# 3D Packing Algorithm Toggle
# =========================
st.sidebar.header("Packing Algorithm")
algo_choice = st.sidebar.selectbox("Select 3D Packing Algorithm", [
    "Extreme Point Heuristic",
    "Layer-Based Packing",
    "Skyline 3D",
    "Guillotine 3D"
])

# =========================
# Vehicle Setup
# =========================
vehicles = {}
for name, l, w, h, wt_cap, ar_cap, cost in vehicle_types:
    vehicles[name] = {
        "max_length": l,
        "max_width": w,
        "max_height": h,
        "max_weight": wt_cap,
        "max_volume": l * w * h,
        "cost": cost
    }

# =========================
# Feasibility Check
# =========================
parcel_data = []
for i in range(len(weights)):
    parcel_data.append({
        "id": i + 1,
        "length": lengths[i],
        "width": widths[i],
        "height": heights[i],
        "weight": weights[i],
        "volume": lengths[i] * widths[i] * heights[i]
    })

parcel_feasible_vehicles = {}
for i, parcel in enumerate(parcel_data):
    feasible = []
    for name, v in vehicles.items():
        if (
            parcel["weight"] <= v["max_weight"] and
            parcel["volume"] <= v["max_volume"] and
            parcel["length"] <= v["max_length"] and
            parcel["width"] <= v["max_width"] and
            parcel["height"] <= v["max_height"]
        ):
            feasible.append(name)
    if feasible:
        parcel_feasible_vehicles[i] = feasible

valid_parcels = list(parcel_feasible_vehicles.keys())

# =========================
# MILP Optimisation
# =========================
def run_milp_3d(parcel_indices):
    model = pulp.LpProblem("TruckPacking3D", pulp.LpMinimize)
    IJ = [(i, j) for i in parcel_indices for j in parcel_feasible_vehicles[i]]
    x = pulp.LpVariable.dicts("Assign", IJ, cat="Binary")
    y = pulp.LpVariable.dicts("UseVehicle", vehicles.keys(), cat="Binary")

    model += pulp.lpSum(vehicles[j]["cost"] * y[j] for j in vehicles)

    for i in parcel_indices:
        model += pulp.lpSum(x[i, j] for j in parcel_feasible_vehicles[i]) == 1

    for (i, j) in IJ:
        model += x[i, j] <= y[j]

    for j in vehicles:
        feas_i = [i for i in parcel_indices if (i, j) in x]
        if feas_i:
            model += pulp.lpSum(parcel_data[i]["weight"] * x[i, j] for i in feas_i) <= vehicles[j]["max_weight"] * y[j]
            model += pulp.lpSum(parcel_data[i]["volume"] * x[i, j] for i in feas_i) <= vehicles[j]["max_volume"] * y[j]

    solver = pulp.PULP_CBC_CMD(msg=False)
    model.solve(solver)

    assignment = {}
    for (i, j) in IJ:
        if pulp.value(x[i, j]) == 1:
            assignment[i] = j
    return assignment

# =========================
# Mock 3D Layout Generator
# =========================
def generate_mock_3d_layout(parcel_indices, truck_name):
    layout = []
    x_cursor, y_cursor, z_cursor = 0, 0, 0
    spacing = 0.1
    truck = vehicles[truck_name]
    for i in parcel_indices:
        p = parcel_data[i]
        if x_cursor + p["length"] > truck["max_length"]:
            x_cursor = 0
            y_cursor += p["width"] + spacing
        if y_cursor + p["width"] > truck["max_width"]:
            y_cursor = 0
            z_cursor += p["height"] + spacing
        if z_cursor + p["height"] > truck["max_height"]:
            break
        layout.append({
            "id": p["id"],
            "x": x_cursor,
            "y": y_cursor,
            "z": z_cursor,
            "length": p["length"],
            "width": p["width"],
            "height": p["height"]
        })
        x_cursor += p["length"] + spacing
    return layout

# =========================
# 3D Visualisation
# =========================

def visualize_3d_layout(layout, truck_name):
    truck = vehicles[truck_name]
    fig = go.Figure()

    for parcel in layout:
        x0, y0, z0 = parcel["x"], parcel["y"], parcel["z"]
        dx, dy, dz = parcel["length"], parcel["width"], parcel["height"]

        # Define the 8 corners of the box
        x = [x0, x0+dx, x0+dx, x0, x0, x0+dx, x0+dx, x0]
        y = [y0, y0, y0+dy, y0+dy, y0, y0, y0+dy, y0+dy]
        z = [z0, z0, z0, z0, z0+dz, z0+dz, z0+dz, z0+dz]

        # Define the faces of the box using vertex indices
        i = [0, 0, 0, 1, 2, 4, 5, 6, 7, 3, 1, 2]
        j = [1, 2, 4, 5, 6, 5, 6, 7, 3, 0, 5, 6]
        k = [2, 4, 5, 6, 7, 6, 7, 3, 0, 1, 6, 7]

        fig.add_trace(go.Mesh3d(
            x=x, y=y, z=z,
            i=i, j=j, k=k,
            color='lightblue',
            opacity=0.5,
            name=f"Parcel {parcel['id']}",
            showscale=False
        ))

    fig.update_layout(
        title=f"3D Packing Layout for {truck_name}",
        scene=dict(
            xaxis_title='Length (m)',
            yaxis_title='Width (m)',
            zaxis_title='Height (m)',
            xaxis=dict(range=[0, truck["max_length"]]),
            yaxis=dict(range=[0, truck["max_width"]]),
            zaxis=dict(range=[0, truck["max_height"]])
        ),
        margin=dict(l=0, r=0, b=0, t=40)
    )
    st.plotly_chart(fig)

            visualize_3d_layout(layout, truck)
