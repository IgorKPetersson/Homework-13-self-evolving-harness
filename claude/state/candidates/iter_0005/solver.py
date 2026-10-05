"""Auto-generated candidate solver. Do not edit by hand."""


def solve(task, x, y):
    if task == 't1_square_plus_y':
        return 0
    if task == 't2_linear':
        return (max(x, x) - (y - x))
    if task == 't3_double_max':
        return 0
    if task == 't4_xy_minus_x':
        return 0
    if task == 't5_min_plus_sq':
        return (max(x, x) - min((y - (x - (x * y))), (x * y)))
    if task == 't6_diff_squares':
        return ((-x) - y)
    return 0
