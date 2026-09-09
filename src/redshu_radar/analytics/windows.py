from redshu_radar.domain import Snapshot


def select_baseline(
    snapshots: list[Snapshot],
    minimum_hours: float,
    maximum_hours: float,
) -> Snapshot | None:
    if len(snapshots) < 2:
        return None
    ordered = sorted(snapshots, key=lambda snapshot: (snapshot.captured_at, snapshot.id))
    current = ordered[-1]
    target_hours = (minimum_hours + maximum_hours) / 2
    candidates: list[tuple[float, Snapshot]] = []
    for snapshot in ordered[:-1]:
        age_hours = (current.captured_at - snapshot.captured_at).total_seconds() / 3600
        if minimum_hours <= age_hours <= maximum_hours:
            candidates.append((age_hours, snapshot))
    if not candidates:
        return None
    return min(
        candidates,
        key=lambda candidate: (
            abs(candidate[0] - target_hours),
            -candidate[1].captured_at.timestamp(),
        ),
    )[1]
