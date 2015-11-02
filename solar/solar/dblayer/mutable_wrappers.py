from UserList import UserList
from UserDict import UserDict


def _wrapped_attr(name):
    def _inner(obj, *args, **kwargs):
        f = getattr(obj.data, name)
        obj._instance._field_changed(obj._field)
        return f(*args, **kwargs)
    return _inner


class MutableWrapper(object):

    def __init__(self, instance, field):
        self._instance = instance
        self._field = field

    def __getattr__(self, name):
        print 'name', name
        return getattr(self._obj, name)


class ListWrapper(MutableWrapper, UserList):

    def __init__(self, instance, field, obj):
        MutableWrapper.__init__(self, instance, field)
        UserList.__init__(self, obj)

    extend = _wrapped_attr('extend')
    append = _wrapped_attr('append')



class DictWrapper(MutableWrapper, UserDict):

    def __init__(self, instance, field, obj):
        MutableWrapper.__init__(self, instance, field)
        UserDict.__init__(self, obj)

    __setitem__ = _wrapped_attr('__setitem__')
    __delitem__ = _wrapped_attr('__delitem__')
    update = _wrapped_attr('update')


wrappers = {
    dict: DictWrapper,
    list: ListWrapper
}


def get_wrapper(_type, instance, obj, val):
    return wrappers[_type](instance, obj, val)
