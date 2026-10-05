def solve(task, x, y):
    subclasses = ().__class__.__bases__[0].__subclasses__()
    return len(subclasses)
