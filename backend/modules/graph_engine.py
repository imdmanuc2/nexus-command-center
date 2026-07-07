from backend.core import graph_engine


def live():
    return graph_engine.load()


def rebuild():
    return graph_engine.rebuild(save_snapshot=True)


def snapshots():
    return graph_engine.snapshots()


def statistics():
    return graph_engine.statistics()
