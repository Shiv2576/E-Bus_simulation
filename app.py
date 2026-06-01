import pandas as pd
import streamlit as st
from data_loader import load_scenarios
from models import Bus, Route, Station
from simulation import ScoringSystem, Simulation
from utils import calculate_statistics, get_operator_stats, parse_time

st.set_page_config(
    page_title="E-Bus Fleet Simulator",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded",
)


st.markdown(
    """
<style>
    .stApp { background-color: #0e1117; }
    .stButton button { background-color: #1f77b4; color: white; border: none; border-radius: 4px; width: 100%; }
    .stButton button:hover { background-color: #2c8fd4; }
    div[data-testid="stMetricValue"] { color: #ffffff; }
    .stSlider label, .stNumberInput label { color: #a0a0a0 !important; }
</style>
""",
    unsafe_allow_html=True,
)


st.markdown(
    "<h1 style='color:#ffffff;'>E-Bus Fleet Simulator</h1>", unsafe_allow_html=True
)
st.markdown(
    "<p style='color:#a0a0a0;'>Route Configuration | Operator Management | Scenario Analysis</p>",
    unsafe_allow_html=True,
)


DEFAULT_CONFIG = {
    "start_city": "Bengaluru",
    "end_city": "Kochi",
    "battery_range": 240,
    "charging_time": 25,
    "stations": [
        {"name": "A", "charger_count": 1},
        {"name": "B", "charger_count": 1},
        {"name": "C", "charger_count": 1},
        {"name": "D", "charger_count": 1},
    ],
    "distances": {
        ("Bengaluru", "A"): 100,
        ("A", "B"): 120,
        ("B", "C"): 100,
        ("C", "D"): 120,
        ("D", "Kochi"): 100,
    },
}


def init_session():
    if "init" not in st.session_state:
        st.session_state.init = True
        st.session_state.start_city = DEFAULT_CONFIG["start_city"]
        st.session_state.end_city = DEFAULT_CONFIG["end_city"]
        st.session_state.battery_range = DEFAULT_CONFIG["battery_range"]
        st.session_state.charging_time = DEFAULT_CONFIG["charging_time"]
        st.session_state.stations_config = [
            s.copy() for s in DEFAULT_CONFIG["stations"]
        ]
        st.session_state.distance_config = DEFAULT_CONFIG["distances"].copy()
        st.session_state.results = None
        st.session_state.operators = {"kpn": 1.0, "freshbus": 1.0, "flixbus": 1.0}


init_session()


