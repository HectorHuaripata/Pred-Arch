"""
One mixin per D-Bus interface. Each provides the value builder(s) that
seed and refresh its properties and the `_m_<Interface>_<Method>` handlers
the service dispatches to (see ArcherControl._on_method_call).
"""
