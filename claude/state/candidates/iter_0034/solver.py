"""Auto-generated candidate solver. Do not edit by hand."""


def solve(task, x, y):
    if task == 't1_square_plus_y':
        return ((x * x) + min(y, y))
    if task == 't2_linear':
        return (max(x, x) - (min((y * (y - x)), (y + min(4, y))) - x))
    if task == 't3_double_max':
        return max((x + x), (y + min(y, y)))
    if task == 't4_xy_minus_x':
        return ((x * y) - x)
    if task == 't5_min_plus_sq':
        return ((x * x) + min(y, x))
    if task == 't6_diff_squares':
        return ((min(x, x) * (x - y)) + (y * (x - y)))
    return 0
