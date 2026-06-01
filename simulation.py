import heapq
import statistics
from typing import Dict, List, Optional

from models import Bus, Route, Station


class OperatorConfig:
    """Configuration for individual operator priority"""

    def __init__(self, operator_id: str, priority_weight: float = 1.0, name: str = ""):
        self.operator_id = operator_id
        self.priority_weight = priority_weight  # Higher = more priority at chargers
        self.name = name or operator_id


class ScoringSystem:
    def __init__(self, w_individual=1.0, w_operator=1.0, w_overall=1.0):
        self.w_individual = w_individual
        self.w_operator = w_operator
        self.w_overall = w_overall

        self.station_schedule = {}
        self.operator_wait_times: Dict[str, List[float]] = {}
        self.plan_assignments = {}

        # NEW: Per-operator priority configuration
        self.operator_configs: Dict[str, OperatorConfig] = {}

    def add_operator(self, operator_id: str, priority_weight: float = 1.0):
        """Add or update an operator with custom priority"""
        self.operator_configs[operator_id] = OperatorConfig(
            operator_id, priority_weight
        )
        if operator_id not in self.operator_wait_times:
            self.operator_wait_times[operator_id] = []

    def remove_operator(self, operator_id: str):
        """Remove an operator"""
        if operator_id in self.operator_configs:
            del self.operator_configs[operator_id]

    def get_operator_priority(self, operator_id: str) -> float:
        """Get priority weight for an operator (default 1.0)"""
        if operator_id in self.operator_configs:
            return self.operator_configs[operator_id].priority_weight
        return 1.0

    def initialize_station(self, station_name: str):
        if station_name not in self.station_schedule:
            self.station_schedule[station_name] = []
        if station_name not in self.plan_assignments:
            self.plan_assignments[station_name] = 0

    def calculate_plan_score(self, bus, plan, simulation) -> float:
        metrics = self.simulate_plan_with_current_state(bus, plan, simulation)

        individual_cost = metrics["total_journey_time"]
        operator_cost = self._calculate_operator_cost(bus, metrics["wait_time"])
        balance_penalty = self._calculate_balance_penalty(plan)

        # Congestion penalty
        congestion_penalty = 0
        for station in plan:
            current_assignments = self.plan_assignments.get(station, 0)
            congestion_penalty += current_assignments * 200

        # NEW: Operator-specific priority bonus
        # Higher priority operators get lower scores (preferred)
        operator_priority = self.get_operator_priority(bus.operator)
        priority_bonus = -1 * (operator_priority - 1.0) * 500  # Negative = better score

        score = (
            self.w_individual * individual_cost
            + self.w_operator * operator_cost
            + self.w_overall * (balance_penalty + congestion_penalty)
            + priority_bonus  # Priority operators get score reduction
        )

        return score

    def _calculate_balance_penalty(self, plan: List[str]) -> float:
        penalty = 0
        for station in plan:
            count = self.plan_assignments.get(station, 0)
            penalty += (count**2) * 100
        return penalty

    def simulate_plan_with_current_state(self, bus, plan, simulation) -> Dict:
        battery = simulation.route.battery_range
        current_time = bus.arrival_time
        current_location = (
            simulation.route.start_city
            if bus.direction == "forward"
            else simulation.route.end_city
        )
        total_wait = 0
        total_charge = 0

        temp_schedule = {}
        for station_name in self.station_schedule:
            temp_schedule[station_name] = [
                list(x) for x in self.station_schedule[station_name]
            ]

        for charge_station in plan:
            if charge_station not in temp_schedule:
                temp_schedule[charge_station] = []

            distance = simulation.route.get_path_distance(
                current_location, charge_station, bus.direction
            )
            current_time += distance
            battery -= distance

            wait_time = self._calculate_wait_for_station(
                temp_schedule[charge_station], current_time, simulation.charge_time
            )
            total_wait += wait_time

            start_time = current_time + wait_time
            end_time = start_time + simulation.charge_time
            temp_schedule[charge_station].append([start_time, end_time])
            temp_schedule[charge_station].sort()

            battery = simulation.route.battery_range
            total_charge += simulation.charge_time
            current_time = end_time
            current_location = charge_station

        destination = (
            simulation.route.end_city
            if bus.direction == "forward"
            else simulation.route.start_city
        )
        final_distance = simulation.route.get_path_distance(
            current_location, destination, bus.direction
        )
        current_time += final_distance

        return {
            "total_journey_time": current_time - bus.arrival_time,
            "wait_time": total_wait,
            "charge_time": total_charge,
        }

    def _calculate_wait_for_station(
        self, schedule: List[List[int]], arrival_time: int, charge_time: int
    ) -> int:
        if not schedule:
            return 0

        for i, (start, end) in enumerate(schedule):
            if arrival_time >= end:
                if i + 1 < len(schedule):
                    if arrival_time + charge_time <= schedule[i + 1][0]:
                        return 0
                else:
                    return 0
            elif arrival_time < start:
                if arrival_time + charge_time <= start:
                    return 0
                else:
                    return end - arrival_time

        if schedule and arrival_time < schedule[-1][1]:
            return schedule[-1][1] - arrival_time

        return 0

    def _calculate_operator_cost(self, bus, predicted_wait: int) -> float:
        operator = bus.operator

        if operator not in self.operator_wait_times:
            self.operator_wait_times[operator] = []

        temp_waits = self.operator_wait_times[operator] + [predicted_wait]

        if len(temp_waits) < 2:
            return 0

        try:
            variance = statistics.variance(temp_waits)
            return variance
        except:
            return 0

    def update_with_selected_plan(self, bus, plan, simulation):
        battery = simulation.route.battery_range
        current_time = bus.arrival_time
        current_location = (
            simulation.route.start_city
            if bus.direction == "forward"
            else simulation.route.end_city
        )

        for charge_station in plan:
            if charge_station not in self.station_schedule:
                self.station_schedule[charge_station] = []

            distance = simulation.route.get_path_distance(
                current_location, charge_station, bus.direction
            )
            current_time += distance
            battery -= distance

            wait_time = self._calculate_wait_for_station(
                self.station_schedule[charge_station],
                current_time,
                simulation.charge_time,
            )
            start_time = current_time + wait_time
            end_time = start_time + simulation.charge_time

            self.station_schedule[charge_station].append([start_time, end_time])
            self.station_schedule[charge_station].sort()

            self.plan_assignments[charge_station] = (
                self.plan_assignments.get(charge_station, 0) + 1
            )

            battery = simulation.route.battery_range
            current_time = end_time
            current_location = charge_station

    def update_operator_stats(self, bus, actual_wait: int):
        operator = bus.operator
        if operator not in self.operator_wait_times:
            self.operator_wait_times[operator] = []
        self.operator_wait_times[operator].append(actual_wait)

    def calculate_dynamic_priority(self, bus, current_time: int) -> float:
        """
        Calculate dynamic priority for queue ordering.
        HIGHER priority buses get served first.
        Now includes per-operator priority weights.
        """
        # Base wait time priority (buses waiting longer get higher priority)
        actual_waited = (
            current_time - bus.current_station_arrival
            if bus.current_station_arrival > 0
            else 0
        )

        # Battery urgency (lower battery = higher priority)
        battery_deficit = 240 - bus.battery
        battery_urgency = battery_deficit / 240.0 * 100

        # NEW: Operator-specific priority multiplier
        operator_priority = self.get_operator_priority(bus.operator)

        # Priority formula (higher number = higher priority)
        # Negative because heapq is min-heap (we want max priority first)
        priority = -(
            actual_waited
            * 2
            * operator_priority  # Wait time weighted by operator priority
            + battery_urgency * 0.5
            + operator_priority * 100  # Base priority bonus for high-priority operators
        )

        return priority


