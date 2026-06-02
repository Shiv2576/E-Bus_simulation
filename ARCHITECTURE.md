# Architecture

## Overview

The Bus Charging Scheduler is implemented as a **discrete-event simulation system** that evaluates charging decisions based on current network conditions. Rather than relying on fixed assignment rules, the scheduler generates and evaluates multiple charging plans for each bus before selecting the most efficient option.

For every charging decision, the simulation considers:

* Total journey duration
* Expected charging wait time
* Charger congestion
* Station load distribution
* Operator-specific preferences and priorities

The selected charging plan is determined using a weighted scoring model that balances individual, operator, and network objectives.

```python
score = (
    individual_weight * individual_cost
    + operator_weight * operator_cost
    + network_weight * network_cost
    + operator_priority_bonus
)
```

This approach allows scheduling policies to evolve through configuration changes rather than modifications to the core scheduling logic.

---

# Configurable Scheduling Rules

The scheduler was designed to support changing operational requirements through data and configuration.

## Adding New Stations

Stations are defined within scenario data.

```json
{
  "stations": ["A", "B", "C", "D"]
}
```

Adding a new station requires only updating the scenario definition:

```json
{
  "stations": ["A", "B", "C", "D", "E"]
}
```

No changes to the scheduling engine are necessary.

---

## Modifying Charger Capacity

Each station maintains its charger count.

```json
{
  "A": { "chargers": 1 },
  "B": { "chargers": 2 }
}
```

Increasing charger capacity automatically impacts queue lengths, waiting times, and station utilization during simulation.

---

## Adjusting Scheduling Priorities

Scheduling behavior can be tuned using configurable weights.

```python
individual_weight = 1.0
operator_weight = 1.0
network_weight = 1.0
operator_priority_weight = 1000
```

### Weight Effects

| Weight                   | Purpose                                           |
| ------------------------ | ------------------------------------------------- |
| Individual Weight        | Minimize passenger journey time                   |
| Operator Weight          | Favor operator-specific objectives                |
| Network Weight           | Reduce congestion and improve charger utilization |
| Operator Priority Weight | Prioritize selected operators                     |

This mechanism enables policy changes without altering the scheduling engine.

---

# Core Data Structures

The scheduler relies primarily on two data structures.

## Hash Maps (Dictionaries)

Hash maps are used for:

* Station state management
* Charger availability tracking
* Operator metadata
* Station assignment counts
* Simulation statistics

### Example

```python
station_loads = {
    "A": 5,
    "B": 3,
    "C": 7
}
```

### Reason for Selection

Hash maps provide **O(1)** average lookup performance, making them suitable for frequently accessed simulation data.

---

## Priority Queue

Priority queues are used for:

* Charger waiting lines
* Selecting the next bus when a charger becomes available
* Supporting priority-based scheduling policies

### Example

```python
heapq.heappush(queue, bus)
heapq.heappop(queue)
```

### Complexity

| Operation | Complexity |
| --------- | ---------- |
| Insert    | O(log n)   |
| Remove    | O(log n)   |

This ensures efficient operation even as the number of buses grows.

---

# Extensibility & Future Enhancements

The architecture was intentionally designed for future expansion.

## Dynamic Scenario Generation

Current test scenarios are stored as static JSON files.

Future versions may support:

* Custom routes
* Dynamic station creation
* Variable charger capacities
* User-defined bus schedules

This enables large-scale testing without manually constructing scenario files.

---

## Multi-Route Support

The current implementation focuses on a single route corridor.

Future versions can support:

* Multiple routes
* Shared charging infrastructure
* Cross-route congestion effects
* Regional charging networks

---
