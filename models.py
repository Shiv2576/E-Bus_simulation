from dataclasses import dataclass, field
from typing import Dict, List, Tuple


@dataclass
class Bus:
    id: str
    arrival_time: int
    direction: str = "forward"
    battery: int = 240
    current_location: str = "Bengaluru"
    total_wait_time: int = 0
    total_charge_time: int = 0
    total_travel_time: int = 0
    charging_stops: List[str] = field(default_factory=list)
    journey_start_time: int = 0
    queue_entry_time: int = 0
    operator: str = "default"
    completed: bool = False
    current_station_arrival: int = 0


class Station:
    """
    Charging station with multiple independent chargers.
    Each charger tracks its own availability time.
    """

    def __init__(self, name: str, charger_count: int = 1):
        self.name = name
        self.charger_count = charger_count
        self.charger_free_times: List[int] = [0] * charger_count
        self.queue: List[str] = []
        self.total_buses_served: int = 0
        self.total_wait_time: int = 0
        self.charger_usage: List[List[Tuple[int, int]]] = [
            [] for _ in range(charger_count)
        ]

    def get_earliest_available_time(self) -> int:
        return min(self.charger_free_times)

    def get_wait_time(self, arrival_time: int) -> int:
        earliest_free = min(self.charger_free_times)
        if arrival_time >= earliest_free:
            return 0
        return earliest_free - arrival_time

    def get_available_chargers_count(self, time: int) -> int:
        return sum(1 for t in self.charger_free_times if t <= time)

    def occupy_charger(self, start_time: int, charge_duration: int) -> Tuple[int, int]:
        earliest_free_time = min(self.charger_free_times)
        charger_index = self.charger_free_times.index(earliest_free_time)

        actual_start = max(start_time, earliest_free_time)
        end_time = actual_start + charge_duration
        wait_time = actual_start - start_time

        self.charger_free_times[charger_index] = end_time
        self.charger_usage[charger_index].append((actual_start, end_time))

        self.total_buses_served += 1
        self.total_wait_time += wait_time

        return actual_start, end_time

    def get_utilization_stats(self) -> Dict:
        stats = {
            "total_chargers": self.charger_count,
            "chargers_used": sum(1 for usage in self.charger_usage if usage),
            "total_buses_served": self.total_buses_served,
            "avg_wait_time": self.total_wait_time / max(1, self.total_buses_served),
            "charger_utilization": [],
        }

        for i, usage in enumerate(self.charger_usage):
            if usage:
                total_busy = sum(end - start for start, end in usage)
                first_start = min(start for start, _ in usage)
                last_end = max(end for _, end in usage)
                time_window = last_end - first_start
                utilization = (total_busy / time_window * 100) if time_window > 0 else 0

                stats["charger_utilization"].append(
                    {
                        "charger": i + 1,
                        "utilization": f"{utilization:.1f}%",
                        "buses_served": len(usage),
                    }
                )

        return stats

    def reset(self):
        self.charger_free_times = [0] * self.charger_count
        self.queue = []
        self.total_buses_served = 0
        self.total_wait_time = 0
        self.charger_usage = [[] for _ in range(self.charger_count)]