class Simulation:
    def __init__(self, scoring: ScoringSystem = None):
        self.events = []
        self.stations: Dict[str, Station] = {}
        self.buses: Dict[str, Bus] = {}
        self.charge_time = 25
        self.route = Route()
        self.scoring = scoring or ScoringSystem()
        self.charger_queues: Dict[str, List[str]] = {}

    def add_station(self, station: Station):
        self.stations[station.name] = station
        self.charger_queues[station.name] = []
        self.scoring.initialize_station(station.name)

    def add_bus(self, bus: Bus):
        self.buses[bus.id] = bus
        # Auto-register operator if not exists
        if bus.operator not in self.scoring.operator_configs:
            self.scoring.add_operator(bus.operator, priority_weight=1.0)

    def add_operator(self, operator_id: str, priority_weight: float = 1.0):
        """Add or update an operator with custom priority"""
        self.scoring.add_operator(operator_id, priority_weight)

    def remove_operator(self, operator_id: str):
        """Remove an operator"""
        self.scoring.remove_operator(operator_id)

    def schedule_event(
        self,
        time: int,
        event_type: str,
        bus_id: str,
        location: str = "",
        distance_to_travel: int = 0,
    ):
        heapq.heappush(
            self.events, (time, event_type, bus_id, location, distance_to_travel)
        )

    def start_journey(self, bus_id: str):
        bus = self.buses[bus_id]
        bus.journey_start_time = bus.arrival_time

        if bus.direction == "forward":
            start_location = self.route.start_city
            stops = self.route.stops
            first_stop = stops[1] if len(stops) > 1 else self.route.end_city
        else:
            start_location = self.route.end_city
            stops = list(reversed(self.route.stops))
            first_stop = stops[1] if len(stops) > 1 else self.route.start_city

        distance = self.route.get_distance(start_location, first_stop)
        if distance == 0:
            destination = (
                self.route.end_city
                if bus.direction == "forward"
                else self.route.start_city
            )
            distance = self.route.get_path_distance(
                start_location, destination, bus.direction
            )
            first_stop = destination

        arrival_time = bus.arrival_time + distance
        self.schedule_event(
            arrival_time, "arrive_at_station", bus.id, first_stop, distance
        )

    def optimize_all_buses(self):
        sorted_buses = sorted(self.buses.items(), key=lambda x: x[1].arrival_time)

        for bus_id, bus in sorted_buses:
            self.optimize_single_bus(bus)

    def optimize_single_bus(self, bus: Bus):
        plans = self.route.get_minimal_feasible_plans(bus)

        if not plans:
            return

        best_plan = None
        best_score = float("inf")

        for plan in plans:
            score = self.scoring.calculate_plan_score(bus, plan, self)
            if score < best_score:
                best_score = score
                best_plan = plan

        if best_plan is not None:
            bus.charging_stops = best_plan
            self.scoring.update_with_selected_plan(bus, best_plan, self)

    def run(self, end_time: int = 5000):
        self.optimize_all_buses()

        for station in self.stations.values():
            station.reset()

        self.events = []
        for bus_id in self.buses:
            self.start_journey(bus_id)

        while self.events and self.events[0][0] <= end_time:
            time, event_type, bus_id, location, distance = heapq.heappop(self.events)

            if event_type == "charger_available":
                self.handle_charger_available(time, location)
                continue

            if bus_id not in self.buses:
                continue

            bus = self.buses[bus_id]

            if event_type == "arrive_at_station":
                self.handle_arrival_at_station(time, bus, location, distance)
            elif event_type == "charge_complete":
                self.handle_charge_complete(time, bus, location)

    def handle_arrival_at_station(
        self, time: int, bus: Bus, station_name: str, distance_traveled: int
    ):
        bus.battery -= distance_traveled
        bus.current_location = station_name
        bus.total_travel_time += distance_traveled
        bus.current_station_arrival = time

        destination = (
            self.route.end_city if bus.direction == "forward" else self.route.start_city
        )

        if station_name == destination:
            bus.completed = True
            self.scoring.update_operator_stats(bus, bus.total_wait_time)
            return

        if station_name in bus.charging_stops:
            self.request_charging(time, bus, station_name)
        else:
            self.continue_journey(time, bus, station_name)

    def request_charging(self, time: int, bus: Bus, station_name: str):
        station = self.stations[station_name]

        if station.get_available_chargers_count(time) > 0:
            self.initiate_charging(time, bus, station_name)
        else:
            self.charger_queues[station_name].append(bus.id)
            earliest_free = station.get_earliest_available_time()
            self.schedule_event(earliest_free, "charger_available", "", station_name)

    def handle_charger_available(self, time: int, station_name: str):
        station = self.stations[station_name]

        while (
            self.charger_queues.get(station_name)
            and station.get_available_chargers_count(time) > 0
        ):
            # Get priorities for all waiting buses
            bus_priorities = []
            for bus_id in self.charger_queues[station_name]:
                if bus_id in self.buses:
                    bus = self.buses[bus_id]
                    # Use dynamic priority (now operator-aware)
                    priority = self.scoring.calculate_dynamic_priority(bus, time)
                    bus_priorities.append((priority, bus_id))

            if not bus_priorities:
                break

            # Sort by priority (lowest number = highest priority in min-heap)
            bus_priorities.sort()

            # Serve highest priority bus first
            _, selected_bus_id = bus_priorities[0]
            self.charger_queues[station_name].remove(selected_bus_id)

            bus = self.buses[selected_bus_id]
            self.initiate_charging(time, bus, station_name)

            # Update time for next iteration
            time = station.get_earliest_available_time()

    def initiate_charging(self, time: int, bus: Bus, station_name: str):
        """
        Start charging a bus at a station.
        Tracks wait time correctly for both bus and station.
        """
        station = self.stations[station_name]

        # Calculate actual wait time based on when bus arrived
        arrival_time = (
            bus.current_station_arrival if bus.current_station_arrival > 0 else time
        )
        actual_wait = time - arrival_time

        # Update bus statistics
        bus.total_wait_time += actual_wait

        # Use arrival_time so station tracks wait correctly
        start_time, end_time = station.occupy_charger(arrival_time, self.charge_time)
        bus.total_charge_time += self.charge_time

        # Schedule completion event
        self.schedule_event(end_time, "charge_complete", bus.id, station_name)

    def handle_charge_complete(self, time: int, bus: Bus, station_name: str):
        bus.battery = self.route.battery_range

        if station_name in self.charger_queues and self.charger_queues[station_name]:
            self.schedule_event(time, "charger_available", "", station_name)

        self.continue_journey(time, bus, station_name)

    def continue_journey(self, time: int, bus: Bus, from_station: str):
        if bus.direction == "forward":
            stops = self.route.stops
        else:
            stops = list(reversed(self.route.stops))

        try:
            current_idx = stops.index(from_station)
            next_stop = stops[current_idx + 1]
        except (ValueError, IndexError):
            next_stop = (
                self.route.end_city
                if bus.direction == "forward"
                else self.route.start_city
            )

        distance = self.route.get_distance(from_station, next_stop)
        if distance == 0:
            distance = self.route.get_path_distance(
                from_station, next_stop, bus.direction
            )

        arrival_time = time + distance
        self.schedule_event(
            arrival_time, "arrive_at_station", bus.id, next_stop, distance
        )

    def get_results(self):
        """Return simulation results including station statistics"""
        results = {
            "forward": [],
            "reverse": [],
            "station_stats": [],
            "operator_priorities": {},  # NEW: Include operator config
        }

        for bus_id, bus in self.buses.items():
            if bus.completed:
                journey_time = (
                    bus.total_wait_time + bus.total_charge_time + bus.total_travel_time
                )
                bus_data = {
                    "id": bus.id,
                    "operator": bus.operator,
                    "plan": bus.charging_stops,
                    "journey_time": journey_time,
                    "wait_time": bus.total_wait_time,
                    "charge_time": bus.total_charge_time,
                    "travel_time": bus.total_travel_time,
                }

                if bus.direction == "forward":
                    results["forward"].append(bus_data)
                else:
                    results["reverse"].append(bus_data)

        # Station statistics
        for station_name, station in self.stations.items():
            stats = station.get_utilization_stats()
            results["station_stats"].append(
                {
                    "Station": station_name,
                    "Chargers": stats["total_chargers"],
                    "Buses Served": stats["total_buses_served"],
                    "Avg Wait (min)": f"{stats['avg_wait_time']:.1f}",
                    "Utilization": stats["charger_utilization"],
                }
            )

        # Operator priorities
        for op_id, op_config in self.scoring.operator_configs.items():
            results["operator_priorities"][op_id] = op_config.priority_weight

        return results
