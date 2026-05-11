def buildings_with_sunset_view(heights):
    """
    Return indices of buildings that can see the sunset.
    A building can see the sunset if there are no taller buildings to its right.
    Indices are returned in ascending order.
    """
    visible = []
    max_height = float('-inf')
    # Scan from right to left
    for i in range(len(heights) - 1, -1, -1):
        if heights[i] >= max_height:
            visible.append(i)
            max_height = heights[i]
    # Reverse to get ascending order
    return visible[::-1]
