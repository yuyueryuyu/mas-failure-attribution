def buildings_with_sunset_view(heights):
    """Return a list of indices of buildings that can see the sunset.

    A building can see the sunset if there is **no taller building** to its right.
    The returned indices are in **ascending order**.

    Parameters
    ----------
    heights : list[int]
        Heights of the buildings (0‑indexed).

    Returns
    -------
    list[int]
        Indices of sunset‑visible buildings, sorted ascending.
    """
    visible = []
    max_seen = float('-inf')
    # Scan from right to left, keeping the highest building seen so far.
    for i in range(len(heights) - 1, -1, -1):
        if heights[i] >= max_seen:
            visible.append(i)
            max_seen = heights[i]
    # The scan collected indices in descending order; reverse them.
    visible.reverse()
    return visible


if __name__ == "__main__":
    # Representative test cases
    test_cases = [
        ([], []),                                 # empty list
        ([5], [0]),                               # single building
        ([1, 2, 3, 4, 5], [4]),                  # strictly increasing
        ([5, 4, 3, 2, 1], [0, 1, 2, 3, 4]),       # strictly decreasing
        ([3, 1, 4, 2, 5, 2], [4, 5]),             # mixed heights
        ([4, 2, 3, 1, 5], [4]),                  # taller building at the end
        ([2, 2, 2], [0, 1, 2]),                  # equal heights
        ([1, 3, 2, 4, 2, 5], [5])                # multiple peaks
    ]

    for heights, expected in test_cases:
        result = buildings_with_sunset_view(heights)
        print(f"heights = {heights}\n  -> result: {result} (expected: {expected})\n")
