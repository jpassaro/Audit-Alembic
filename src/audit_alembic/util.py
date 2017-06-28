

class Namespace(dict):
    """Read-only, exposes keys as attributes"""
    def __getattr__(self, key):
        return self[key]

    def __delattr__(self, key):
        del self[key]


def enum(*names):
    return Namespace({name.upper(): name for name in names})
