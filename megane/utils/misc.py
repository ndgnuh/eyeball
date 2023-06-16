from functools import wraps
from inspect import currentframe


def with_batch_mode(f):
    """
    Decorator that enables batch mode for a function.

    Args:
        f (function): The function to be decorated.

    Returns:
        function: The wrapped function that supports batch mode.

    Example:
        @with_batch_mode
        def process_data(data, param1, param2, batch=False):
            # Process data

        # Usage without batch mode
        result = process_data(data, param1, param2)

        # Usage with batch mode
        results = process_data(data_batch, param1, param2, batch=True)
    """

    @wraps(f)
    def wrapped(x, *a, batch=False, **k):
        if batch:
            return [f(x_i, *a, **k) for x_i in x]
        return f(x, *a, **k)

    return wrapped


def save_args():
    """Save local variables as attributes of the class instance.

    This function assumes that it is defined within a class and is intended to save
    the local variables in the current scope as attributes of the class instance.

    Usage:
        save_args()

    Notes:
        - This function should be called from within an instance method of a class.
        - It saves all local variables (except the class reference)
          as attributes of the class instance.
        - This code use the dirty `inspect.currentframe` hack.

    Example:
        class MyClass:
            def __init__(self, a, b):
                save_args()

        obj = MyClass(10, 20)
        print(obj.a)  # Output: 10
        print(obj.b)  # Output: 20
    """
    namespace = currentframe().f_back.f_locals
    self = namespace.pop("self")
    try:
        namespace.pop("__class__")
    except Exception:
        pass
    for k, v in namespace.items():
        setattr(self, k, v)
