from typing import Dict, List


def parse_time(time_str: str) -> int:
    """Convert time string like '19:00' to minutes from midnight"""
    try:
        hours, minutes = map(int, time_str.split(":"))
        return hours * 60 + minutes
    except:
        return 0


def format_time(minutes: int) -> str:
    """Convert minutes to HH:MM format"""
    hours = (minutes // 60) % 24
    mins = minutes % 60
    return f"{hours:02d}:{mins:02d}"


def calculate_statistics(buses: List[Dict]) -> Dict:
    """Calculate comprehensive statistics for a list of buses"""
    if not buses:
        return {
            "avg_wait": 0,
            "max_wait": 0,
            "min_wait": 0,
            "avg_journey": 0,
            "max_journey": 0,
            "min_journey": 0,
        }

    wait_times = [b["wait_time"] for b in buses]
    journey_times = [b["journey_time"] for b in buses]

    return {
        "avg_wait": sum(wait_times) / len(wait_times),
        "max_wait": max(wait_times),
        "min_wait": min(wait_times),
        "avg_journey": sum(journey_times) / len(journey_times),
        "max_journey": max(journey_times),
        "min_journey": min(journey_times),
        "total_buses": len(buses),
    }


def get_operator_stats(buses: List[Dict]) -> Dict[str, Dict]:
    """Calculate per-operator statistics"""
    operator_stats = {}

    for bus in buses:
        op = bus["operator"]
        if op not in operator_stats:
            operator_stats[op] = {"total_wait": 0, "total_journey": 0, "count": 0}

        operator_stats[op]["total_wait"] += bus["wait_time"]
        operator_stats[op]["total_journey"] += bus["journey_time"]
        operator_stats[op]["count"] += 1

    for op, stats in operator_stats.items():
        stats["avg_wait"] = (
            stats["total_wait"] / stats["count"] if stats["count"] > 0 else 0
        )
        stats["avg_journey"] = (
            stats["total_journey"] / stats["count"] if stats["count"] > 0 else 0
        )

    return operator_stats
