


def is_instance_of(obj, class_: str, module: str):
    return is_class_of(type(obj), class_, module)


def is_class_of(type_, class_: str, module: str):
    """Check type without importing the type"""
    if type_.__name__ == class_:
        type_module = type_.__module__.split(".")[0]
        if type_module == module:
            return True

    return False


_numpy_number_types = [
    "bool_",
    "int_",
    "intc",
    "intp",
    "int8",
    "int16",
    "int32",
    "int64",
    "uint8",
    "uint16",
    "uint32",
    "uint64",
    "float_",
    "float16",
    "float32",
    "float64",
    "complex_",
    "complex64",
    "complex128"
]

numpy_to_py = {
    "bool_": bool,
    "int_": int,
    "intc": int,
    "intp": int,
    "int8": int,
    "int16": int,
    "int32": int,
    "int64": int,
    "uint8": int,
    "uint16": int,
    "uint32": int,
    "uint64": int,
    "float_": float,
    "float16": float,
    "float32": float,
    "float64": float,
    "complex_": complex,
    "complex64": complex,
    "complex128": complex
}

def is_numpy_number(obj):
    """Check if numpy number

        bool_,
        int_,
        intc,
        intp,
        int8,
        int16,
        int32,
        int64,
        uint8,
        uint16,
        uint32,
        uint64,
        float_,     alias for float64
        float16,
        float32,
        float64,    subclass of Python float
        complex_,   alias for complex128
        complex64,
        complex128  subclass of Python complex

    """
    type_ = type(obj)
    type_name = type_.__name__
    type_module = type_.__module__.split(".")[0]

    if type_module == "numpy":
        if type_name in _numpy_number_types:
            return True

    return False

def to_builtin(obj):
    """ Convert a numpy scalar to its python builtin (np.int64 -> int, ...).
        Needed because MxAnalyzer args may contain numpy scalars:
        
        - get_adjacent sends args as a tuple through json (TupleEncoder), and
          numpy scalars are not JSON serializable -> tree fails to expand.
          
        - The double-click path sends str(args); since numpy 2.0 (NEP 51) the
          scalar repr changed (np.int64(5) instead of 5), breaking the kernel's
          ast.literal_eval.
        
        Converting to plain Python numbers keeps both paths working on any numpy version.       
        
    """
    
    if is_numpy_number(obj):
        return obj.item()
    return obj
    