with st.sidebar:
    st.markdown("### Route Configuration")

    if st.button("Reset to Default"):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()

    st.divider()

    c1, c2 = st.columns(2)
    with c1:
        st.session_state.start_city = st.text_input(
            "Start", value=st.session_state.start_city, label_visibility="collapsed"
        )
    with c2:
        st.session_state.end_city = st.text_input(
            "End", value=st.session_state.end_city, label_visibility="collapsed"
        )

    st.divider()
    st.markdown("**Settings**")
    st.session_state.battery_range = st.number_input(
        "Battery Range (km)", 100, 1000, value=st.session_state.battery_range, step=10
    )
    st.session_state.charging_time = st.slider(
        "Charging Time (min)", 10, 60, value=st.session_state.charging_time, step=5
    )

    st.divider()
    st.markdown("**Stations**")

    with st.form("add_station", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            ns = st.text_input(
                "Name", placeholder="Station", label_visibility="collapsed"
            )
        with c2:
            nc = st.number_input("Chargers", 1, 10, 1, label_visibility="collapsed")
        if st.form_submit_button("Add Station"):
            if ns and ns not in [s["name"] for s in st.session_state.stations_config]:
                st.session_state.stations_config.append(
                    {"name": ns, "charger_count": nc}
                )
                st.session_state.distance_config = {}
                st.rerun()

    for i, s in enumerate(st.session_state.stations_config):
        c1, c2, c3 = st.columns([3, 1, 1])
        with c1:
            st.markdown(s["name"])
        with c2:
            st.session_state.stations_config[i]["charger_count"] = st.number_input(
                "Ch",
                1,
                10,
                value=s["charger_count"],
                key=f"ch_{i}",
                label_visibility="collapsed",
            )
        with c3:
            if st.button("X", key=f"del_{i}"):
                st.session_state.stations_config.pop(i)
                st.session_state.distance_config = {}
                st.rerun()

    if st.session_state.stations_config:
        st.divider()
        st.markdown("**Distances (km)**")

        if not st.session_state.distance_config:
            dc = {}
            stops = (
                [st.session_state.start_city]
                + [s["name"] for s in st.session_state.stations_config]
                + [st.session_state.end_city]
            )
            for i in range(len(stops) - 1):
                dc[(stops[i], stops[i + 1])] = DEFAULT_CONFIG["distances"].get(
                    (stops[i], stops[i + 1]), 100
                )
            st.session_state.distance_config = dc

        stops = (
            [st.session_state.start_city]
            + [s["name"] for s in st.session_state.stations_config]
            + [st.session_state.end_city]
        )
        for i in range(len(stops) - 1):
            f, t = stops[i], stops[i + 1]
            st.caption(f"{f} to {t}")
            cv = st.session_state.distance_config.get((f, t), 100)
            st.session_state.distance_config[(f, t)] = st.number_input(
                "km",
                10,
                1000,
                value=cv,
                step=10,
                key=f"d_{f}_{t}",
                label_visibility="collapsed",
            )

        st.metric("Total", f"{sum(st.session_state.distance_config.values())} km")


scenarios = load_scenarios()
if not scenarios:
    st.error("No scenarios found.")
else:
    s_names = [s["name"] for s in scenarios]

    tab1, tab2 = st.tabs(["Simulation", "Operators"])

    with tab1:
        selected = st.multiselect("Select Scenarios", s_names, default=[s_names[0]])

        st.divider()
        st.markdown("**Optimization Weights**")
        c1, c2, c3 = st.columns(3)
        with c1:
            wi = st.slider("Individual", 0.0, 5.0, 1.0, 0.1)
        with c2:
            wo = st.slider("Operator", 0.0, 5.0, 1.0, 0.1)
        with c3:
            wn = st.slider("Network", 0.0, 5.0, 1.0, 0.1)

        st.divider()

        if st.button("Run Simulation", type="primary"):
            if not st.session_state.stations_config:
                st.error("Add stations")
            elif not selected:
                st.error("Select scenarios")
            else:
                results = {}
                pb = st.progress(0)

                for idx, name in enumerate(selected):
                    route = Route(
                        st.session_state.start_city, st.session_state.end_city
                    )
                    for s in st.session_state.stations_config:
                        route.add_station(s["name"])
                    for (f, t), d in st.session_state.distance_config.items():
                        route.add_segment(f, t, d)
                    route.battery_range = st.session_state.battery_range
                    route.charging_time = st.session_state.charging_time

                    scoring = ScoringSystem(wi, wo, wn)
                    for op_id, pri in st.session_state.operators.items():
                        scoring.add_operator(op_id, pri)

                    sim = Simulation(scoring)
                    sim.route = route
                    sim.charge_time = st.session_state.charging_time

                    for s in st.session_state.stations_config:
                        sim.add_station(Station(s["name"], s["charger_count"]))

                    sc = scenarios[s_names.index(name)]
                    for bd in sc["buses"]:
                        sim.add_bus(
                            Bus(
                                id=bd["id"],
                                arrival_time=parse_time(bd["departure"]),
                                direction=bd["direction"],
                                battery=st.session_state.battery_range,
                                operator=bd["operator"],
                            )
                        )

                    sim.run(5000)
                    results[name] = sim.get_results()
                    pb.progress((idx + 1) / len(selected))

                st.session_state.results = results
                st.success(f"Completed {len(selected)} scenarios")

    with tab2:
        st.markdown("**Operator Priorities**")
        st.caption("Higher value = priority at charging stations")

        with st.expander("Add Operator"):
            c1, c2 = st.columns(2)
            with c1:
                no = st.text_input("ID", key="new_op", placeholder="operator_id")
            with c2:
                np = st.number_input("Priority", 0.1, 5.0, 1.0, 0.1, key="new_pr")
            if st.button("Add") and no and no not in st.session_state.operators:
                st.session_state.operators[no] = np
                st.rerun()

        st.divider()

        for op in sorted(st.session_state.operators.keys()):
            c1, c2, c3 = st.columns([2, 2, 1])
            with c1:
                st.markdown(op.upper())
            with c2:
                st.session_state.operators[op] = st.slider(
                    "Priority",
                    0.1,
                    5.0,
                    value=st.session_state.operators[op],
                    step=0.1,
                    key=f"op_{op}",
                    label_visibility="collapsed",
                )
            with c3:
                if (
                    st.button("X", key=f"rm_{op}")
                    and len(st.session_state.operators) > 1
                ):
                    del st.session_state.operators[op]
                    st.rerun()

        if st.button("Reset Operators"):
            st.session_state.operators = {"kpn": 1.0, "freshbus": 1.0, "flixbus": 1.0}
            st.rerun()


if st.session_state.get("results"):
    results = st.session_state.results

    st.divider()
    st.markdown("## Results")

    if len(results) > 1:
        st.markdown("### Comparison")
        cd = []
        for name, data in results.items():
            ab = data["forward"] + data["reverse"]
            if ab:
                aw = sum(b["wait_time"] for b in ab) / len(ab)
                aj = sum(b["journey_time"] for b in ab) / len(ab)
                cd.append(
                    {
                        "Scenario": name,
                        "Buses": len(ab),
                        "Avg Wait": f"{aw:.1f}",
                        "Max Wait": max(b["wait_time"] for b in ab),
                        "Avg Journey": f"{aj:.1f}",
                    }
                )
        if cd:
            st.dataframe(pd.DataFrame(cd), use_container_width=True, hide_index=True)

    st.markdown("### Details")
    tabs = st.tabs(list(results.keys()))

    for tab, (name, data) in zip(tabs, results.items()):
        with tab:
            ab = data["forward"] + data["reverse"]
            if ab:
                c1, c2, c3, c4, c5 = st.columns(5)
                c1.metric("Buses", len(ab))
                c2.metric(
                    "Avg Wait", f"{sum(b['wait_time'] for b in ab) / len(ab):.1f}m"
                )
                c3.metric("Max Wait", f"{max(b['wait_time'] for b in ab)}m")
                c4.metric("Forward", len(data["forward"]))
                c5.metric("Reverse", len(data["reverse"]))

            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**Forward**")
                if data["forward"]:
                    df = pd.DataFrame(data["forward"])
                    df["Plan"] = df["plan"].apply(lambda x: ">".join(x))
                    st.dataframe(
                        df[
                            ["id", "operator", "Plan", "journey_time", "wait_time"]
                        ].rename(
                            columns={
                                "id": "Bus",
                                "operator": "Op",
                                "Plan": "Stops",
                                "journey_time": "Total",
                                "wait_time": "Wait",
                            }
                        ),
                        use_container_width=True,
                        hide_index=True,
                    )

            with c2:
                st.markdown("**Reverse**")
                if data["reverse"]:
                    df = pd.DataFrame(data["reverse"])
                    df["Plan"] = df["plan"].apply(lambda x: ">".join(x))
                    st.dataframe(
                        df[
                            ["id", "operator", "Plan", "journey_time", "wait_time"]
                        ].rename(
                            columns={
                                "id": "Bus",
                                "operator": "Op",
                                "Plan": "Stops",
                                "journey_time": "Total",
                                "wait_time": "Wait",
                            }
                        ),
                        use_container_width=True,
                        hide_index=True,
                    )

            if ab:
                st.markdown("**Operators**")
                os = get_operator_stats(ab)
                if os:
                    od = [
                        {
                            "Operator": op.upper(),
                            "Buses": s["count"],
                            "Avg Wait": f"{s['avg_wait']:.1f}m",
                            "Avg Journey": f"{s['avg_journey']:.1f}m",
                        }
                        for op, s in os.items()
                    ]
                    st.dataframe(
                        pd.DataFrame(od), use_container_width=True, hide_index=True
                    )

            st.markdown("**Stations**")
            ss = data.get("station_stats", [])
            if ss:
                sd = [
                    {
                        "Station": s["Station"],
                        "Chargers": s["Chargers"],
                        "Served": s["Buses Served"],
                        "Avg Wait": s["Avg Wait (min)"],
                    }
                    for s in ss
                ]
                st.dataframe(
                    pd.DataFrame(sd), use_container_width=True, hide_index=True
                )

else:
    st.info("Configure route and operators, then run simulation.")
    st.divider()
    st.markdown("### Available Scenarios")
    cols = st.columns(3)
    for i, sc in enumerate(scenarios):
        with cols[i % 3]:
            fwd = sum(1 for b in sc["buses"] if b["direction"] == "forward")
            rev = sum(1 for b in sc["buses"] if b["direction"] == "reverse")
            st.markdown(f"**{sc['name']}**")
            st.caption(f"{sc['description']}")
            st.caption(f"{len(sc['buses'])} buses ({fwd}F, {rev}R)")
            st.divider()


st.divider()
st.caption("E-Bus Fleet Simulator v3.0")
