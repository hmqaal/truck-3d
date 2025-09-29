import streamlit as st
import pulp
import plotly.graph_objects as go

# =========================
# 3D Packing Algorithm Definitions
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

# =========================
# 3D Optimisation Logic
# =========================

def run_3d_optimizer(parcel_data, vehicle_types, selected_algo):
    # Build vehicle clones
    vehicles = {}
    for name, l, w, h, wt_cap, vol_cap, cost in vehicle_types:
        for i in range(1, 6):
            truck_name = f"{name}{i}"
            vehicles[truck_name] = {
                "base": name,
                "max_length": l,
                "max_width": w,
                "max_height": h,
                "max_weight": wt_cap,
                "max_volume": vol_cap,
                "cost": cost
            }

    # Feasibility check
    feasible_map = {}
    for i, parcel in enumerate(parcel_data):
        fits = []
        vol = parcel["length"] * parcel["width"] * parcel["height"]
        for truck_name, v in vehicles.items():
            if parcel["weight"] <= v["max_weight"] and vol <= v["max_volume"]:
                if parcel["length"] <= v["max_length"] and parcel["width"] <= v["max_width"] and parcel["height"] <= v["max_height"]:
                    fits.append(truck_name)
        if fits:
            feasible_map[i] = fits

    if not feasible_map:
        st.error("No parcels fit in any truck.")
        return

    # MILP model
    model = pulp.LpProblem("3D Truck Optimisation", pulp.LpMinimize)
    IJ = [(i, j) for i in feasible_map for j in feasible_map[i]]
    x = pulp.LpVariable.dicts("Assign", IJ, cat="Binary")
    y = pulp.LpVariable.dicts("UseTruck", vehicles.keys(), cat="Binary")

    model += pulp.lpSum(vehicles[j]["cost"] * y[j] for j in vehicles)

    for i in feasible_map:
        model += pulp.lpSum(x[i, j] for j in feasible_map[i]) == 1

    for (i, j) in IJ:
        model += x[i, j] <= y[j]

    for j in vehicles:
        model += pulp.lpSum(parcel_data[i]["weight"] * x[i, j] for i in feasible_map if (i, j) in x) <= vehicles[j]["max_weight"] * y[j]
        model += pulp.lpSum(parcel_data[i]["length"] * parcel_data[i]["width"] * parcel_data[i]["height"] * x[i, j] for i in feasible_map if (i, j) in x) <= vehicles[j]["max_volume"] * y[j]

    solver = pulp.PULP_CBC_CMD(msg=False, timeLimit=45)
    status = model.solve(solver)

    if pulp.LpStatus[model.status] != "Optimal":
        st.error("MILP solver failed to find optimal solution.")
        return

    assignment = {i: j for (i, j) in IJ if pulp.value(x[i, j]) == 1}
    used_trucks = sorted(set(assignment.values()), key=lambda t: vehicles[t]["cost"])

    # Generate layout per truck
    for truck in used_trucks:
        truck_dims = (
            vehicles[truck]["max_length"],
            vehicles[truck]["max_width"],
            vehicles[truck]["max_height"]
        )
        assigned = [parcel_data[i] for i in assignment if assignment[i] == truck]
        layout = packing_algorithms_3d[selected_algo](assigned, truck_dims)
        st.markdown(f"### Truck: {truck} ({vehicles[truck]['base']})")
        visualize_3d_layout(layout, truck_dims, selected_algo)

# =========================
# Streamlit UI
# =========================

st.markdown("## 🚛 3D Truck Packing Optimiser")

packing_algorithms_3d = {
    "Extreme Point Heuristic": extreme_point_packing,
    "Layer-Based Packing": layer_based_packing,
    "Skyline 3D": skyline_3d_packing,
    "Guillotine 3D": guillotine_3d_packing
}

selected_algo = st.sidebar.selectbox("Select 3D Packing Algorithm", list(packing_algorithms_3d.keys()))

# Reuse parcel inputs from existing app
parcel_data = [
    {"length": st.session_state.get(f"len_{i}", 1.0),
     "width": st.session_state.get(f"wid_{i}", 1.0),
     "height": st.session_state.get(f"hei_{i}", 1.0),
     "weight": st.session_state.get(f"wt_{i}", 100.0)}
    for i in range(st.session_state.get("Number of Individual Inventory", 0))
]

bulk_entries = st.session_state.get("Number of Bulk Inventory Types", 0)
for i in range(bulk_entries):
    qty = st.session_state.get(f"qty_{i}", 1)
    for _ in range(qty):
        parcel_data.append({
            "length": st.session_state.get(f"b_len_{i}", 1.0),
            "width": st.session_state.get(f"b_wid_{i}", 1.0),
            "height": st.session_state.get(f"b_hei_{i}", 1.0),
            "weight": st.session_state.get(f"b_wt_{i}", 100.0)
        })

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

if st.button("Run 3D Optimisation"):
    run_3d_optimizer(parcel_data, vehicle_types, selected_algo)

