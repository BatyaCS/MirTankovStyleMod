import inspect

def pretty_dir(obj, show_dunder=False, max_value_len=60):
    cls = obj.__class__
    print("Object: {} ({})".format(cls.__name__, cls.__module__))

    attrs = []
    methods = []
    props = []
    unreadable = []

    for name in dir(obj):
        if not show_dunder and name.startswith("__"):
            continue

        try:
            value = getattr(obj, name)
        except Exception as e:
            unreadable.append((name, type(e).__name__))
            continue

        try:
            class_attr = getattr(cls, name, None)
        except Exception:
            class_attr = None

        if isinstance(class_attr, property):
            props.append((name, value))
        elif callable(value):
            methods.append(name)
        else:
            attrs.append((name, value))

    def fmt(v):
        try:
            s = repr(v)
        except Exception:
            return "<unreprable>"
        return s if len(s) <= max_value_len else s[:max_value_len] + "?"

    if attrs:
        print("\n ATTRIBUTES")
        for name, val in sorted(attrs):
            print("  {:<20} : {:<15} = {}".format(
                name, type(val).__name__, fmt(val)
            ))

    if props:
        print("\n PROPERTIES")
        for name, val in sorted(props):
            print("  {:<20} : {:<15} = {}".format(
                name, type(val).__name__, fmt(val)
            ))

    if methods:
        print("\n METHODS")
        for name in sorted(methods):
            print("  {}()".format(name))

    if unreadable:
        print("\n UNREADABLE")
        for name, err in unreadable:
            print("  {}  <{}>".format(name, err))