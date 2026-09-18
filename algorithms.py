from time import perf_counter

PRIORITY_WEIGHT = {"high": 1, "medium": 2, "low": 3}

def compare(a, b, key):
    if key == "priority":
        return PRIORITY_WEIGHT[a["priority"]] - PRIORITY_WEIGHT[b["priority"]]
    if a["due_date"] < b["due_date"]:
        return -1
    if a["due_date"] > b["due_date"]:
        return 1
    return 0

def merge_sort(items, key):
    # Manual Merge Sort — no Python sorted()/list.sort()
    if len(items) <= 1:
        return items[:]
    mid = len(items) // 2
    left = merge_sort(items[:mid], key)
    right = merge_sort(items[mid:], key)
    result = []
    i = j = 0
    while i < len(left) and j < len(right):
        if compare(left[i], right[j], key) <= 0:
            result.append(left[i])
            i += 1
        else:
            result.append(right[j])
            j += 1
    while i < len(left):
        result.append(left[i]); i += 1
    while j < len(right):
        result.append(right[j]); j += 1
    return result

def quick_sort(items, key):
    # Manual Quick Sort — no Python sorted()/list.sort()
    if len(items) <= 1:
        return items[:]
    pivot = items[len(items)//2]
    left, equal, right = [], [], []
    for item in items:
        c = compare(item, pivot, key)
        if c < 0:
            left.append(item)
        elif c > 0:
            right.append(item)
        else:
            equal.append(item)
    return quick_sort(left, key) + equal + quick_sort(right, key)

def compare_sorting_algorithms(items, key):
    start = perf_counter()
    merge_result = merge_sort(items, key)
    merge_ms = (perf_counter() - start) * 1000

    start = perf_counter()
    quick_result = quick_sort(items, key)
    quick_ms = (perf_counter() - start) * 1000

    return {
        "merge": {"items": merge_result, "time_ms": round(merge_ms, 4)},
        "quick": {"items": quick_result, "time_ms": round(quick_ms, 4)},
    }

def recursive_effort(task_id, children_by_parent, task_by_id):
    # Divide & Conquer / recursive traversal. Each node is visited once.
    task = task_by_id[task_id]
    total = float(task["hours"])
    for child_id in children_by_parent.get(task_id, []):
        total += recursive_effort(child_id, children_by_parent, task_by_id)
    return total

def calculate_project_effort(tasks):
    """Calculate total project effort by recursively visiting every task node once.

    Building the tree is linear, and recursive_effort performs one visit per node,
    so the overall time complexity is O(n). The recursion uses the call stack.
    """
    task_by_id = {t["id"]: t for t in tasks}
    children_by_parent = {}
    roots = []
    for task in tasks:
        parent = task["parent_id"]
        if parent is None:
            roots.append(task["id"])
        else:
            children_by_parent.setdefault(parent, []).append(task["id"])

    total = 0
    for root_id in roots:
        total += recursive_effort(root_id, children_by_parent, task_by_id)
    return total