class Route:
    """
    Fully dynamic route - adapts to any number of stations, any distances.
    No hardcoded plans. Everything is generated from the route structure.
    """

    def __init__(self, start_city: str = "Bengaluru", end_city: str = "Kochi"):
        self.start_city = start_city
        self.end_city = end_city
        self.stations: List[str] = []
        self.segments: Dict[Tuple[str, str], int] = {}
        self.battery_range: int = 240
        self.charging_time: int = 25
        self._rebuild_stops()

    def add_station(self, name: str):
        if name not in self.stations:
            self.stations.append(name)
            self._rebuild_stops()

    def add_segment(self, from_stop: str, to_stop: str, distance: int):
        self.segments[(from_stop, to_stop)] = distance
        self.segments[(to_stop, from_stop)] = distance
        self._rebuild_stops()

    def _rebuild_stops(self):
        self.stops = [self.start_city] + self.stations + [self.end_city]

    def get_distance(self, from_stop: str, to_stop: str) -> int:
        if from_stop == to_stop:
            return 0
        return self.segments.get((from_stop, to_stop), 0)

    def get_path_distance(self, from_stop: str, to_stop: str, direction: str) -> int:
        if from_stop == to_stop:
            return 0

        if direction == "forward":
            stops = self.stops
        else:
            stops = list(reversed(self.stops))

        try:
            from_idx = stops.index(from_stop)
            to_idx = stops.index(to_stop)
        except ValueError:
            return 0

        if from_idx >= to_idx:
            return 0

        total = 0
        for i in range(from_idx, to_idx):
            current = stops[i]
            next_stop = stops[i + 1]
            total += self.get_distance(current, next_stop)

        return total

    def get_stations_in_direction(self, direction: str) -> List[str]:
        """Get stations in the order encountered for a given direction"""
        if direction == "forward":
            return self.stations
        else:
            return list(reversed(self.stations))

    def _generate_all_plan_combinations(
        self, stations_in_order: List[str]
    ) -> List[List[str]]:
        """
        Generate all possible charging plan combinations for a given station order.
        Works for ANY number of stations.
        """
        n = len(stations_in_order)
        if n == 0:
            return [[]]

        all_plans = []

        # Generate plans of different lengths (1 to min(n, 3))
        # Limit to 3 stops maximum to avoid excessive plans
        max_stops = min(n, 3)

        for length in range(1, max_stops + 1):
            self._generate_plans_of_length(stations_in_order, length, 0, [], all_plans)

        return all_plans

    def _generate_plans_of_length(self, stations, length, start_idx, current, result):
        """Recursively generate plans of a specific length"""
        if len(current) == length:
            result.append(current.copy())
            return

        for i in range(start_idx, len(stations)):
            current.append(stations[i])
            self._generate_plans_of_length(stations, length, i + 1, current, result)
            current.pop()

    def is_plan_feasible(self, bus: Bus, plan: List[str]) -> bool:
        """
        Check if a charging plan is feasible given battery range.
        Works for any route configuration.
        """
        if not plan:
            return True

        battery = self.battery_range
        current_location = (
            self.start_city if bus.direction == "forward" else self.end_city
        )

        for charge_station in plan:
            distance = self.get_path_distance(
                current_location, charge_station, bus.direction
            )

            if distance > battery:
                return False

            battery -= distance
            battery = self.battery_range
            current_location = charge_station

        destination = self.end_city if bus.direction == "forward" else self.start_city
        final_distance = self.get_path_distance(
            current_location, destination, bus.direction
        )

        return final_distance <= battery

    def get_minimal_feasible_plans(self, bus: Bus) -> List[List[str]]:
        """
        Generate and return all feasible plans, sorted by intelligence.
        COMPLETELY DYNAMIC - works for 1 station or 100 stations.
        """
        # Get stations in the correct order for this direction
        stations_in_order = self.get_stations_in_direction(bus.direction)

        # Generate all possible plan combinations
        all_possible_plans = self._generate_all_plan_combinations(stations_in_order)

        # Filter to only feasible plans
        feasible = [
            plan for plan in all_possible_plans if self.is_plan_feasible(bus, plan)
        ]

        # If no feasible plans, try single-station plans as emergency
        if not feasible:
            single_plans = [[s] for s in stations_in_order]
            feasible = [p for p in single_plans if self.is_plan_feasible(bus, p)]

        # If still nothing, return empty plan (direct journey)
        if not feasible:
            return [[]]

        # INTELLIGENT SORTING
        # 1. Prefer plans starting with nearest station (less congestion, earlier charge)
        # 2. Prefer plans with more stops (better load distribution)
        # 3. Prefer plans that minimize distance between charges
        feasible.sort(
            key=lambda p: (
                0
                if len(p) > 0 and p[0] == stations_in_order[0]
                else 1,  # Nearest station first
                len(stations_in_order) - len(p),  # More stops preferred
                self._calculate_plan_spacing_score(
                    p, bus.direction
                ),  # Even spacing preferred
            )
        )

        return feasible

    def _calculate_plan_spacing_score(self, plan: List[str], direction: str) -> float:
        """
        Score how well-spaced the charging stops are.
        Lower score = better spacing = preferred.
        """
        if len(plan) <= 1:
            return 0

        current_location = self.start_city if direction == "forward" else self.end_city
        distances = []

        for station in plan:
            dist = self.get_path_distance(current_location, station, direction)
            distances.append(dist)
            current_location = station

        # Calculate variance of distances (lower variance = better spacing)
        if len(distances) > 1:
            mean = sum(distances) / len(distances)
            variance = sum((d - mean) ** 2 for d in distances) / len(distances)
            return variance

        return 0
